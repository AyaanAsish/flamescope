"""FR-11: stage 8, index (document 06 sections 2 and 3.8; document 04 table `chunk`).

Chunk size 1000 characters, overlap 150, split on section boundaries first; chunk text 800 to
1200 characters; chunk key `(doc_ref, char_start, char_end)` plus text decides re-embedding.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

import pytest

from flamescope_common.errors import IngestError
from flamescope_common.schemas.card import SeedInvestigation
from flamescope_common.sources import SourceRef
from flamescope_ingest.embedder import (
    ChunkDraft,
    Embedder,
    IndexSection,
    chunk_section,
    chunk_spans,
    parsed_sections,
    seed_sections,
)
from flamescope_ingest.parser import ParsedDoc, ParsedSection

pytestmark = pytest.mark.unit

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 800
SOURCE = SourceRef(kind="s3_object", uri="s3://nasa-psi/combustion/TEST-1/report.pdf")
WORD = "flame "


def _prose(characters: int) -> str:
    return (WORD * (characters // len(WORD) + 1))[:characters]


def _section(text: str, heading: str = "Results", start: int = 0) -> IndexSection:
    return IndexSection(SOURCE.uri, "Report", heading, text, start, SOURCE)


class FakeEmbedder:
    """Counts texts sent for embedding; vectors are fixed and synthetic."""

    def __init__(self, short_by: int = 0) -> None:
        self.calls: list[list[str]] = []
        self._short_by = short_by

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0, 0.0] for _ in texts[self._short_by :]]


def test_short_text_is_one_chunk() -> None:
    assert chunk_spans("short text") == [(0, len("short text"))]


def test_empty_text_has_no_chunk() -> None:
    assert chunk_spans("") == []
    assert chunk_spans("   ") == []


def test_chunks_are_at_most_1000_characters() -> None:
    spans = chunk_spans(_prose(5000))
    assert all(end - start <= CHUNK_SIZE for start, end in spans)


def test_consecutive_chunks_overlap_by_150() -> None:
    spans = chunk_spans(_prose(5000))
    for (_, previous_end), (next_start, _) in itertools.pairwise(spans):
        assert previous_end - next_start == CHUNK_OVERLAP


def test_chunks_cover_the_whole_text() -> None:
    text = _prose(4321)
    spans = chunk_spans(text)
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    covered = {index for start, end in spans for index in range(start, end)}
    assert covered == set(range(len(text)))


def test_non_final_chunks_hold_at_least_800_characters() -> None:
    """Document 04 table `chunk`: text of 800 to 1200 characters."""
    spans = chunk_spans(_prose(5000))
    assert all(end - start >= MIN_CHUNK_CHARS for start, end in spans[:-1])


def test_text_without_spaces_still_chunks_at_1000() -> None:
    spans = chunk_spans("x" * 2500)
    assert spans[0] == (0, CHUNK_SIZE)
    assert spans[1][0] == CHUNK_SIZE - CHUNK_OVERLAP


def test_chunks_never_cross_section_boundaries() -> None:
    """Split on section boundaries first (document 06 section 3.8)."""
    first = _section(_prose(1500), heading="Intro", start=0)
    second = _section(_prose(300), heading="Method", start=1502)
    chunks = Embedder(FakeEmbedder()).build_chunks([first, second])
    for chunk in chunks:
        owner = first if chunk.section == "Intro" else second
        assert owner.char_start <= chunk.char_start < chunk.char_end
        assert chunk.char_end <= owner.char_start + len(owner.text)
    assert [chunk.section for chunk in chunks].count("Method") == 1


def test_chunk_offsets_and_text_come_from_the_section() -> None:
    section = _section(_prose(1800), start=500)
    for chunk in chunk_section(section):
        local = slice(chunk.char_start - section.char_start, chunk.char_end - section.char_start)
        assert chunk.text == section.text[local]
        assert chunk.source == SOURCE
        assert chunk.key == (SOURCE.uri, chunk.char_start, chunk.char_end)


def test_parsed_sections_keep_document_offsets() -> None:
    document = ParsedDoc(
        doc_ref=SOURCE.uri,
        title="Report",
        kind="pdf",
        sections=[
            ParsedSection(heading="Page 1", text="aaa", char_start=0, char_end=3, page=1),
            ParsedSection(heading="Page 2", text="bbb", char_start=5, char_end=8, page=2),
        ],
    )
    sections = parsed_sections([document])
    assert [(s.heading, s.char_start) for s in sections] == [("Page 1", 0), ("Page 2", 5)]
    assert all(s.source.uri == SOURCE.uri for s in sections)


def test_seed_sections_order_and_offsets(make_card: Callable[..., dict[str, Any]]) -> None:
    """Seed mode: summary, objectives, approach, findings and `documents:` text (doc 06 s3.8)."""
    source = SOURCE.model_dump(exclude_none=True)
    record = SeedInvestigation.model_validate(
        make_card(
            summary="Synthetic summary.",
            approach={"text": "Synthetic approach.", "source": source},
            findings=[
                {
                    "statement": "Synthetic finding.",
                    "category": "fundamental",
                    "source": source,
                    "confidence": 0.5,
                }
            ],
            documents=[{"title": "Doc", "uri": "https://doi.org/10.0/test", "text": "Doc text."}],
        )
    )
    sections = seed_sections(record)
    assert [section.text for section in sections] == [
        "Synthetic summary.",
        "Synthetic objective.",
        "Synthetic approach.",
        "Synthetic finding.",
        "Doc text.",
    ]
    card_sections = sections[:-1]
    keys = [(s.doc_ref, s.char_start, s.char_start + len(s.text)) for s in card_sections]
    assert len(set(keys)) == len(keys), "chunk keys stay unique inside the card pseudo-document"


def test_embed_stale_skips_chunks_already_embedded() -> None:
    """Idempotency: chunk key plus text for rows that already have an embedding (doc 06 s2)."""
    gateway = FakeEmbedder()
    embedder = Embedder(gateway)
    drafts = embedder.build_chunks([_section("first section"), _section("second", start=100)])
    embedded = {drafts[0].key: drafts[0].text}
    result = embedder.embed_stale(drafts, embedded)
    assert result[0].embedding is None
    assert result[1].embedding == [1.0, 0.0]
    assert gateway.calls == [["second"]]


def test_embed_stale_reembeds_changed_text() -> None:
    gateway = FakeEmbedder()
    drafts = Embedder(gateway).build_chunks([_section("new text")])
    Embedder(gateway).embed_stale(drafts, {drafts[0].key: "old text"})
    assert gateway.calls == [["new text"]]


def test_force_reembeds_every_chunk() -> None:
    """`index --force` after an `EMBED_MODEL` change re-embeds every chunk (doc 06 s2)."""
    gateway = FakeEmbedder()
    embedder = Embedder(gateway)
    drafts = embedder.build_chunks([_section("one"), _section("two", start=10)])
    embedded = {draft.key: draft.text for draft in drafts}
    result = embedder.embed_stale(drafts, embedded, force=True)
    assert all(draft.embedding is not None for draft in result)


def test_nothing_stale_makes_no_embedding_call() -> None:
    gateway = FakeEmbedder()
    embedder = Embedder(gateway)
    drafts = embedder.build_chunks([_section("same")])
    embedder.embed_stale(drafts, {drafts[0].key: "same"})
    assert gateway.calls == []


def test_embedding_count_mismatch_is_an_ingest_error() -> None:
    embedder = Embedder(FakeEmbedder(short_by=1))
    drafts: list[ChunkDraft] = embedder.build_chunks([_section("a"), _section("b", start=5)])
    with pytest.raises(IngestError):
        embedder.embed_stale(drafts, {})
