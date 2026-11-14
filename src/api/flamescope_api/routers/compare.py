"""`POST /compare` (document 05 section 6)."""

from __future__ import annotations

from fastapi import APIRouter

from flamescope_api.deps import CompareServiceDep
from flamescope_common.schemas.api import CompareRequest, CompareResponse

router = APIRouter(tags=["compare"])


@router.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest, service: CompareServiceDep) -> CompareResponse:
    return await service.compare(body.investigations, body.narrative)
