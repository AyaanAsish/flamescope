"""`base.Agent`: rendering, ADK `LlmAgent`, validation and schema retry (document 07 s2, s5)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from google.adk.agents import LlmAgent
from pydantic import BaseModel

from flamescope_agents.base import MAX_SCHEMA_RETRIES, Agent
from flamescope_agents.comparator import ComparatorAgent
from flamescope_agents.earth_apps import EarthAppsAgent
from flamescope_agents.extractor import ExtractorAgent
from flamescope_agents.insight_qa import InsightQAAgent
from flamescope_agents.scenario_interpreter import ScenarioInterpreterAgent
from flamescope_agents.scorer import ScorerAgent
from flamescope_common.errors import LLMError, ValidationError
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.llm.providers.mock import MockLlm
from flamescope_common.schemas import agents as agent_schemas

pytestmark = pytest.mark.unit

AGENT_CONTRACTS: dict[type[Agent], tuple[str, str, str | None]] = {
    ExtractorAgent: ("extractor", "ExtractorInput", "ExtractorOutput"),
    ScorerAgent: ("scorer", "ScorerInput", "ScorerOutput"),
    ComparatorAgent: ("comparator", "ComparatorInput", "ComparatorOutput"),
    ScenarioInterpreterAgent: (
        "scenario_interpreter",
        "ScenarioInterpreterInput",
        "ScenarioInterpreterOutput",
    ),
    InsightQAAgent: ("insight_qa", "InsightQAInput", None),
    EarthAppsAgent: ("earth_apps", "EarthAppsInput", "EarthAppsOutput"),
}
EXPECTED_ATTEMPTS = MAX_SCHEMA_RETRIES + 1
DOCUMENTED_MAX_RETRIES = 2
INVALID_JSON = "{not json"


class ScriptedExecute:
    """Replaces the ADK runner: returns scripted texts and records every user message."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.user_messages: list[str] = []

    async def __call__(self, _llm_agent: LlmAgent, user_message: str) -> str:
        self.user_messages.append(user_message)
        return self.replies[min(len(self.user_messages), len(self.replies)) - 1]


def schema_model(name: str | None) -> type[BaseModel] | None:
    return getattr(agent_schemas, name) if name else None


@pytest.fixture
def scorer(mock_gateway: LLMGateway) -> ScorerAgent:
    return ScorerAgent(mock_gateway)


@pytest.mark.parametrize("agent_class", list(AGENT_CONTRACTS))
def test_agent_declares_its_contract(agent_class: type[Agent]) -> None:
    """NFR-07: one agent, one prompt, one input schema, one output schema (doc 07 s1)."""
    name, input_name, output_name = AGENT_CONTRACTS[agent_class]

    assert agent_class.name == name
    assert agent_class.input_model is getattr(agent_schemas, input_name)
    assert agent_class.output_model is schema_model(output_name)


@pytest.mark.parametrize("agent_class", list(AGENT_CONTRACTS))
def test_builds_adk_llm_agent_without_tools(
    agent_class: type[Agent], mock_gateway: LLMGateway, agent_payloads: dict[str, Any]
) -> None:
    """NFR-07: an ADK `LlmAgent` with no tools, the right `output_schema`, gateway model."""
    agent = agent_class(mock_gateway)
    rendered = agent.render(agent.validate_input(agent_payloads[agent.name]))

    llm_agent = agent.build_llm_agent(rendered, mock_gateway.callbacks())

    assert isinstance(llm_agent, LlmAgent)
    assert llm_agent.tools == []
    assert llm_agent.output_schema is schema_model(AGENT_CONTRACTS[agent_class][2])
    assert isinstance(llm_agent.model, MockLlm)


def test_generation_config_comes_from_front_matter(
    scorer: ScorerAgent, scorer_payload: dict[str, Any], mock_gateway: LLMGateway
) -> None:
    """NFR-07: `temperature` and `max_tokens` map to `GenerateContentConfig`."""
    rendered = scorer.render(scorer.validate_input(scorer_payload))
    config = scorer.build_llm_agent(rendered, mock_gateway.callbacks()).generate_content_config

    assert config is not None
    assert (config.temperature, config.max_output_tokens) == (
        scorer.prompt.temperature,
        scorer.prompt.max_tokens,
    )


def test_render_embeds_input_json_and_scalar_fields(
    scorer: ScorerAgent, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: `{{input_json}}` is the validated payload; scalars such as `{{acronym}}`."""
    payload = scorer.validate_input(scorer_payload)

    rendered = scorer.render(payload)
    embedded = next(line for line in rendered.user.splitlines() if line.startswith("{"))

    assert json.loads(embedded) == payload.model_dump(mode="json")
    assert "Score TEST-1 on the habitat lens" in rendered.user
    assert "{{" not in rendered.system + rendered.user


def test_validation_feedback_is_empty_on_the_first_attempt(
    scorer: ScorerAgent, scorer_payload: dict[str, Any]
) -> None:
    """NFR-07: `{{validation_feedback}}` is empty first and the error on a retry."""
    payload = scorer.validate_input(scorer_payload)

    first = scorer.render(payload)
    retry = scorer.render(payload, "lens: field required")

    assert "lens: field required" not in first.user
    assert retry.user.rstrip().endswith("Return the JSON object only.")
    assert "lens: field required" in retry.user


def test_invalid_input_is_a_validation_error(scorer: ScorerAgent) -> None:
    """NFR-07: payloads are validated against the input schema."""
    with pytest.raises(ValidationError):
        scorer.validate_input({"acronym": "TEST-1", "lens": "astrology"})


def test_parse_output_validates_json(scorer: ScorerAgent) -> None:
    """NFR-07: every agent output is Pydantic-validated."""
    valid = json.dumps({"lens": "habitat", "scores": []})

    assert scorer.parse_output(valid) == agent_schemas.ScorerOutput(lens="habitat", scores=[])
    with pytest.raises(ValueError, match=r"(?i)json"):
        scorer.parse_output(INVALID_JSON)


def test_maximum_retries_is_two() -> None:
    """NFR-07: retry up to 2 times on schema failure (document 07 section 5)."""
    assert MAX_SCHEMA_RETRIES == DOCUMENTED_MAX_RETRIES


async def test_invalid_json_is_retried_with_the_error_appended(
    scorer: ScorerAgent, scorer_payload: dict[str, Any], mock_gateway: LLMGateway
) -> None:
    """NFR-07: on schema failure the validation error is sent back as feedback."""
    execute = ScriptedExecute([INVALID_JSON, json.dumps({"lens": "habitat", "scores": []})])
    payload = scorer.validate_input(scorer_payload)

    run = await scorer.run_validated(payload, execute, mock_gateway.callbacks())

    assert run.retries == 1
    assert len(execute.user_messages) == EXPECTED_ATTEMPTS - 1
    assert "Invalid JSON" in execute.user_messages[1]


async def test_final_failure_raises_llm_error_after_two_retries(
    scorer: ScorerAgent, scorer_payload: dict[str, Any], mock_gateway: LLMGateway
) -> None:
    """NFR-07: `LLMError` after the last of 1 + 2 attempts."""
    execute = ScriptedExecute([INVALID_JSON])
    payload = scorer.validate_input(scorer_payload)

    with pytest.raises(LLMError):
        await scorer.run_validated(payload, execute, mock_gateway.callbacks())
    assert len(execute.user_messages) == EXPECTED_ATTEMPTS


async def test_schema_violation_is_retried(
    scorer: ScorerAgent, scorer_payload: dict[str, Any], mock_gateway: LLMGateway
) -> None:
    """NFR-07: valid JSON that breaks the schema (value without evidence) is retried."""
    no_evidence = {"lens": "habitat", "scores": [{"criterion": "fuel_realism", "value": 4}]}
    execute = ScriptedExecute(
        [json.dumps(no_evidence), json.dumps({"lens": "habitat", "scores": []})]
    )

    run = await scorer.run_validated(
        scorer.validate_input(scorer_payload), execute, mock_gateway.callbacks()
    )

    assert run.retries == 1
    assert "evidence" in execute.user_messages[1]


async def test_text_agent_retries_an_empty_answer(
    mock_gateway: LLMGateway, insight_payload: dict[str, Any]
) -> None:
    """FR-11: the plain-text agent rejects an empty answer."""
    agent = InsightQAAgent(mock_gateway)
    execute = ScriptedExecute(["   ", "TEST-1 burned samples in microgravity. [c:101]"])

    run = await agent.run_validated(
        agent.validate_input(insight_payload), execute, mock_gateway.callbacks()
    )

    assert run.output == "TEST-1 burned samples in microgravity. [c:101]"
    assert run.retries == 1
