"""`ExtractorAgent` contract (document 07 section 3; FR-01, FR-15)."""

from __future__ import annotations

from typing import Any, get_args

import pytest

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import ValidationError
from flamescope_common.schemas.agents import ExtractorOutput
from flamescope_common.schemas.card import FireSafetyTag

pytestmark = pytest.mark.unit


def draft_sources(output: ExtractorOutput) -> list[Any]:
    sources = [item.source for item in output.objectives + output.measurements + output.findings]
    sources += [fuel.source for fuel in output.fuels]
    return sources + ([output.approach.source] if output.approach else [])


@pytest.mark.parametrize("missing", ["acronym", "title", "psi_url", "context"])
def test_input_requires_every_documented_field(
    orchestrator: AgentOrchestrator, extractor_payload: dict[str, Any], missing: str
) -> None:
    """FR-01: input `{acronym, title, psi_url, context:[{doc_id, title, section, text}]}`."""
    payload = {key: value for key, value in extractor_payload.items() if key != missing}

    with pytest.raises(ValidationError):
        orchestrator.run("extractor", payload)


def test_context_item_requires_doc_id_and_text(
    orchestrator: AgentOrchestrator, extractor_payload: dict[str, Any]
) -> None:
    """FR-01: each context item carries its document ID and text."""
    payload = extractor_payload | {"context": [{"title": "Overview"}]}

    with pytest.raises(ValidationError):
        orchestrator.run("extractor", payload)


async def test_mock_output_is_a_schema_valid_card_draft(
    orchestrator: AgentOrchestrator, extractor_payload: dict[str, Any]
) -> None:
    """NFR-02: `ExtractorOutput` in mock mode."""
    output = await orchestrator.run("extractor", extractor_payload)

    assert isinstance(output, ExtractorOutput)


async def test_draft_sources_cite_supplied_documents_verbatim(
    orchestrator: AgentOrchestrator, extractor_payload: dict[str, Any]
) -> None:
    """FR-15: every `DraftSource` names a supplied `doc_id` and quotes its text verbatim."""
    output = await orchestrator.run("extractor", extractor_payload)
    texts = {item["doc_id"]: item["text"] for item in extractor_payload["context"]}

    sources = draft_sources(output)
    assert sources
    for source in sources:
        assert source.doc_id in texts
        assert source.quote is None or source.quote in texts[source.doc_id]


async def test_tags_are_in_the_vocabulary(
    orchestrator: AgentOrchestrator, extractor_payload: dict[str, Any]
) -> None:
    """FR-01: tags come from the controlled vocabulary (document 04 section 5)."""
    output = await orchestrator.run("extractor", extractor_payload)

    assert set(output.fire_safety_tags) <= set(get_args(FireSafetyTag))


async def test_unstated_values_stay_null(orchestrator: AgentOrchestrator) -> None:
    """FR-01: context that states nothing yields nulls, never guesses."""
    payload = {
        "acronym": "TEST-0",
        "title": "Test",
        "psi_url": "https://psi.nasa.gov/test-0",
        "context": [{"doc_id": "doc-0", "title": "Empty", "text": ""}],
    }

    output = await orchestrator.run("extractor", payload)

    assert (output.platform, output.gravity_level, output.conditions) == (None, None, None)
    assert (output.fuels, output.findings) == ([], [])
