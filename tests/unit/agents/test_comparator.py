"""`ComparatorAgent` contract (document 07 section 3; FR-05)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import ValidationError
from flamescope_common.schemas.agents import ComparatorOutput, SentenceWithFacts

pytestmark = pytest.mark.unit

MIN_SENTENCES = 4
MAX_SENTENCES = 7


@pytest.mark.parametrize("missing", ["investigations", "matrix", "shared", "facts"])
def test_input_requires_every_documented_field(
    orchestrator: AgentOrchestrator, comparator_payload: dict[str, Any], missing: str
) -> None:
    """FR-05: input `{investigations, matrix, shared, facts}`."""
    payload = {key: value for key, value in comparator_payload.items() if key != missing}

    with pytest.raises(ValidationError):
        orchestrator.run("comparator", payload)


def test_fact_requires_a_source(
    orchestrator: AgentOrchestrator, comparator_payload: dict[str, Any]
) -> None:
    """FR-15: facts are `{id, text, source}`."""
    payload = comparator_payload | {"facts": [{"id": "f1", "text": "Unsourced."}]}

    with pytest.raises(ValidationError):
        orchestrator.run("comparator", payload)


async def test_mock_narrative_has_four_to_seven_sentences(
    orchestrator: AgentOrchestrator, comparator_payload: dict[str, Any]
) -> None:
    """FR-05: 4 to 7 sentences in mock mode."""
    output = await orchestrator.run("comparator", comparator_payload)

    assert isinstance(output, ComparatorOutput)
    assert MIN_SENTENCES <= len(output.sentences) <= MAX_SENTENCES


async def test_cited_fact_ids_were_supplied(
    orchestrator: AgentOrchestrator, comparator_payload: dict[str, Any]
) -> None:
    """FR-05, FR-15: sentences cite only supplied fact IDs."""
    output = await orchestrator.run("comparator", comparator_payload)
    supplied = {fact["id"] for fact in comparator_payload["facts"]}

    cited = {fact_id for sentence in output.sentences for fact_id in sentence.fact_ids}
    assert cited
    assert cited <= supplied


@pytest.mark.parametrize("count", [MIN_SENTENCES - 1, MAX_SENTENCES + 1])
def test_sentence_count_is_schema_enforced(count: int) -> None:
    """FR-05: a shorter or longer answer fails validation (and is retried)."""
    sentences = [SentenceWithFacts(text=f"Sentence {index}.") for index in range(count)]

    with pytest.raises(PydanticValidationError):
        ComparatorOutput(sentences=sentences)
