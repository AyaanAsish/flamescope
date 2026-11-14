"""`/investigations` (document 05 section 4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from flamescope_api.deps import CatalogServiceDep
from flamescope_common.schemas.api import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    InvestigationDetail,
    InvestigationFilters,
    InvestigationSummary,
    Page,
    PageRequest,
    PublicationOut,
    RunItem,
    VariablesResponse,
)

router = APIRouter(prefix="/investigations", tags=["investigations"])
# Document 05 sections 4 and 11 name the path parameter `{id}`; the alias keeps that contract
# without shadowing the `id` builtin in Python.
InvestigationId = Annotated[str, Path(alias="id")]


class ListQuery(InvestigationFilters, PageRequest):
    """Every query parameter of `GET /investigations`."""


@router.get("", response_model=Page[InvestigationSummary])
def list_investigations(
    query: Annotated[ListQuery, Query()], service: CatalogServiceDep
) -> Page[InvestigationSummary]:
    page = PageRequest(page=query.page, page_size=query.page_size, sort=query.sort)
    return service.list(
        InvestigationFilters.model_validate(
            query.model_dump(include=set(InvestigationFilters.model_fields))
        ),
        page,
    )


@router.get("/{id}", response_model=InvestigationDetail)
def get_investigation(
    investigation_id: InvestigationId, service: CatalogServiceDep
) -> InvestigationDetail:
    return service.get(investigation_id)


@router.get("/{id}/runs", response_model=Page[RunItem])
def list_runs(
    investigation_id: InvestigationId,
    service: CatalogServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[RunItem]:
    return service.runs(investigation_id, PageRequest(page=page, page_size=page_size))


@router.get("/{id}/variables", response_model=VariablesResponse)
def get_variables(
    investigation_id: InvestigationId, service: CatalogServiceDep
) -> VariablesResponse:
    return service.variables(investigation_id)


@router.get("/{id}/publications", response_model=list[PublicationOut])
def list_publications(
    investigation_id: InvestigationId, service: CatalogServiceDep
) -> list[PublicationOut]:
    return service.publications(investigation_id)
