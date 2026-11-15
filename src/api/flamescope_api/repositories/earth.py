"""`EarthRepo`: Earth applications with their linked investigations and findings."""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from flamescope_common.models import (
    EarthApplication,
    EarthApplicationInvestigation,
    Finding,
    FindingEarthApplication,
    Investigation,
)
from flamescope_common.schemas.card import acronym_sort_key


@dataclass(frozen=True)
class EarthRow:
    application: EarthApplication
    investigations: list[str] = field(default_factory=list)
    finding_ids: list[int] = field(default_factory=list)


class EarthRepo:
    """Read access to `earth_application` and its link tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, sector: str | None = None) -> builtins.list[EarthRow]:
        statement = select(EarthApplication).order_by(
            EarthApplication.sector, EarthApplication.title
        )
        if sector:
            statement = statement.where(EarthApplication.sector == sector)
        applications = list(self._session.scalars(statement))
        direct = self._direct_links()
        via_findings = self._finding_links()
        return [
            EarthRow(
                application=app,
                investigations=sorted(
                    {*direct.get(app.id, []), *(name for _, name in via_findings.get(app.id, []))},
                    key=acronym_sort_key,
                ),
                finding_ids=sorted(finding_id for finding_id, _ in via_findings.get(app.id, [])),
            )
            for app in applications
        ]

    def _direct_links(self) -> dict[int, builtins.list[str]]:
        rows = self._session.execute(
            select(EarthApplicationInvestigation.earth_application_id, Investigation.acronym).join(
                Investigation, Investigation.id == EarthApplicationInvestigation.investigation_id
            )
        )
        links: dict[int, builtins.list[str]] = {}
        for application_id, acronym in rows:
            links.setdefault(application_id, []).append(acronym)
        return links

    def _finding_links(self) -> dict[int, builtins.list[tuple[int, str]]]:
        rows = self._session.execute(
            select(FindingEarthApplication.earth_application_id, Finding.id, Investigation.acronym)
            .join(Finding, Finding.id == FindingEarthApplication.finding_id)
            .join(Investigation, Investigation.id == Finding.investigation_id)
        )
        links: dict[int, builtins.list[tuple[int, str]]] = {}
        for application_id, finding_id, acronym in rows:
            links.setdefault(application_id, []).append((finding_id, acronym))
        return links
