"""`InsightService`: cited question answering over hybrid retrieval (document 09 CF-09)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence

import structlog

from flamescope_agents.citation_verifier import CitationVerifier, ContextEntry
from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_api.repositories.chunks import ChunkRepo
from flamescope_api.repositories.investigations import InvestigationRepo
from flamescope_api.sse import sse_event
from flamescope_common.config import ProviderName, get_settings
from flamescope_common.errors import FlameScopeError, LLMError
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.logging import get_request_id
from flamescope_common.schemas.agents import (
    INSUFFICIENT_INFORMATION_SENTENCE,
    InsightQAInput,
    QACardFact,
    QAChunk,
)
from flamescope_common.schemas.api import (
    DEFAULT_ASK_TOP_K,
    AskCitations,
    AskDone,
    AskError,
    AskFilters,
    AskMeta,
    AskRelated,
    AskToken,
    ChunkHit,
    RetrievedChunk,
    VerifiedSentence,
)
from flamescope_common.sources import SourceRef

logger = structlog.get_logger(__name__)

RRF_CONSTANT = 60
CANDIDATE_POOL_FACTOR = 3
# Cosine floor per embedding provider (doc 05 s10): the mock hashes content words; the ollama
# value is calibrated for `nomic-embed-text`, where off-corpus questions score up to ~0.47.
MIN_VECTOR_SIMILARITY: dict[ProviderName, float] = {"mock": 0.2, "ollama": 0.5}
FACTS_PER_INVESTIGATION = 3
INTERNAL_ERROR_MESSAGE = "The answer could not be produced."


def fuse_ranks(
    keyword_hits: Sequence[ChunkHit], vector_hits: Sequence[ChunkHit], k: int = RRF_CONSTANT
) -> list[ChunkHit]:
    """Reciprocal rank fusion: score = sum over lists of 1 / (k + rank), ranks start at 1."""
    scores: dict[int, float] = {}
    hits: dict[int, ChunkHit] = {}
    for ranked in (keyword_hits, vector_hits):
        for rank, hit in enumerate(ranked, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            hits.setdefault(hit.chunk_id, hit)
    order = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    return [hits[chunk_id].model_copy(update={"score": scores[chunk_id]}) for chunk_id in order]


def _related(sentences: Sequence[VerifiedSentence], acronyms: Mapping[int, str]) -> list[str]:
    cited = (
        acronyms[citation.chunk_id]
        for sentence in sentences
        for citation in sentence.citations
        if citation.chunk_id is not None and citation.chunk_id in acronyms
    )
    return list(dict.fromkeys(cited))


def _refusal_events() -> list[str]:
    fixed = VerifiedSentence(text=INSUFFICIENT_INFORMATION_SENTENCE, supported=True)
    return [
        sse_event("citations", AskCitations(sentences=[fixed], dropped=0)),
        sse_event("related", AskRelated()),
        sse_event("done", AskDone()),
    ]


class InsightService:
    """Retrieve, stream a cited answer, verify it; the answer is the only LLM completion."""

    def __init__(
        self,
        chunks: ChunkRepo,
        investigations: InvestigationRepo,
        orchestrator: AgentOrchestrator,
        verifier: CitationVerifier,
        gateway: LLMGateway,
    ) -> None:
        self._chunks = chunks
        self._investigations = investigations
        self._orchestrator = orchestrator
        self._verifier = verifier
        self._gateway = gateway

    async def ask(
        self, question: str, filters: AskFilters, top_k: int = DEFAULT_ASK_TOP_K
    ) -> AsyncIterator[str]:
        """SSE frames in the order meta, token*, citations, related, done (or error)."""
        try:
            async for frame in self._answer(question, filters, top_k):
                yield frame
        except LLMError as error:
            logger.warning("ask_llm_unavailable", error=error.message)
            yield sse_event("error", AskError(code=error.code, message=error.message))
        except FlameScopeError as error:
            yield sse_event("error", AskError(code=error.code, message=error.message))
        except Exception:
            logger.exception("ask_failed")
            yield sse_event(
                "error", AskError(code="internal_error", message=INTERNAL_ERROR_MESSAGE)
            )

    async def _answer(self, question: str, filters: AskFilters, top_k: int) -> AsyncIterator[str]:
        hits = await asyncio.to_thread(self._retrieve, question, filters, top_k)
        retrieved = [
            RetrievedChunk(
                chunk_id=hit.chunk_id,
                acronym=hit.acronym,
                doc_title=hit.doc_title,
                score=hit.score,
            )
            for hit in hits
        ]
        yield sse_event("meta", AskMeta(request_id=get_request_id(), retrieved=retrieved))
        if not hits:
            for frame in _refusal_events():
                yield frame
            return
        facts = await asyncio.to_thread(self._card_facts, sorted({hit.acronym for hit in hits}))
        payload = InsightQAInput(
            question=question,
            chunks=[
                QAChunk(chunk_id=h.chunk_id, acronym=h.acronym, doc_title=h.doc_title, text=h.text)
                for h in hits
            ],
            card_facts=[
                QACardFact(id=f_id, acronym=acronym, text=entry.text)
                for f_id, acronym, entry in facts
            ],
        )
        draft = ""
        async for delta in self._orchestrator.run("insight_qa", payload, stream=True):
            draft += delta
            yield sse_event("token", AskToken(text=delta))
        context = self._context(hits, facts)
        verified = self._verifier.verify(draft, context)
        yield sse_event(
            "citations", AskCitations(sentences=verified.sentences, dropped=verified.dropped)
        )
        acronyms = {hit.chunk_id: hit.acronym for hit in hits}
        yield sse_event(
            "related", AskRelated(investigations=_related(verified.sentences, acronyms))
        )
        yield sse_event("done", AskDone())

    def _retrieve(self, question: str, filters: AskFilters, top_k: int) -> list[ChunkHit]:
        pool = top_k * CANDIDATE_POOL_FACTOR
        keyword_hits = self._chunks.keyword_search(question, pool, filters)
        vector_hits = self._vector_hits(question, pool, filters)
        return fuse_ranks(keyword_hits, vector_hits)[:top_k]

    def _vector_hits(self, question: str, pool: int, filters: AskFilters) -> list[ChunkHit]:
        try:
            embedding = self._gateway.embed([question])[0]
        except LLMError as error:
            logger.warning("ask_embedding_unavailable", error=error.message)
            return []
        hits = self._chunks.vector_search(embedding, pool, filters)
        threshold = MIN_VECTOR_SIMILARITY[get_settings().embed_provider_name]
        return [hit for hit in hits if hit.score >= threshold]

    def _card_facts(self, acronyms: Sequence[str]) -> list[tuple[int, str, ContextEntry]]:
        per_investigation: dict[str, int] = {}
        facts: list[tuple[int, str, ContextEntry]] = []
        for row in self._investigations.findings(None, acronyms):
            taken = per_investigation.get(row.acronym, 0)
            if taken >= FACTS_PER_INVESTIGATION:
                continue
            per_investigation[row.acronym] = taken + 1
            source = SourceRef.model_validate(row.finding.source)
            facts.append(
                (row.finding.id, row.acronym, ContextEntry(row.finding.statement, source))
            )
        return facts

    @staticmethod
    def _context(
        hits: Sequence[ChunkHit], facts: Sequence[tuple[int, str, ContextEntry]]
    ) -> dict[str, ContextEntry]:
        context = {
            f"c:{hit.chunk_id}": ContextEntry(hit.text, hit.source)
            for hit in hits
            if hit.source is not None
        }
        context.update({f"f:{fact_id}": entry for fact_id, _acronym, entry in facts})
        return context
