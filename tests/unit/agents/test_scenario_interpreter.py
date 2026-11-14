"""`ScenarioInterpreterAgent` contract (document 07 section 3; document 08 4.4; FR-07, FR-16)."""

from __future__ import annotations

from typing import Any

import pytest

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import ValidationError
from flamescope_common.schemas.agents import ScenarioInterpreterOutput

pytestmark = pytest.mark.unit

TOP_MATCHES = 5
FLAGGED_STATES = {"extrapolated", "no_data"}


def all_text(output: ScenarioInterpreterOutput) -> list[str]:
    return [sentence.text for sentence in output.sentences] + output.caveats


@pytest.mark.parametrize(
    "missing", ["scenario", "coverage", "matches", "gravity_bounding", "facts"]
)
def test_input_requires_every_documented_field(
    orchestrator: AgentOrchestrator, scenario_payload: dict[str, Any], missing: str
) -> None:
    """FR-07: input `{scenario, coverage, matches, gravity_bounding, facts}`."""
    payload = {key: value for key, value in scenario_payload.items() if key != missing}

    with pytest.raises(ValidationError):
        orchestrator.run("scenario_interpreter", payload)


def test_matches_are_limited_to_the_top_five(
    orchestrator: AgentOrchestrator, scenario_payload: dict[str, Any]
) -> None:
    """FR-07: matches are the top 5 with runs."""
    match = scenario_payload["matches"][0]
    payload = scenario_payload | {"matches": [match] * (TOP_MATCHES + 1)}

    with pytest.raises(ValidationError):
        orchestrator.run("scenario_interpreter", payload)


def test_coverage_state_must_be_documented(
    orchestrator: AgentOrchestrator, scenario_payload: dict[str, Any]
) -> None:
    """FR-07: coverage states `covered`, `extrapolated`, `no_data` (document 04 section 5)."""
    payload = scenario_payload | {"coverage": {"o2_fraction": {"state": "partial"}}}

    with pytest.raises(ValidationError):
        orchestrator.run("scenario_interpreter", payload)


async def test_mock_output_is_schema_valid(
    orchestrator: AgentOrchestrator, scenario_payload: dict[str, Any]
) -> None:
    """NFR-02: `{sentences:[{text, fact_ids}], caveats}` in mock mode."""
    output = await orchestrator.run("scenario_interpreter", scenario_payload)

    assert isinstance(output, ScenarioInterpreterOutput)
    assert output.sentences


@pytest.mark.parametrize("gravity_g", [0.166, 0.38])
async def test_repeats_gravity_statement_for_partial_gravity(
    orchestrator: AgentOrchestrator, scenario_payload: dict[str, Any], gravity_g: float
) -> None:
    """FR-16: gravity neither 0 nor 1 repeats the gravity-bounding statement unchanged."""
    payload = scenario_payload | {
        "scenario": scenario_payload["scenario"] | {"gravity_g": gravity_g}
    }

    output = await orchestrator.run("scenario_interpreter", payload)

    assert any(
        scenario_payload["gravity_bounding"]["statement"] in text for text in all_text(output)
    )


async def test_flags_every_extrapolated_or_no_data_dimension(
    orchestrator: AgentOrchestrator, scenario_payload: dict[str, Any]
) -> None:
    """FR-07: every `extrapolated` or `no_data` dimension is flagged in the caveats."""
    flagged = [
        name
        for name, entry in scenario_payload["coverage"].items()
        if entry["state"] in FLAGGED_STATES
    ]

    output = await orchestrator.run("scenario_interpreter", scenario_payload)

    assert flagged
    for dimension in flagged:
        assert any(dimension in caveat for caveat in output.caveats), dimension


async def test_cited_fact_ids_were_supplied(
    orchestrator: AgentOrchestrator, scenario_payload: dict[str, Any]
) -> None:
    """FR-15: sentences cite only supplied fact IDs."""
    output = await orchestrator.run("scenario_interpreter", scenario_payload)
    supplied = {fact["id"] for fact in scenario_payload["facts"]}

    assert {fid for sentence in output.sentences for fid in sentence.fact_ids} <= supplied
