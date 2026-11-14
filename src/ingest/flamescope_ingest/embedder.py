"""Stage 8, index: chunking and embeddings (document 06 section 3.8)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from flamescope_common.errors import IngestError
from flamescope_common.schemas.card import SeedInvestigation
from flamescope_common.sources import SourceRef
from flamescope_ingest.parser import ParsedDoc

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
BOUNDARY_SEARCH_FRACTION = 0.8
SECTION_GAP = 2
ChunkKey = tuple[str, int, int]


class TextEmbedder(Protocol):
    """The slice of `LLMGateway` the index stage needs."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChunkDraft(BaseModel):
    """One `chunk` row; `embedding` is None when the stored vector is still valid."""

    doc_ref: str
    doc_title: str
    section: str | None = None
    char_start: int
    char_end: int
    text: str
    source: SourceRef
    embedding: list[float] | None = None

    @property
    def key(self) -> ChunkKey:
        return (self.doc_ref, self.char_start, self.char_end)


@dataclass(frozen=True)
class IndexSection:
    """A span of document text with its provenance; offsets are positions in the document."""

    doc_ref: str
    doc_title: str
    heading: str | None
    text: str
    char_start: int
    source: SourceRef


def _soft_boundary(text: str, start: int, end: int, size: int) -> int:
    """Prefer ending a chunk after a space in the last fifth of the window."""
    floor = start + int(size * BOUNDARY_SEARCH_FRACTION)
    cut = text.rfind(" ", floor, end)
    return cut + 1 if cut != -1 else end


def chunk_spans(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[tuple[int, int]]:
    """Character spans of at most `size` characters that overlap by about `overlap`."""
    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            end = _soft_boundary(text, start, end, size)
        if text[start:end].strip():
            spans.append((start, end))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return spans


def chunk_section(section: IndexSection) -> list[ChunkDraft]:
    return [
        ChunkDraft(
            doc_ref=section.doc_ref,
            doc_title=section.doc_title,
            section=section.heading,
            char_start=section.char_start + start,
            char_end=section.char_start + end,
            text=section.text[start:end],
            source=section.source,
        )
        for start, end in chunk_spans(section.text)
    ]


def seed_sections(record: SeedInvestigation) -> list[IndexSection]:
    """Summary, objectives, approach, findings and `documents:` text of a seed record."""
    page = SourceRef(kind="psi_page", uri=record.psi_url, title=record.title)
    titled: list[tuple[str, str, SourceRef]] = []
    if record.summary:
        titled.append(("Summary", record.summary, page))
    titled += [(f"Objective {i}", o.text, o.source) for i, o in enumerate(record.objectives, 1)]
    if record.approach:
        titled.append(("Approach", record.approach.text, record.approach.source))
    titled += [(f"Finding {i}", f.statement, f.source) for i, f in enumerate(record.findings, 1)]
    sections = _lay_out(record.psi_url, f"{record.acronym} card", titled)
    for document in record.documents:
        source = SourceRef(kind="document", uri=document.uri, title=document.title)
        sections.append(
            IndexSection(document.uri, document.title, document.section, document.text, 0, source)
        )
    return sections


def _lay_out(
    doc_ref: str, doc_title: str, parts: Iterable[tuple[str, str, SourceRef]]
) -> list[IndexSection]:
    """Place parts one after another in a pseudo-document so chunk offsets stay unique."""
    sections: list[IndexSection] = []
    offset = 0
    for heading, text, source in parts:
        sections.append(IndexSection(doc_ref, doc_title, heading, text, offset, source))
        offset += len(text) + SECTION_GAP
    return sections


def parsed_sections(documents: Iterable[ParsedDoc]) -> list[IndexSection]:
    sections: list[IndexSection] = []
    for document in documents:
        source = SourceRef(kind="s3_object", uri=document.doc_ref, title=document.title)
        sections += [
            IndexSection(
                document.doc_ref, document.title, part.heading, part.text, part.char_start, source
            )
            for part in document.sections
        ]
    return sections


class Embedder:
    """Builds chunk drafts and embeds only those whose stored vector is stale."""

    def __init__(self, gateway: TextEmbedder) -> None:
        self._gateway = gateway

    def build_chunks(self, sections: Iterable[IndexSection]) -> list[ChunkDraft]:
        return [chunk for section in sections for chunk in chunk_section(section)]

    def embed_stale(
        self,
        drafts: Sequence[ChunkDraft],
        embedded: Mapping[ChunkKey, str],
        *,
        force: bool = False,
    ) -> list[ChunkDraft]:
        """Chunks already embedded with the same text keep `embedding=None` (nothing to write)."""
        stale = [d for d in drafts if force or embedded.get(d.key) != d.text]
        vectors = self._gateway.embed([draft.text for draft in stale]) if stale else []
        if len(vectors) != len(stale):
            raise IngestError(
                "Embedding count does not match chunk count",
                {"chunks": len(stale), "vectors": len(vectors)},
            )
        by_key = {draft.key: vector for draft, vector in zip(stale, vectors, strict=True)}
        return [d.model_copy(update={"embedding": by_key.get(d.key)}) for d in drafts]
