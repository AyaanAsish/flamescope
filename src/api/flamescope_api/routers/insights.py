"""`/insights/*` (document 05 section 9)."""

from __future__ import annotations

from fastapi import APIRouter

from flamescope_api.deps import SafetyTechServiceDep
from flamescope_common.schemas.api import GapsResponse, SafetyTechResponse

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/safety-tech", response_model=SafetyTechResponse)
def safety_tech(service: SafetyTechServiceDep) -> SafetyTechResponse:
    return service.grouped()


@router.get("/gaps", response_model=GapsResponse)
def gaps(service: SafetyTechServiceDep) -> GapsResponse:
    return service.gaps()
