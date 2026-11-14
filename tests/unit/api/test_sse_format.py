"""FR-11: Server-Sent Events frame formatting and the `/ask` stream (document 05 section 10)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flamescope_api import deps
from flamescope_api.sse import sse_event, sse_response
from flamescope_common.schemas.api import AskDone, AskFilters, AskToken

pytestmark = pytest.mark.unit

SSE_MEDIA_TYPE = "text/event-stream"
EVENT_ORDER = ["meta", "token", "token", "citations", "related", "done"]


def _split(frame: str) -> tuple[str, Any]:
    assert frame.endswith("\n\n"), "a frame ends with a blank line"
    lines = frame[:-2].split("\n")
    assert len(lines) == 2, "one event line and one single-line data field"
    event_line, data_line = lines
    assert event_line.startswith("event: ")
    assert data_line.startswith("data: ")
    return event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))


def _frames(body: str) -> list[tuple[str, Any]]:
    return [_split(f"{chunk}\n\n") for chunk in body.split("\n\n") if chunk]


class TestSseEvent:
    def test_fr11_mapping_frame(self) -> None:
        """FR-11: `event:` line, JSON `data:` line, blank line."""
        assert _split(sse_event("token", {"text": "partial"})) == ("token", {"text": "partial"})

    def test_fr11_model_frame(self) -> None:
        """FR-11: Pydantic models serialize as their JSON."""
        assert _split(sse_event("done", AskDone())) == ("done", {"status": "ok"})

    def test_fr11_newlines_in_text_stay_in_one_data_line(self) -> None:
        """FR-11: multi-line text never splits the data field."""
        event, data = _split(sse_event("token", AskToken(text="line one\nline two")))
        assert event == "token"
        assert data == {"text": "line one\nline two"}

    async def test_fr11_streaming_response_media_type(self) -> None:
        """FR-11: frames stream as `text/event-stream`, uncached and not re-encoded by proxies."""

        async def frames() -> AsyncIterator[str]:
            yield sse_event("done", AskDone())

        response = sse_response(frames())
        assert response.media_type == SSE_MEDIA_TYPE
        assert response.headers["Cache-Control"] == "no-cache, no-transform"


class FakeInsightService:
    """Yields the documented event sequence and records the arguments."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, AskFilters, int]] = []

    async def ask(self, question: str, filters: AskFilters, top_k: int) -> AsyncIterator[str]:
        self.calls.append((question, filters, top_k))
        yield sse_event("meta", {"request_id": "r", "retrieved": []})
        yield sse_event("token", AskToken(text="Partial "))
        yield sse_event("token", AskToken(text="answer [c:1]."))
        yield sse_event("citations", {"sentences": [], "dropped": 0})
        yield sse_event("related", {"investigations": []})
        yield sse_event("done", AskDone())


def test_fr11_ask_endpoint_streams_events_in_order(app: FastAPI, client: TestClient) -> None:
    """FR-11: `POST /ask` streams meta, token+, citations, related, done; request ID echoed."""
    service = FakeInsightService()
    app.dependency_overrides[deps.get_insight_service] = lambda: service
    response = client.post(
        "/api/v1/ask", json={"question": "Which fuels?"}, headers={"X-Request-ID": "ask-1"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(SSE_MEDIA_TYPE)
    assert response.headers["X-Request-ID"] == "ask-1"
    assert [event for event, _ in _frames(response.text)] == EVENT_ORDER
    assert service.calls == [("Which fuels?", AskFilters(), 8)]
