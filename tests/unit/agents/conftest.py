"""Fixtures for the `flamescope_agents` unit tests: mock gateway, scripted model, payloads.

Payload values are test-only placeholders; none is a scientific fact about a real
investigation, and sources point at test keys in the public bucket shape.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.config import Settings, get_settings
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.llm.providers.mock import MockProvider
from flamescope_common.rubric import Presets

SOURCE = {"kind": "document", "uri": "s3://nasa-psi/test-folder/overview.pdf"}
LUNAR_GRAVITY_G = 0.166


class InMemoryLLMCache:
    """Stands in for the database-backed `llm_cache` table (document 04 section 2)."""

    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self.entries.get(key)

    def put(self, key: str, provider: str, model: str, response: dict[str, Any]) -> None:
        self.entries[key] = response


class ScriptedLlm(BaseLlm):
    """ADK model that answers with the next scripted text and records every user prompt."""

    model: str = "scripted"
    replies: list[str]
    prompts: list[str] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        user_turn = llm_request.contents[-1]
        self.prompts.append("".join(part.text or "" for part in user_turn.parts or []))
        reply = self.replies[min(len(self.prompts), len(self.replies)) - 1]
        if reply.startswith("RAISE:"):
            raise RuntimeError(reply)
        content = types.Content(role="model", parts=[types.Part(text=reply)])
        yield LlmResponse(content=content, partial=False)


class ScriptedProvider:
    """`LLMProvider` whose model is one shared `ScriptedLlm`."""

    name = "mock"

    def __init__(self, llm: ScriptedLlm) -> None:
        self.llm = llm

    def model(self) -> BaseLlm:
        return self.llm

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def mock_gateway(settings: Settings) -> LLMGateway:
    provider = MockProvider(embed_dim=settings.embed_dim)
    return LLMGateway(
        settings=settings,
        cache=InMemoryLLMCache(),  # type: ignore[arg-type]
        providers={"mock": provider},
    )


@pytest.fixture
def orchestrator(mock_gateway: LLMGateway, settings: Settings) -> AgentOrchestrator:
    return AgentOrchestrator(gateway=mock_gateway, settings=settings)


ScriptedFactory = Callable[[list[str]], tuple[AgentOrchestrator, ScriptedLlm]]


@pytest.fixture
def scripted_orchestrator(settings: Settings) -> ScriptedFactory:
    """An orchestrator whose model replies with the given texts in order."""

    def build(replies: list[str]) -> tuple[AgentOrchestrator, ScriptedLlm]:
        llm = ScriptedLlm(replies=replies, prompts=[])
        gateway = LLMGateway(
            settings=settings,
            cache=InMemoryLLMCache(),  # type: ignore[arg-type]
            providers={"mock": ScriptedProvider(llm)},
        )
        return AgentOrchestrator(gateway=gateway, settings=settings), llm

    return build


@pytest.fixture
def sample_card() -> dict[str, Any]:
    return {
        "acronym": "TEST-1",
        "title": "Test Investigation One",
        "platform": "ISS",
        "gravity_level": "microgravity",
        "hardware": [{"name": "Test rack", "role": "host"}],
        "fuels": [{"name": "test sheet", "phase": "solid", "source": SOURCE}],
        "conditions": {
            "o2_fraction": {"min": 0.15, "max": 0.40, "source": SOURCE},
            "pressure_kpa": {"min": 50.0, "max": 101.3, "source": SOURCE},
            "gravity_g": [0, 1],
        },
        "variables": {"varied": ["o2_fraction", "pressure_kpa"], "fixed": []},
        "fire_safety_tags": ["flame_spread", "solid_fuel"],
    }


@pytest.fixture
def empty_card() -> dict[str, Any]:
    return {"acronym": "TEST-0", "title": "Test Investigation Without Facts"}


def criteria_for(lens_criteria: list[str]) -> list[dict[str, Any]]:
    return [
        {"id": cid, "label": cid.replace("_", " "), "anchors": {0: "low", 3: "mid", 5: "high"}}
        for cid in lens_criteria
    ]


HABITAT_CRITERIA = [
    "fuel_realism",
    "atmosphere_match",
    "flow_regime",
    "phenomenon",
    "gravity_bounding",
]


@pytest.fixture
def scorer_payload(sample_card: dict[str, Any]) -> dict[str, Any]:
    return {
        "acronym": "TEST-1",
        "lens": "habitat",
        "criteria": criteria_for(HABITAT_CRITERIA),
        "card": sample_card,
        "excerpts": [{"chunk_id": 11, "text": "Test samples burned in a test duct."}],
    }


@pytest.fixture
def extractor_payload() -> dict[str, Any]:
    return {
        "acronym": "TEST-1",
        "title": "Test Investigation One",
        "psi_url": "https://psi.nasa.gov/test-1",
        "context": [
            {
                "doc_id": "doc-1",
                "title": "Overview",
                "section": "1",
                "text": "Test samples were burned on the ISS in microgravity. Flame spread "
                "was recorded with a camera.",
            }
        ],
    }


def fact(fact_id: str, text: str) -> dict[str, Any]:
    return {"id": fact_id, "text": text, "source": SOURCE}


@pytest.fixture
def comparator_payload() -> dict[str, Any]:
    return {
        "investigations": [{"acronym": "TEST-1"}, {"acronym": "TEST-2"}],
        "matrix": [
            {
                "attribute": "platform",
                "label": "Platform",
                "group": "context",
                "values": {"TEST-1": "ISS", "TEST-2": "ISS"},
                "same": True,
            },
            {
                "attribute": "fuel_phases",
                "label": "Fuel phases",
                "group": "fuel",
                "values": {"TEST-1": ["solid"], "TEST-2": ["gas"]},
                "same": False,
            },
        ],
        "shared": {"hardware": ["Test rack"], "tags": [], "instruments": []},
        "facts": [
            fact("f1", "TEST-1 burned test sheets."),
            fact("f2", "TEST-2 burned a test gas."),
        ],
    }


@pytest.fixture
def gravity_statement() -> str:
    return Presets.load().gravity_bounding_statement(LUNAR_GRAVITY_G)


def scenario_payload_for(gravity_g: float, statement: str | None) -> dict[str, Any]:
    return {
        "scenario": {
            "preset": "lunar_habitat",
            "o2_fraction": 0.34,
            "pressure_kpa": 56.5,
            "gravity_g": gravity_g,
            "flow_speed_cm_s": 10,
            "assumed_default": True,
        },
        "coverage": {
            "o2_fraction": {"state": "covered", "catalog_range": [0.1, 0.5]},
            "pressure_kpa": {"state": "extrapolated", "catalog_range": [60.0, 101.3]},
            "flow_speed_cm_s": {"state": "no_data"},
            "gravity_g": {"state": "no_data", "catalog_values": [0.0, 1.0]},
        },
        "matches": [{"acronym": "TEST-1", "similarity": 0.7, "median_similarity": 0.6}],
        "gravity_bounding": {"partial_gravity_data": False, "statement": statement},
        "facts": [fact("m1", "TEST-1 matches the oxygen fraction of the scenario.")],
    }


@pytest.fixture
def scenario_payload(gravity_statement: str) -> dict[str, Any]:
    return scenario_payload_for(LUNAR_GRAVITY_G, gravity_statement)


@pytest.fixture
def insight_payload() -> dict[str, Any]:
    return {
        "question": "Which test burned samples in microgravity?",
        "chunks": [
            {
                "chunk_id": 101,
                "acronym": "TEST-1",
                "doc_title": "Overview",
                "text": "TEST-1 burned samples in microgravity. Results are in the report.",
            },
            {
                "chunk_id": 102,
                "acronym": "TEST-2",
                "doc_title": "Report",
                "text": "TEST-2 measured flame spread rates.",
            },
        ],
        "card_facts": [{"id": 45, "acronym": "TEST-1", "text": "TEST-1 flew on the ISS."}],
    }


@pytest.fixture
def earth_payload() -> dict[str, Any]:
    return {
        "findings": [
            {
                "id": 1,
                "acronym": "TEST-1",
                "statement": "Smoke was observed.",
                "category": "detection",
            },
            {
                "id": 2,
                "acronym": "TEST-1",
                "statement": "A flame went out.",
                "category": "suppression",
            },
        ],
        "known_applications": [],
    }


PAYLOAD_FIXTURES = {
    "extractor": "extractor_payload",
    "scorer": "scorer_payload",
    "comparator": "comparator_payload",
    "scenario_interpreter": "scenario_payload",
    "insight_qa": "insight_payload",
    "earth_apps": "earth_payload",
}


@pytest.fixture
def agent_payloads(request: pytest.FixtureRequest) -> dict[str, dict[str, Any]]:
    """A valid input payload per agent name."""
    return {agent: request.getfixturevalue(fixture) for agent, fixture in PAYLOAD_FIXTURES.items()}
