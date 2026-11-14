"""FR-11: reciprocal rank fusion, retrieval threshold and the refusal path (doc 05 s10)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest

from flamescope_agents.citation_verifier import CitationVerifier
from flamescope_api.services.insight import InsightService, fuse_ranks
from flamescope_common.config import get_settings
from flamescope_common.errors import LLMError
from flamescope_common.schemas.api import AskFilters, ChunkHit
from flamescope_common.sources import SourceRef

pytestmark = pytest.mark.unit

RRF_K = 60
REFUSAL = "The curated PSI corpus does not contain enough information to answer that."
REFUSAL_EVENT_ORDER = ["meta", "citations", "related", "done"]


def _hit(chunk_id: int, score: float = 1.0) -> ChunkHit:
    return ChunkHit(chunk_id=chunk_id, acronym="ALPHA", doc_title="doc", text="text", score=score)


def _ids(hits: list[ChunkHit]) -> list[int]:
    return [hit.chunk_id for hit in hits]


class TestFuseRanks:
    def test_fr11_reciprocal_rank_fusion_order(self) -> None:
        """FR-11: score = sum 1 / (60 + rank); hits in both lists rise to the top."""
        fused = fuse_ranks([_hit(1), _hit(2), _hit(3)], [_hit(3), _hit(1), _hit(4)])
        assert _ids(fused) == [1, 3, 2, 4]
        assert fused[0].score == pytest.approx(1 / (RRF_K + 1) + 1 / (RRF_K + 2))
        assert fused[1].score == pytest.approx(1 / (RRF_K + 3) + 1 / (RRF_K + 1))
        assert fused[3].score == pytest.approx(1 / (RRF_K + 3))

    def test_fr11_duplicates_are_merged(self) -> None:
        """FR-11: a chunk found by both retrievers appears once."""
        fused = fuse_ranks([_hit(7), _hit(8)], [_hit(8), _hit(7)])
        assert sorted(_ids(fused)) == [7, 8]

    def test_fr11_custom_constant(self) -> None:
        """FR-11: `k` is the fusion constant."""
        fused = fuse_ranks([_hit(1)], [], k=10)
        assert fused[0].score == pytest.approx(1 / 11)

    def test_fr11_single_list_keeps_its_order(self) -> None:
        """FR-11: with only keyword hits the order is the keyword order."""
        assert _ids(fuse_ranks([_hit(5), _hit(2), _hit(9)], [])) == [5, 2, 9]

    def test_fr11_no_hits(self) -> None:
        """FR-11: nothing in, nothing out."""
        assert fuse_ranks([], []) == []


class FakeChunkRepo:
    def __init__(self, keyword: list[ChunkHit], vector: list[ChunkHit]) -> None:
        self._keyword = keyword
        self._vector = vector

    def keyword_search(self, q: str, k: int, filters: Any = None) -> list[ChunkHit]:
        return self._keyword[:k]

    def vector_search(self, embedding: Any, k: int, filters: Any = None) -> list[ChunkHit]:
        return self._vector[:k]


class FakeGateway:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeInvestigationRepo:
    def findings(self, category: Any, acronyms: Any = None) -> list[Any]:
        return []


class StreamingOrchestrator:
    """Streams fixed deltas, like `run(..., stream=True)`; an `LLMError` delta is raised."""

    def __init__(self, deltas: Sequence[str | LLMError]) -> None:
        self._deltas = deltas

    def run(self, name: str, payload: Any, *, stream: bool = False) -> AsyncIterator[str]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[str]:
        for delta in self._deltas:
            if isinstance(delta, LLMError):
                raise delta
            yield delta


def _service(
    keyword: list[ChunkHit], vector: list[ChunkHit], deltas: Sequence[str | LLMError] | None = None
) -> InsightService:
    return InsightService(
        FakeChunkRepo(keyword, vector),  # type: ignore[arg-type]
        FakeInvestigationRepo(),  # type: ignore[arg-type]
        StreamingOrchestrator(deltas or []),  # type: ignore[arg-type]
        CitationVerifier(),
        FakeGateway(),  # type: ignore[arg-type]
    )


def _parse(frames: list[str]) -> list[tuple[str, dict[str, Any]]]:
    parsed = []
    for frame in frames:
        event_line, data_line = frame.strip().split("\n")
        event = event_line.removeprefix("event: ")
        parsed.append((event, json.loads(data_line.removeprefix("data: "))))
    return parsed


async def _events(service: InsightService, top_k: int = 8) -> list[tuple[str, dict[str, Any]]]:
    return _parse([frame async for frame in service.ask("question?", AskFilters(), top_k)])


def _retrieved_ids(events: list[tuple[str, dict[str, Any]]]) -> list[int]:
    return [item["chunk_id"] for item in events[0][1]["retrieved"]]


def _cited_chunk() -> ChunkHit:
    return ChunkHit(
        chunk_id=1,
        acronym="ALPHA",
        doc_title="doc",
        text="Flames spread along the sample at 2 mm/s in the test duct.",
        score=1.0,
        # ChunkRepo stamps the chunk ID onto the source (repositories/chunks.py).
        source=SourceRef(kind="document", uri="https://psi.nasa.gov/test", chunk_id=1),
    )


class TestRetrieval:
    async def test_fr11_nothing_retrieved_returns_fixed_sentence(self) -> None:
        """FR-11: no retrieval hit -> fixed sentence, no citations, events in order."""
        events = await _events(_service([], []))
        assert [name for name, _ in events] == REFUSAL_EVENT_ORDER
        sentences = events[1][1]["sentences"]
        assert [sentence["text"] for sentence in sentences] == [REFUSAL]
        assert sentences[0]["citations"] == []
        assert events[-1][1] == {"status": "ok"}

    async def test_fr11_vector_hits_below_0_2_are_ignored(self) -> None:
        """FR-11: a vector hit counts only with cosine similarity >= 0.2."""
        events = await _events(_service([], [_hit(1, score=0.19)]))
        assert _retrieved_ids(events) == []
        assert [name for name, _ in events] == REFUSAL_EVENT_ORDER

    @pytest.mark.parametrize(("provider", "kept"), [("mock", [1]), ("ollama", [])])
    async def test_fr11_vector_threshold_follows_embed_provider(
        self, monkeypatch: pytest.MonkeyPatch, provider: str, kept: list[int]
    ) -> None:
        """FR-11, doc 05 s10: cosine floor 0.2 for mock, 0.5 for ollama (`nomic-embed-text`)."""
        monkeypatch.setenv("EMBED_PROVIDER", provider)
        get_settings.cache_clear()
        events = await _events(_service([], [_hit(1, score=0.45)]))
        assert _retrieved_ids(events) == kept

    async def test_fr11_retrieval_keeps_best_top_k(self) -> None:
        """FR-11: fused hits are truncated to `top_k`; vector hits >= 0.2 count."""
        service = _service([_hit(1), _hit(2), _hit(3)], [_hit(3, score=0.2), _hit(4, score=0.9)])
        events = await _events(service, top_k=2)
        assert _retrieved_ids(events) == [3, 1]

    async def test_fr11_answer_events_in_documented_order(self) -> None:
        """FR-11: meta, token+, citations, related, done; verified sentence keeps its source."""
        chunk = ChunkHit(
            chunk_id=1,
            acronym="ALPHA",
            doc_title="doc",
            text="Flames spread along the sample at 2 mm/s in the test duct.",
            score=1.0,
            # ChunkRepo stamps the chunk ID onto the source (repositories/chunks.py).
            source=SourceRef(kind="document", uri="https://psi.nasa.gov/test", chunk_id=1),
        )
        deltas = ["Flames spread along the sample ", "at 2 mm/s [c:1]."]
        events = await _events(_service([chunk], [], deltas))
        names = [name for name, _ in events]
        assert names == ["meta", "token", "token", "citations", "related", "done"]
        sentences = events[3][1]["sentences"]
        assert len(sentences) == 1
        assert sentences[0]["citations"][0]["uri"] == "https://psi.nasa.gov/test"
        assert events[4][1] == {"investigations": ["ALPHA"]}

    async def test_fr11_llm_failure_ends_with_error_event(self) -> None:
        """FR-11: an LLM failure ends the stream with the terminal `error` event."""
        service = _service([_cited_chunk()], [], ["Partial ", LLMError("provider down")])
        events = await _events(service)
        assert [name for name, _ in events] == ["meta", "token", "error"]
        assert events[-1][1]["code"] == "llm_unavailable"
