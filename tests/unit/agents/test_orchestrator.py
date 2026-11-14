"""`AgentOrchestrator` (document 07 section 5; document 03 section 3; NFR-07)."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, ClassVar

import pytest
from google.adk.runners import Runner
from pydantic import BaseModel
from structlog.testing import capture_logs

from flamescope_agents import orchestrator as orchestrator_module
from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import LLMError, ValidationError
from flamescope_common.llm.providers.mock import MockLlm
from flamescope_common.logging import request_id_var
from flamescope_common.schemas.agents import (
    ComparatorOutput,
    EarthAppsOutput,
    ExtractorOutput,
    ScenarioInterpreterOutput,
    ScorerOutput,
)

pytestmark = pytest.mark.unit

AGENTS_DOC = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "07-agents-and-llm.md"
VERSION_KEY_ROW = re.compile(r"^\| `(\w+)\.md` \| \w+ \| `(\1@\d+)` \|$", re.MULTILINE)
DOCUMENTED_VERSION_KEYS = dict(VERSION_KEY_ROW.findall(AGENTS_DOC.read_text(encoding="utf-8")))

AGENT_NAMES = [
    "comparator",
    "earth_apps",
    "extractor",
    "insight_qa",
    "scenario_interpreter",
    "scorer",
]
OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "extractor": ExtractorOutput,
    "scorer": ScorerOutput,
    "comparator": ComparatorOutput,
    "scenario_interpreter": ScenarioInterpreterOutput,
    "earth_apps": EarthAppsOutput,
}
LOG_FIELDS = {"agent", "prompt_version", "provider", "model", "latency_ms", "cache_hit", "retries"}
INVALID_JSON = "{not json"
# Distinct invalid replies give distinct validation feedback, so no retry prompt repeats.
INVALID_REPLIES = ["{not json", '{"lens": "astrology"}', '["not", "an", "object"]']
VALID_SCORER_REPLY = json.dumps({"lens": "habitat", "scores": []})


class RecordingRunner(Runner):
    """ADK `Runner` that records the user ID and agent of every run."""

    runs: ClassVar[list[tuple[str, Any]]] = []

    def run_async(self, *, user_id: str, **kwargs: Any) -> Any:
        RecordingRunner.runs.append((user_id, self.agent))
        return super().run_async(user_id=user_id, **kwargs)


@pytest.fixture
def recording_runner(monkeypatch: pytest.MonkeyPatch) -> type[RecordingRunner]:
    RecordingRunner.runs = []
    monkeypatch.setattr(orchestrator_module, "Runner", RecordingRunner)
    return RecordingRunner


def agent_run_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in logs if entry["event"] == "agent_run"]


def test_registers_every_agent(orchestrator: AgentOrchestrator) -> None:
    """NFR-07: the registry holds the six agents of document 07 section 3."""
    assert orchestrator.agent_names() == AGENT_NAMES


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_prompt_version_is_the_version_key(orchestrator: AgentOrchestrator, name: str) -> None:
    """NFR-07: `prompt_version(name)` is the version key in the document 07 section 2 table."""
    assert orchestrator.prompt_version(name) == DOCUMENTED_VERSION_KEYS[name]


def test_unknown_agent_is_rejected(orchestrator: AgentOrchestrator) -> None:
    """NFR-07: the orchestrator resolves agents by name."""
    with pytest.raises(ValidationError):
        orchestrator.prompt_version("summarizer")


def test_invalid_payload_is_rejected_before_any_model_call(
    orchestrator: AgentOrchestrator, recording_runner: type[RecordingRunner]
) -> None:
    """NFR-07: step 1 validates the payload against the input schema."""
    with pytest.raises(ValidationError):
        orchestrator.run("scorer", {"acronym": "TEST-1"})
    assert recording_runner.runs == []


@pytest.mark.parametrize("name", list(OUTPUT_MODELS))
async def test_run_returns_the_validated_output_model(
    orchestrator: AgentOrchestrator, agent_payloads: dict[str, Any], name: str
) -> None:
    """NFR-02: every JSON agent returns its schema-valid output model in mock mode."""
    output = await orchestrator.run(name, agent_payloads[name])

    assert isinstance(output, OUTPUT_MODELS[name])


async def test_runs_through_an_adk_runner_on_mock_llm(
    orchestrator: AgentOrchestrator,
    scorer_payload: dict[str, Any],
    recording_runner: type[RecordingRunner],
) -> None:
    """NFR-07: one ADK `Runner` per call, agent model `MockLlm`, no tools."""
    await orchestrator.run("scorer", scorer_payload)

    [(_user_id, llm_agent)] = recording_runner.runs
    assert isinstance(llm_agent.model, MockLlm)
    assert llm_agent.tools == []


async def test_request_id_is_attached_to_the_run(
    orchestrator: AgentOrchestrator,
    scorer_payload: dict[str, Any],
    recording_runner: type[RecordingRunner],
) -> None:
    """NFR-07: the orchestrator attaches the request ID (document 03 section 3)."""
    token = request_id_var.set("req-test-1")
    try:
        await orchestrator.run("scorer", scorer_payload)
    finally:
        request_id_var.reset(token)

    assert recording_runner.runs[0][0] == "req-test-1"


async def test_insight_qa_returns_text(
    orchestrator: AgentOrchestrator, insight_payload: dict[str, Any]
) -> None:
    """FR-11: `await run("insight_qa", ...)` returns a `str`."""
    answer = await orchestrator.run("insight_qa", insight_payload)

    assert isinstance(answer, str)
    assert answer


async def test_stream_yields_deltas_that_join_to_the_answer(
    orchestrator: AgentOrchestrator, insight_payload: dict[str, Any]
) -> None:
    """FR-11: `run(..., stream=True)` is an async iterator of text deltas."""
    deltas = [
        delta async for delta in orchestrator.run("insight_qa", insight_payload, stream=True)
    ]
    answer = await orchestrator.run("insight_qa", insight_payload)

    assert len(deltas) > 1
    assert "".join(deltas) == answer


def test_sync_callers_use_asyncio_run(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: ingestion stages call `asyncio.run(orchestrator.run(name, payload))`."""
    output = asyncio.run(orchestrator.run("scorer", scorer_payload))

    assert isinstance(output, ScorerOutput)


async def test_logs_the_documented_fields(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: log agent, prompt_version, provider, model, latency_ms, cache_hit, retries."""
    with capture_logs() as logs:
        await orchestrator.run("scorer", scorer_payload)

    [entry] = agent_run_logs(logs)
    assert set(entry) >= LOG_FIELDS
    assert (entry["agent"], entry["prompt_version"]) == ("scorer", "scorer@1")
    assert (entry["provider"], entry["model"], entry["retries"]) == ("mock", "mock", 0)


async def test_second_identical_call_is_a_cache_hit(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: the response cache is visible as `cache_hit` in the log."""
    with capture_logs() as logs:
        first = await orchestrator.run("scorer", scorer_payload)
        second = await orchestrator.run("scorer", scorer_payload)

    assert first == second
    assert [entry["cache_hit"] for entry in agent_run_logs(logs)] == [False, True]


async def test_retries_on_invalid_json_and_logs_the_count(
    scripted_orchestrator: Any, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: invalid JSON is retried with `{{validation_feedback}}`, at most twice."""
    orchestrator, llm = scripted_orchestrator([*INVALID_REPLIES[:2], VALID_SCORER_REPLY])

    with capture_logs() as logs:
        output = await orchestrator.run("scorer", scorer_payload)

    assert output == ScorerOutput(lens="habitat", scores=[])
    assert len(llm.prompts) == 3
    assert "validation error" in llm.prompts[-1]
    assert agent_run_logs(logs)[0]["retries"] == 2


async def test_llm_error_after_final_failure(
    scripted_orchestrator: Any, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: `LLMError` once the two retries are used up."""
    orchestrator, llm = scripted_orchestrator(INVALID_REPLIES)

    with capture_logs() as logs, pytest.raises(LLMError):
        await orchestrator.run("scorer", scorer_payload)

    assert len(llm.prompts) == 3
    assert agent_run_logs(logs)[0]["retries"] == 2


async def test_provider_failure_raises_llm_error(
    scripted_orchestrator: Any, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: a failing model call surfaces as `LLMError`; callers decide the fallback."""
    orchestrator, _llm = scripted_orchestrator(["RAISE: provider down"])

    with pytest.raises(LLMError):
        await orchestrator.run("scorer", scorer_payload)
