"""`POST /rank` (document 05 section 5)."""

from __future__ import annotations

from fastapi import APIRouter

from flamescope_api.deps import RankingServiceDep
from flamescope_api.services.ranking import WeightOverrides
from flamescope_common.schemas.api import RankRequest, RankResponse

router = APIRouter(tags=["ranking"])


@router.post("/rank", response_model=RankResponse)
def rank(body: RankRequest, service: RankingServiceDep) -> RankResponse:
    overrides = WeightOverrides(body.lens_weights, body.criterion_weights)
    response = service.rank(body.lens, overrides, body.preset, body.filters)
    return response.model_copy(update={"items": response.items[: body.limit]})
