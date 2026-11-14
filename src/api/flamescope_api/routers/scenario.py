"""`POST /scenario` (document 05 section 7)."""

from __future__ import annotations

from fastapi import APIRouter

from flamescope_api.deps import ScenarioServiceDep
from flamescope_common.schemas.api import ScenarioRequest, ScenarioResponse

router = APIRouter(tags=["scenario"])


@router.post("/scenario", response_model=ScenarioResponse)
async def scenario(body: ScenarioRequest, service: ScenarioServiceDep) -> ScenarioResponse:
    return await service.match(body, body.explain)
