"""`GET /earth-applications` (document 05 section 9)."""

from __future__ import annotations

from fastapi import APIRouter

from flamescope_api.deps import EarthServiceDep
from flamescope_common.schemas.api import EarthApplicationsResponse, EarthSector

router = APIRouter(tags=["earth"])


@router.get("/earth-applications", response_model=EarthApplicationsResponse)
def earth_applications(
    service: EarthServiceDep, sector: EarthSector | None = None
) -> EarthApplicationsResponse:
    return service.list(sector)
