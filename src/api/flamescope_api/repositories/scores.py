"""`ScoreRepo`: stored criterion ratings per investigation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from flamescope_api.repositories import ACRONYM_ORDER, to_float
from flamescope_api.repositories.investigations import investigation_conditions
from flamescope_common.models import Investigation, RelevanceScore
from flamescope_common.rubric import Lens
from flamescope_common.schemas.api import InvestigationFilters
from flamescope_common.sources import SourceRef

ScoreOrigin = Literal["llm", "seed", "override"]


@dataclass(frozen=True)
class CriterionRating:
    """A criterion value 0 to 5 (None when there is no evidence) with its rationale."""

    value: float | None
    rationale: str = ""
    evidence: tuple[SourceRef, ...] = ()
    origin: ScoreOrigin = "seed"


@dataclass(frozen=True)
class InvestigationRatings:
    investigation_id: int
    acronym: str
    title: str
    ratings: dict[Lens, dict[str, CriterionRating]] = field(default_factory=dict)


class ScoreRepo:
    """Reads `relevance_score` rows of the current rubric version."""

    def __init__(self, session: Session, rubric_version: str) -> None:
        self._session = session
        self._rubric_version = rubric_version

    def all_scores(
        self, filters: InvestigationFilters | None = None
    ) -> list[InvestigationRatings]:
        """Ratings of every investigation matching the filters, ordered by acronym."""
        statement = (
            select(Investigation.id, Investigation.acronym, Investigation.title)
            .where(*investigation_conditions(filters))
            .order_by(*ACRONYM_ORDER)
        )
        heads = list(self._session.execute(statement))
        grouped = self._ratings_for([head.id for head in heads])
        return [
            InvestigationRatings(head.id, head.acronym, head.title, grouped.get(head.id, {}))
            for head in heads
        ]

    def for_investigation(self, investigation_id: int) -> InvestigationRatings:
        head = self._session.execute(
            select(Investigation.id, Investigation.acronym, Investigation.title).where(
                Investigation.id == investigation_id
            )
        ).one()
        grouped = self._ratings_for([investigation_id])
        return InvestigationRatings(
            head.id, head.acronym, head.title, grouped.get(investigation_id, {})
        )

    def _ratings_for(
        self, investigation_ids: Sequence[int]
    ) -> dict[int, dict[Lens, dict[str, CriterionRating]]]:
        if not investigation_ids:
            return {}
        statement = select(RelevanceScore).where(
            RelevanceScore.investigation_id.in_(investigation_ids),
            RelevanceScore.rubric_version == self._rubric_version,
        )
        grouped: dict[int, dict[Lens, dict[str, CriterionRating]]] = {}
        for row in self._session.scalars(statement):
            lens_ratings = grouped.setdefault(row.investigation_id, {}).setdefault(
                row.lens,  # type: ignore[arg-type]  # why: DB column is str, schema field is a Literal validated at ingest
                {},
            )
            lens_ratings[row.criterion] = _to_rating(row)
        return grouped


def _to_rating(row: RelevanceScore) -> CriterionRating:
    return CriterionRating(
        value=to_float(row.value),
        rationale=row.rationale,
        evidence=tuple(SourceRef.model_validate(item) for item in row.evidence),
        origin=row.origin,  # type: ignore[arg-type]  # why: DB column is str, schema field is a Literal validated at ingest
    )
