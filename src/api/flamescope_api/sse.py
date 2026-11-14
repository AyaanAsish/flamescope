"""Server-Sent Events formatting and the streaming response helper (document 05 section 10)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

SSE_MEDIA_TYPE = "text/event-stream"
# `no-transform` keeps the UI's Next.js rewrite from gzip-compressing the stream, which would
# hold every event until the response ends (doc 10 section 5 `/ask`: streaming).
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


def sse_event(event: str, data: BaseModel | Mapping[str, Any]) -> str:
    """One event frame: `event:` line, single-line JSON `data:` line, blank line."""
    payload = data.model_dump_json() if isinstance(data, BaseModel) else json.dumps(dict(data))
    return f"event: {event}\ndata: {payload}\n\n"


def sse_response(events: AsyncIterator[str]) -> StreamingResponse:
    """Stream pre-formatted frames with proxy buffering disabled."""
    return StreamingResponse(events, media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)
