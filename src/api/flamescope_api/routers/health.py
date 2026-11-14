"""`/health` and `/ready` (document 05 section 3)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from flamescope_api.deps import MetaServiceDep
from flamescope_common.schemas.api import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])
NOT_READY_STATUS = "not_ready"
SERVICE_UNAVAILABLE = 503


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={SERVICE_UNAVAILABLE: {"description": "Database, migrations or data missing"}},
)
def ready(service: MetaServiceDep) -> ReadyResponse | JSONResponse:
    readiness = service.ready()
    if readiness.is_ready:
        return readiness.report
    body = {**readiness.report.model_dump(), "status": NOT_READY_STATUS}
    return JSONResponse(body, status_code=SERVICE_UNAVAILABLE)
