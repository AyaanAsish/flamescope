"""`InsightQAAgent` contract (document 07 section 3; document 05 section 10; FR-11)."""

from __future__ import annotations

import re
from typing import Any

import pytest

from flamescope_agents.citation_verifier import split_sentences
from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import ValidationError

pytestmark = pytest.mark.unit

REFUSAL = "The curated PSI corpus does not contain enough information to answer that."
TRAILING_MARKERS = re.compile(r"(?:\s*\[[cf]:\d+\])+\s*$")
MARKER = re.compile(r"\[([cf]):(\d+)\]")


def supplied_markers(payload: dict[str, Any]) -> set[tuple[str, str]]:
    chunks = {("c", str(chunk["chunk_id"])) for chunk in payload["chunks"]}
    return chunks | {("f", str(card_fact["id"])) for card_fact in payload["card_facts"]}


def test_question_is_required(orchestrator: AgentOrchestrator) -> None:
    """FR-11: input `{question, chunks, card_facts}`."""
    with pytest.raises(ValidationError):
        orchestrator.run("insight_qa", {"chunks": []})


def test_chunk_requires_its_id(
    orchestrator: AgentOrchestrator, insight_payload: dict[str, Any]
) -> None:
    """FR-11: chunks are `{chunk_id, acronym, doc_title, text}`."""
    payload = insight_payload | {"chunks": [{"acronym": "TEST-1", "doc_title": "D", "text": "x"}]}

    with pytest.raises(ValidationError):
        orchestrator.run("insight_qa", payload)


async def test_every_sentence_ends_with_a_citation_marker(
    orchestrator: AgentOrchestrator, insight_payload: dict[str, Any]
) -> None:
    """FR-11: each sentence ends with one or more `[c:ID]` / `[f:ID]` markers."""
    answer = await orchestrator.run("insight_qa", insight_payload)

    sentences = split_sentences(answer)
    assert sentences
    assert all(TRAILING_MARKERS.search(sentence) for sentence in sentences)


async def test_markers_cite_only_supplied_context(
    orchestrator: AgentOrchestrator, insight_payload: dict[str, Any]
) -> None:
    """FR-11, FR-15: markers reference supplied chunk and card-fact IDs only."""
    answer = await orchestrator.run("insight_qa", insight_payload)

    assert set(MARKER.findall(answer)) <= supplied_markers(insight_payload)


async def test_answer_has_no_markdown_headings(
    orchestrator: AgentOrchestrator, insight_payload: dict[str, Any]
) -> None:
    """FR-11: plain sentences, no Markdown headings."""
    answer = await orchestrator.run("insight_qa", insight_payload)

    assert not any(line.lstrip().startswith("#") for line in answer.splitlines())


async def test_insufficient_context_gives_the_fixed_sentence(
    orchestrator: AgentOrchestrator,
) -> None:
    """FR-11: refusal is exactly the fixed sentence of document 05 section 10."""
    answer = await orchestrator.run("insight_qa", {"question": "What is outside the corpus?"})

    assert answer == REFUSAL


async def test_streamed_answer_matches_the_full_answer(
    orchestrator: AgentOrchestrator, insight_payload: dict[str, Any]
) -> None:
    """FR-11: the streamed deltas form the same cited answer."""
    deltas = [
        delta async for delta in orchestrator.run("insight_qa", insight_payload, stream=True)
    ]

    assert "".join(deltas) == await orchestrator.run("insight_qa", insight_payload)
