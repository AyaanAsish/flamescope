"""Ask over SSE (document 12 section 2; document 05 section 10; document 07 section 4).

Requirements: FR-11 (streamed, cited answers; unsupported claims removed), FR-15 (citations
resolve to chunks), NFR-11 (request ID propagated). Call flow: CF-09 (Ask: retrieval,
streamed insight-QA completion, citation verifier).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(17)]

Rows = Callable[..., list[dict[str, Any]]]
FIXED_SENTENCE = "The curated PSI corpus does not contain enough information to answer that."
# Shares only function words with the corpus; the mock embedding ignores them (doc 07 s6), so
# no keyword match and no vector hit reaches the threshold (doc 05 s10).
OUT_OF_CORPUS_QUESTION = "What is the capital of France?"
REQUEST_ID = "it-ask-0017"
STREAM_TIMEOUT_S = 60.0
FINAL_EVENTS = ["citations", "related", "done"]


def _ask(
    api: httpx.Client, body: dict[str, Any], headers: dict[str, str] | None = None
) -> httpx.Response:
    with api.stream(
        "POST", "/ask", json=body, headers=headers or {}, timeout=STREAM_TIMEOUT_S
    ) as response:
        response.read()
        return response


@pytest.fixture(scope="module")
def corpus_question(hardware_file: dict[str, Any], seed_records: dict[str, dict[str, Any]]) -> str:
    """A question naming the facility most seed investigations use (doc 01 s6 hardware)."""
    used = [
        item["name"] for record in seed_records.values() for item in record.get("hardware") or []
    ]
    facilities = [
        item
        for item in hardware_file["hardware"]
        if item["kind"] == "facility" and item["name"] in used
    ]
    facility = max(facilities, key=lambda item: used.count(item["name"]))
    return f"Which experiments used the {facility['description'].rstrip('.')}?"


@pytest.fixture(scope="module")
def answered(
    stack: str, corpus_question: str, sse_events: Callable[[str], list[Any]]
) -> tuple[httpx.Response, list[Any]]:
    with httpx.Client(base_url=stack) as client:
        response = _ask(client, {"question": corpus_question}, {"X-Request-ID": REQUEST_ID})
    return response, sse_events(response.text)


def test_fr11_event_order(answered: tuple[httpx.Response, list[Any]]) -> None:
    """FR-11, doc 05 s10: `meta`, one or more `token`, then `citations`, `related`, `done`."""
    response, events = answered
    assert response.status_code == httpx.codes.OK
    assert response.headers["content-type"].startswith("text/event-stream")
    names = [event.event for event in events]
    tokens = names[1 : -len(FINAL_EVENTS)]
    assert names[0] == "meta"
    assert tokens and set(tokens) == {"token"}
    assert names[-len(FINAL_EVENTS) :] == FINAL_EVENTS


def test_nfr11_request_id_echoed(answered: tuple[httpx.Response, list[Any]]) -> None:
    """NFR-11: the supplied `X-Request-ID` is echoed in the header and the `meta` event."""
    response, events = answered
    assert response.headers["x-request-id"] == REQUEST_ID
    assert events[0].data["request_id"] == REQUEST_ID


def _final_citations(answered: tuple[httpx.Response, list[Any]]) -> dict[str, Any]:
    return dict(next(event.data for event in answered[1] if event.event == "citations"))


def _is_weak(sentence: dict[str, Any], is_valid: Callable[..., bool]) -> bool:
    citations = sentence["citations"]
    return not (sentence["supported"] and citations and all(map(is_valid, citations)))


def _chunk_ids(sentences: list[dict[str, Any]]) -> set[int]:
    cited = (citation.get("chunk_id") for s in sentences for citation in s["citations"])
    return {chunk_id for chunk_id in cited if chunk_id is not None}


def test_fr11_final_sentences_supported_and_cited(
    answered: tuple[httpx.Response, list[Any]], source_ref_is_valid: Callable[..., bool]
) -> None:
    """FR-11, FR-15: every final sentence is `supported` with at least one valid citation."""
    citations = _final_citations(answered)
    sentences = citations["sentences"]
    assert sentences and sentences[0]["text"] != FIXED_SENTENCE
    weak = [s["text"] for s in sentences if _is_weak(s, source_ref_is_valid)]
    assert weak == []
    assert isinstance(citations["dropped"], int)


def test_fr15_citations_resolve_to_chunks(
    answered: tuple[httpx.Response, list[Any]], sql: Rows
) -> None:
    """FR-15: cited chunk IDs exist; at least one citation resolves to a stored chunk."""
    cited = _chunk_ids(_final_citations(answered)["sentences"])
    stored = {
        row["id"] for row in sql("SELECT id FROM chunk WHERE id = ANY(:ids)", ids=list(cited))
    }
    assert cited and cited == stored


def test_fr11_retrieved_and_related_investigations_exist(
    answered: tuple[httpx.Response, list[Any]], seed_acronyms: list[str]
) -> None:
    """FR-11: retrieved chunks and `related` acronyms name seeded investigations; `done` is ok."""
    events = {event.event: event.data for event in answered[1]}
    retrieved = {item["acronym"] for item in events["meta"]["retrieved"]}
    assert retrieved and retrieved <= set(seed_acronyms)
    assert set(events["related"]["investigations"]) <= set(seed_acronyms)
    assert events["done"] == {"status": "ok"}


def test_fr11_out_of_corpus_question_gets_fixed_sentence(
    stack: str, api: httpx.Client, sse_events: Callable[[str], list[Any]]
) -> None:
    """FR-11, doc 05 s10: nothing retrieved gives the fixed sentence with no citations."""
    events = sse_events(_ask(api, {"question": OUT_OF_CORPUS_QUESTION}).text)
    data = {event.event: event.data for event in events}
    assert [event.event for event in events][-len(FINAL_EVENTS) :] == FINAL_EVENTS
    assert data["meta"]["retrieved"] == []
    assert data["citations"]["sentences"] == [
        {"text": FIXED_SENTENCE, "citations": [], "supported": True}
    ]
    assert (data["related"]["investigations"], data["done"]["status"]) == ([], "ok")


def test_fr11_malformed_body_is_422_envelope(
    stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """FR-11, doc 05 s2: a malformed body is the 422 JSON envelope, not a stream."""
    response = api.post("/ask", json={"top_k": 8})
    assert response.headers["content-type"].startswith("application/json")
    error = assert_error_envelope(response, 422, "validation_error")
    assert error["details"]
