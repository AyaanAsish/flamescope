"""`/meta/*` (document 05 section 3)."""

from __future__ import annotations

from fastapi import APIRouter

from flamescope_api.deps import MetaServiceDep, PresetsDep, RubricDep
from flamescope_common.schemas.api import (
    PresetsResponse,
    RubricResponse,
    StatsResponse,
    StatusResponse,
)

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/stats", response_model=StatsResponse)
def stats(service: MetaServiceDep) -> StatsResponse:
    return service.stats()


@router.get("/status", response_model=StatusResponse)
def status(service: MetaServiceDep) -> StatusResponse:
    return service.status()


@router.get("/rubric", response_model=RubricResponse)
def rubric(current: RubricDep) -> RubricResponse:
    return current


@router.get("/presets", response_model=PresetsResponse)
def presets(current: PresetsDep) -> PresetsResponse:
    return current
