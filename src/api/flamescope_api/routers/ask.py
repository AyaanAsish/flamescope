"""`POST /ask` (document 05 section 10): Server-Sent Events."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from flamescope_api.deps import InsightServiceDep
from flamescope_api.sse import SSE_MEDIA_TYPE, sse_response
from flamescope_common.schemas.api import AskRequest

router = APIRouter(tags=["ask"])


@router.post(
    "/ask",
    response_class=StreamingResponse,
    responses={200: {"content": {SSE_MEDIA_TYPE: {}}, "description": "Event stream"}},
)
async def ask(body: AskRequest, service: InsightServiceDep) -> StreamingResponse:
    return sse_response(service.ask(body.question, body.filters, body.top_k))
