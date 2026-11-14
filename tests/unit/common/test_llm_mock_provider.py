"""Deterministic mock provider (document 07 section 6; document 12 section 1; NFR-02)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from flamescope_common.config import Settings
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.llm.providers.mock import MockLlm, MockProvider
from flamescope_common.schemas.agents import (
    ComparatorOutput,
    EarthAppsOutput,
    ExtractorOutput,
    ScenarioInterpreterOutput,
    ScorerOutput,
)

pytestmark = pytest.mark.unit

EMBED_DIM = 768
NORM_TOLERANCE = 1e-9
MOCK_VECTOR_FLOOR = 0.2  # doc 05 s10, mock provider
FIXTURE_KEY_LENGTH = 16
CITATION_MARKER = re.compile(r"\[[cf]:\d+\]")
SOURCE = {"kind": "document", "uri": "s3://nasa-psi/test/doc.pdf"}
INSUFFICIENT = "The curated PSI corpus does not contain enough information to answer that."

AGENT_INPUTS: dict[str, dict[str, Any]] = {
    "extractor": {
        "acronym": "TEST-1",
        "title": "Test",
        "psi_url": "https://psi.nasa.gov/test",
        "context": [
            {"doc_id": "d1", "title": "Overview", "text": "A flame spread test on the ISS."}
        ],
    },
    "scorer": {
        "acronym": "TEST-1",
        "lens": "habitat",
        "criteria": [{"id": "fuel_realism", "label": "Fuel realism"}],
        "card": {"acronym": "TEST-1", "title": "Test"},
    },
    "comparator": {
        "investigations": [{"acronym": "A"}, {"acronym": "B"}],
        "matrix": [],
        "shared": {},
        "facts": [{"id": "f1", "text": "A burned a test fuel.", "source": SOURCE}],
    },
    "scenario_interpreter": {
        "scenario": {"o2_fraction": 0.3},
        "coverage": {"o2_fraction": {"state": "covered"}},
        "matches": [],
        "gravity_bounding": {"partial_gravity_data": False},
        "facts": [],
    },
    "insight_qa": {
        "question": "What burned?",
        "chunks": [{"chunk_id": 7, "acronym": "A", "doc_title": "Doc", "text": "A test burned."}],
    },
    "earth_apps": {
        "findings": [
            {"id": 3, "acronym": "A", "statement": "Smoke was seen.", "category": "detection"}
        ]
    },
}
OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "extractor": ExtractorOutput,
    "scorer": ScorerOutput,
    "comparator": ComparatorOutput,
    "scenario_interpreter": ScenarioInterpreterOutput,
    "earth_apps": EarthAppsOutput,
}

RequestFactory = Callable[..., LlmRequest]


def user_prompt(agent_name: str) -> str:
    return f"Task data:\n{json.dumps(AGENT_INPUTS[agent_name])}\n"


async def complete(model: BaseLlm, request: LlmRequest, *, stream: bool = False) -> list[Any]:
    return [response async for response in model.generate_content_async(request, stream=stream)]


def final_text(responses: list[Any]) -> str:
    return "".join(part.text for part in responses[-1].content.parts)


def test_mock_llm_is_an_adk_model() -> None:
    """NFR-02: `MockLlm` subclasses ADK `BaseLlm`."""
    assert isinstance(MockProvider(embed_dim=EMBED_DIM).model(), BaseLlm)


@pytest.mark.parametrize("agent_name", list(OUTPUT_MODELS))
async def test_output_validates_against_agent_schema(
    agent_name: str, make_llm_request: RequestFactory
) -> None:
    """NFR-02: schema-valid mock output for every JSON agent."""
    responses = await complete(MockLlm(), make_llm_request(user_prompt(agent_name)))

    OUTPUT_MODELS[agent_name].model_validate_json(final_text(responses))


async def test_insight_qa_answer_cites_supplied_chunks(make_llm_request: RequestFactory) -> None:
    """NFR-02: the mock answer carries citation markers for supplied chunks."""
    responses = await complete(MockLlm(), make_llm_request(user_prompt("insight_qa")))

    assert CITATION_MARKER.findall(final_text(responses)) == ["[c:7]"]


async def test_insight_qa_without_context_refuses(make_llm_request: RequestFactory) -> None:
    """FR-11: no context gives the fixed sentence of document 05 section 10."""
    request = make_llm_request(json.dumps({"question": "What is the answer?"}))

    assert final_text(await complete(MockLlm(), request)) == INSUFFICIENT


@pytest.mark.parametrize("agent_name", list(AGENT_INPUTS))
async def test_same_input_gives_same_output(
    agent_name: str, make_llm_request: RequestFactory
) -> None:
    """NFR-02: determinism across calls and instances."""
    first = await complete(MockLlm(), make_llm_request(user_prompt(agent_name)))
    second = await complete(MockLlm(), make_llm_request(user_prompt(agent_name)))

    assert final_text(first) == final_text(second)


async def test_input_is_found_in_system_text(make_llm_request: RequestFactory) -> None:
    """NFR-02: the input is found in `## User`, then in `## System` (document 07 section 6)."""
    request = make_llm_request("Return the JSON object only.", system=user_prompt("scorer"))

    output = ScorerOutput.model_validate_json(final_text(await complete(MockLlm(), request)))

    assert output.lens == "habitat"


async def test_streaming_yields_partial_deltas_then_the_full_text(
    make_llm_request: RequestFactory,
) -> None:
    """FR-11: streaming builds the answer from deltas."""
    responses = await complete(MockLlm(), make_llm_request(user_prompt("insight_qa")), stream=True)
    partials = [r for r in responses if r.partial]

    assert partials
    assert "".join(r.content.parts[0].text for r in partials) == final_text(responses)
    assert responses[-1].partial is False


async def test_fixture_file_is_used_when_present(
    tmp_path: Path, make_llm_request: RequestFactory
) -> None:
    """NFR-02: `fixtures/<agent>/<sha256(user)[:16]>.json` wins over synthesis."""
    prompt = user_prompt("earth_apps")
    key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:FIXTURE_KEY_LENGTH]
    fixture = EarthAppsOutput(applications=[]).model_dump_json()
    (tmp_path / "earth_apps").mkdir()
    (tmp_path / "earth_apps" / f"{key}.json").write_text(fixture, encoding="utf-8")

    responses = await complete(MockLlm(fixtures_dir=tmp_path), make_llm_request(prompt))

    assert final_text(responses) == fixture


async def test_mock_llm_runs_inside_an_adk_runner() -> None:
    """NFR-07: an ADK `LlmAgent` on `MockLlm` runs through a `Runner`."""
    agent = LlmAgent(
        name="scorer",
        model=MockLlm(),
        instruction=lambda _context: "Score the investigation.",
        output_schema=ScorerOutput,
    )
    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name="flamescope", user_id="test")
    runner = Runner(app_name="flamescope", agent=agent, session_service=sessions)
    message = types.Content(role="user", parts=[types.Part(text=user_prompt("scorer"))])

    events = [
        event
        async for event in runner.run_async(
            user_id="test", session_id=session.id, new_message=message
        )
    ]
    final = [event for event in events if event.is_final_response()][-1]

    ScorerOutput.model_validate_json(final.content.parts[0].text)


def test_embedding_has_embed_dim_and_unit_norm() -> None:
    """NFR-02: hashed bag-of-words vector of `EMBED_DIM`, L2-normalized."""
    vectors = MockProvider(embed_dim=EMBED_DIM).embed(["flame spread in microgravity", ""])

    assert [len(vector) for vector in vectors] == [EMBED_DIM, EMBED_DIM]
    for vector in vectors:
        assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(
            1.0, abs=NORM_TOLERANCE
        )


def test_embedding_is_deterministic_and_text_dependent() -> None:
    """NFR-02: same text, same vector; different text, different vector."""
    provider = MockProvider(embed_dim=EMBED_DIM)

    assert provider.embed(["soot"]) == provider.embed(["soot"])
    assert provider.embed(["soot"]) != provider.embed(["droplet"])


def test_embedding_ignores_function_words() -> None:
    """FR-11, doc 07 s6: only content words are hashed, so shared function words add nothing."""
    provider = MockProvider(embed_dim=EMBED_DIM)
    question, chunk, content_only = provider.embed(
        [
            "What is the capital of France?",
            "What is the effect of the flow on the flame?",
            "effect flow flame",
        ]
    )
    cosine = sum(left * right for left, right in zip(question, chunk, strict=True))
    assert (cosine < MOCK_VECTOR_FLOOR, chunk == content_only) == (True, True)


def test_gateway_embeddings_follow_embed_dim_setting(llm_cache: object) -> None:
    """NFR-02: the gateway's mock embeddings have length `EMBED_DIM`."""
    settings = Settings(_env_file=None, embed_dim=32)  # type: ignore[call-arg]
    gateway = LLMGateway(settings=settings, cache=llm_cache)  # type: ignore[arg-type]

    assert [len(vector) for vector in gateway.embed(["a", "b"])] == [32, 32]


async def test_unidentified_request_gets_a_schema_valid_fallback() -> None:
    """NFR-02: without a recognizable input the mock still answers within the schema."""
    config = types.GenerateContentConfig(response_json_schema=ComparatorOutput.model_json_schema())
    content = types.Content(role="user", parts=[types.Part(text="no agent input here")])
    request = LlmRequest(contents=[content], config=config)

    ComparatorOutput.model_validate_json(final_text(await complete(MockLlm(), request)))
