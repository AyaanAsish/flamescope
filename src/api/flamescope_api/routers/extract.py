"""`/extract/*` (document 05 section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Response

from flamescope_api.deps import ExtractServiceDep
from flamescope_common.schemas.api import (
    DictionaryResponse,
    ExportRequest,
    ExtractRequest,
    Table,
)

router = APIRouter(prefix="/extract", tags=["extract"])


@router.post("/preview", response_model=Table)
def preview(body: ExtractRequest, service: ExtractServiceDep) -> Table:
    return service.preview(body)


@router.post("/export", response_class=Response)
def export(body: ExportRequest, service: ExtractServiceDep) -> Response:
    file = service.export(body, body.format)
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


@router.get("/dictionary", response_model=DictionaryResponse)
def dictionary(service: ExtractServiceDep) -> DictionaryResponse:
    return service.dictionary()
