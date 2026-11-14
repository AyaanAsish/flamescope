"""`EarthService`: Earth applications of the findings (objective O4)."""

from __future__ import annotations

from flamescope_api.repositories.earth import EarthRepo
from flamescope_common.schemas.api import EarthApplicationOut, EarthApplicationsResponse
from flamescope_common.sources import SourceRef


class EarthService:
    """Lists applications with their linked investigations and findings; no LLM."""

    def __init__(self, earth: EarthRepo) -> None:
        self._earth = earth

    def list(self, sector: str | None = None) -> EarthApplicationsResponse:
        return EarthApplicationsResponse(
            items=[
                EarthApplicationOut.model_validate(
                    {
                        "id": row.application.id,
                        "title": row.application.title,
                        "sector": row.application.sector,
                        "description": row.application.description,
                        "maturity": row.application.maturity,
                        "investigations": row.investigations,
                        "findings": row.finding_ids,
                        "references": [
                            SourceRef.model_validate(ref) for ref in row.application.references
                        ],
                    }
                )
                for row in self._earth.list(sector)
            ]
        )
