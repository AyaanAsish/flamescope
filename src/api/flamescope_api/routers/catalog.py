"""`/facets`, `/hardware`, `/projects` (document 05 section 4)."""

from __future__ import annotations

from fastapi import APIRouter

from flamescope_api.deps import CatalogServiceDep
from flamescope_common.schemas.api import FacetsResponse, LineageGraph, ProjectOut

router = APIRouter(tags=["catalog"])


@router.get("/facets", response_model=FacetsResponse)
def facets(service: CatalogServiceDep) -> FacetsResponse:
    return service.facets()


@router.get("/hardware", response_model=LineageGraph)
def hardware(service: CatalogServiceDep) -> LineageGraph:
    return service.hardware_lineage()


@router.get("/projects", response_model=list[ProjectOut])
def projects(service: CatalogServiceDep) -> list[ProjectOut]:
    return service.projects()
