"""`ChunkRepo`: keyword and vector retrieval over document chunks."""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, func, literal, select
from sqlalchemy.orm import Session

from flamescope_api.repositories import ENGLISH_TS_CONFIG
from flamescope_common.models import Chunk, Investigation
from flamescope_common.schemas.api import AskFilters, ChunkHit
from flamescope_common.sources import SourceRef

QUERY_TERM = re.compile(r"[A-Za-z0-9]+")
MIN_QUERY_TERM_LENGTH = 3


def or_query(text: str) -> str | None:
    """`a | b | c` tsquery text from free text; only alphanumerics survive (no operators)."""
    terms = dict.fromkeys(
        term.lower() for term in QUERY_TERM.findall(text) if len(term) >= MIN_QUERY_TERM_LENGTH
    )
    return " | ".join(terms) or None


def _investigation_clauses(filters: AskFilters | None) -> list[ColumnElement[bool]]:
    if filters is None or not filters.investigations:
        return []
    return [
        func.lower(Investigation.acronym).in_([name.lower() for name in filters.investigations])
    ]


class ChunkRepo:
    """Read access to `chunk` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def keyword_search(self, q: str, k: int, filters: AskFilters | None = None) -> list[ChunkHit]:
        """Top `k` chunks by full-text rank (any query term matches)."""
        query_text = or_query(q)
        if query_text is None:
            return []
        tsquery = func.to_tsquery(ENGLISH_TS_CONFIG, query_text)
        rank = func.ts_rank_cd(Chunk.tsv, tsquery)
        statement = self._base(rank).where(
            Chunk.tsv.op("@@")(tsquery), *_investigation_clauses(filters)
        )
        return self._hits(statement.order_by(rank.desc(), Chunk.id).limit(k))

    def vector_search(
        self, embedding: Sequence[float], k: int, filters: AskFilters | None = None
    ) -> list[ChunkHit]:
        """Top `k` chunks by cosine similarity (score = 1 - cosine distance)."""
        distance = Chunk.embedding.cosine_distance(list(embedding))
        statement = self._base(1 - distance).where(
            Chunk.embedding.is_not(None), *_investigation_clauses(filters)
        )
        return self._hits(statement.order_by(distance, Chunk.id).limit(k))

    def by_ids(self, ids: Sequence[int]) -> list[ChunkHit]:
        if not ids:
            return []
        statement = self._base(literal(0.0)).where(Chunk.id.in_(ids))
        return self._hits(statement.order_by(Chunk.id))

    def _base(self, score: ColumnElement[float]) -> Select[Chunk, str, float]:
        return select(Chunk, Investigation.acronym, score).join(
            Investigation, Investigation.id == Chunk.investigation_id
        )

    def _hits(self, statement: Select[Chunk, str, float]) -> list[ChunkHit]:
        return [
            ChunkHit(
                chunk_id=chunk.id,
                acronym=acronym,
                doc_title=chunk.doc_title,
                text=chunk.text,
                score=float(score),
                source=_chunk_source(chunk),
            )
            for chunk, acronym, score in self._session.execute(statement)
        ]


def _chunk_source(chunk: Chunk) -> SourceRef:
    source = SourceRef.model_validate(chunk.source)
    return source.model_copy(update={"chunk_id": chunk.id})
