"""`ScorerAgent` contract (document 07 section 3; document 08 section 1; FR-03)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import ValidationError
from flamescope_common.schemas.agents import ScorerCriterionScore, ScorerEvidence, ScorerOutput

pytestmark = pytest.mark.unit

SCORE_MIN = 0
SCORE_MAX = 5


def test_lens_must_be_a_rubric_lens(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any]
) -> None:
    """FR-03: lenses are habitat, modeling, controls."""
    with pytest.raises(ValidationError):
        orchestrator.run("scorer", scorer_payload | {"lens": "cost"})


@pytest.mark.parametrize("missing", ["acronym", "lens", "criteria", "card"])
def test_input_requires_every_documented_field(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any], missing: str
) -> None:
    """FR-03: input `{acronym, lens, criteria, card, excerpts}`."""
    payload = {key: value for key, value in scorer_payload.items() if key != missing}

    with pytest.raises(ValidationError):
        orchestrator.run("scorer", payload)


async def test_mock_scores_every_criterion_of_the_lens(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any]
) -> None:
    """FR-03: one score per supplied criterion, same lens."""
    output = await orchestrator.run("scorer", scorer_payload)

    assert isinstance(output, ScorerOutput)
    assert output.lens == "habitat"
    assert [s.criterion for s in output.scores] == [c["id"] for c in scorer_payload["criteria"]]


async def test_values_are_null_or_between_zero_and_five(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any]
) -> None:
    """FR-03: each criterion is rated 0 to 5, or null when there is no evidence."""
    output = await orchestrator.run("scorer", scorer_payload)

    values = [score.value for score in output.scores]
    assert all(value is None or SCORE_MIN <= value <= SCORE_MAX for value in values)


async def test_non_null_value_carries_evidence(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any]
) -> None:
    """FR-03, FR-15: a non-null value requires at least one evidence item."""
    output = await orchestrator.run("scorer", scorer_payload)

    rated = [score for score in output.scores if score.value is not None]
    assert rated
    assert all(score.evidence for score in rated)


async def test_card_without_facts_scores_null(
    orchestrator: AgentOrchestrator, scorer_payload: dict[str, Any], empty_card: dict[str, Any]
) -> None:
    """FR-03: no evidence means null and empty evidence; unknown over a guess."""
    output = await orchestrator.run("scorer", scorer_payload | {"card": empty_card})

    assert {(score.value, len(score.evidence)) for score in output.scores} == {(None, 0)}


def test_schema_rejects_a_value_without_evidence() -> None:
    """FR-03: the rule is schema-enforced, so an LLM answer breaking it is retried."""
    with pytest.raises(PydanticValidationError):
        ScorerCriterionScore(criterion="fuel_realism", value=3)


@pytest.mark.parametrize("value", [-1, 6])
def test_schema_rejects_values_outside_zero_to_five(value: int) -> None:
    """FR-03: ratings are 0 to 5."""
    evidence = [ScorerEvidence(field_path="fuels", quote="test sheet")]

    with pytest.raises(PydanticValidationError):
        ScorerCriterionScore(criterion="fuel_realism", value=value, evidence=evidence)


def test_evidence_points_at_a_chunk_or_a_card_field() -> None:
    """FR-15: evidence is `{chunk_id|field_path, quote}`."""
    with pytest.raises(PydanticValidationError):
        ScorerEvidence(quote="floating quote")
