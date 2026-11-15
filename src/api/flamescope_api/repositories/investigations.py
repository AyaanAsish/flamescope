"""`InvestigationRepo`: catalog queries over investigations and their related tables."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    ColumnElement,
    Text,
    and_,
    case,
    exists,
    func,
    literal,
    null,
    or_,
    select,
    text,
)
from sqlalchemy.orm import QueryableAttribute, Session

from flamescope_api.repositories import ACRONYM_ORDER, ENGLISH_TS_CONFIG
from flamescope_common.errors import NotFoundError
from flamescope_common.models import (
    Chunk,
    Finding,
    Fuel,
    Hardware,
    IngestRun,
    Investigation,
    InvestigationHardware,
    Measurement,
    Project,
    Publication,
    TestRun,
)
from flamescope_common.schemas.api import (
    InvestigationFilters,
    PageRequest,
)

HARDWARE_ROLE_ORDER = {"host": 0, "apparatus": 1, "instrument": 2}
FUEL_PHASES = ("gas", "liquid", "solid")


@dataclass(frozen=True)
class InvestigationRow:
    """An investigation with the names of its project and hardware."""

    investigation: Investigation
    project: str | None = None
    hardware: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchResult:
    rows: list[InvestigationRow]
    total: int


@dataclass(frozen=True)
class FindingRow:
    finding: Finding
    acronym: str


@dataclass(frozen=True)
class HardwareLinks:
    """Everything the lineage graph is built from."""

    hardware: list[Hardware] = field(default_factory=list)
    links: list[tuple[str, str, str]] = field(default_factory=list)  # acronym, hardware, role
    projects: dict[str, str | None] = field(default_factory=dict)  # acronym -> project name


@dataclass(frozen=True)
class CorpusStats:
    """Row counts and parameter ranges for `GET /meta/stats`."""

    investigations: int
    test_runs: int
    publications: int
    findings: int
    hardware: int
    chunks: int
    fuel_phase_counts: dict[str, int]
    o2_range: tuple[float | None, float | None]
    pressure_range_kpa: tuple[float | None, float | None]


def investigation_conditions(filters: InvestigationFilters | None) -> list[ColumnElement[bool]]:
    """WHERE clauses for the catalog filters of document 05 section 4."""
    if filters is None:
        return []
    clauses = [
        *_text_conditions(filters),
        *_array_conditions(filters),
        *_range_conditions(filters),
    ]
    if filters.gravity_level:
        clauses.append(Investigation.gravity_level == filters.gravity_level)
    return clauses


def _text_conditions(filters: InvestigationFilters) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.q:
        clauses.append(
            or_(
                Investigation.search_tsv.op("@@")(
                    func.websearch_to_tsquery(ENGLISH_TS_CONFIG, filters.q)
                ),
                Investigation.acronym.icontains(filters.q, autoescape=True),
                Investigation.title.icontains(filters.q, autoescape=True),
            )
        )
    if filters.project:
        clauses.append(
            Investigation.project_id.in_(
                select(Project.id).where(func.lower(Project.name) == filters.project.lower())
            )
        )
    if filters.material:
        clauses.append(
            exists().where(
                TestRun.investigation_id == Investigation.id,
                TestRun.fuel_id == Fuel.id,
                Fuel.name.icontains(filters.material, autoescape=True),
            )
        )
    return clauses


def _overlaps(column: QueryableAttribute[Any], values: Sequence[str]) -> ColumnElement[bool]:
    """Postgres array overlap (`&&`) with a typed `text[]` bind."""
    return column.op("&&")(literal(list(values), ARRAY(Text)))


def _array_conditions(filters: InvestigationFilters) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.fuel_phase:
        clauses.append(_overlaps(Investigation.fuel_phases, filters.fuel_phase))
    if filters.tag:
        clauses.append(_overlaps(Investigation.fire_safety_tags, filters.tag))
    if filters.hardware:
        wanted = [name.lower() for name in filters.hardware]
        clauses.append(
            exists().where(
                InvestigationHardware.investigation_id == Investigation.id,
                InvestigationHardware.hardware_id == Hardware.id,
                func.lower(Hardware.name).in_(wanted),
            )
        )
    return clauses


def _overlaps_range(
    low: QueryableAttribute[Any],
    high: QueryableAttribute[Any],
    wanted_min: float | None,
    wanted_max: float | None,
) -> list[ColumnElement[bool]]:
    """Overlap with `[wanted_min, wanted_max]`; a null end of a range with data is open."""
    has_data = or_(low.is_not(None), high.is_not(None))
    clauses: list[ColumnElement[bool]] = []
    if wanted_min is not None:
        clauses.append(and_(has_data, or_(high.is_(None), high >= wanted_min)))
    if wanted_max is not None:
        clauses.append(and_(has_data, or_(low.is_(None), low <= wanted_max)))
    return clauses


def _range_conditions(filters: InvestigationFilters) -> list[ColumnElement[bool]]:
    """An investigation matches when its stated range overlaps the requested one."""
    return [
        *_overlaps_range(
            Investigation.o2_min, Investigation.o2_max, filters.o2_min, filters.o2_max
        ),
        *_overlaps_range(
            Investigation.pressure_min_kpa,
            Investigation.pressure_max_kpa,
            filters.pressure_min_kpa,
            filters.pressure_max_kpa,
        ),
    ]


class InvestigationRepo:
    """Read access to investigations, their findings, publications and hardware links."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self, filters: InvestigationFilters | None, page: PageRequest | None = None
    ) -> SearchResult:
        """Filtered investigations ordered by acronym; `page=None` returns every match."""
        conditions = investigation_conditions(filters)
        total = self._session.scalar(
            select(func.count()).select_from(Investigation).where(and_(True, *conditions))
        )
        statement = select(Investigation).where(*conditions).order_by(*ACRONYM_ORDER)
        if page is not None:
            statement = statement.limit(page.page_size).offset(page.offset)
        rows = self._rows(list(self._session.scalars(statement)))
        return SearchResult(rows=rows, total=total or 0)

    def get(self, id_or_acronym: str | int) -> InvestigationRow:
        """Resolve a numeric ID or a case-insensitive acronym; raises `NotFoundError`."""
        text = str(id_or_acronym)
        investigation = None
        if text.isdecimal():
            investigation = self._session.get(Investigation, int(text))
        if investigation is None:
            investigation = self._session.scalar(
                select(Investigation).where(func.lower(Investigation.acronym) == text.lower())
            )
        if investigation is None:
            raise NotFoundError(f"Investigation '{text}' not found")
        return self._rows([investigation])[0]

    def by_ids(self, ids: Sequence[int]) -> list[InvestigationRow]:
        if not ids:
            return []
        statement = select(Investigation).where(Investigation.id.in_(ids)).order_by(*ACRONYM_ORDER)
        return self._rows(list(self._session.scalars(statement)))

    def facet_counts(self) -> dict[str, list[tuple[str, int]]]:
        """Value counts for every facet of `GET /facets`."""
        return {
            "fuel_phase": self._unnest_counts(Investigation.fuel_phases),
            "tag": self._unnest_counts(Investigation.fire_safety_tags),
            "platform": self._column_counts(Investigation.platform),
            "gravity_level": self._column_counts(Investigation.gravity_level),
            "hardware": self._hardware_counts(),
            "project": self._project_counts(),
        }

    def findings(
        self, category: str | None = None, acronyms: Sequence[str] | None = None
    ) -> list[FindingRow]:
        statement = (
            select(Finding, Investigation.acronym)
            .join(Investigation, Investigation.id == Finding.investigation_id)
            .order_by(*ACRONYM_ORDER, Finding.id)
        )
        if category:
            statement = statement.where(Finding.category == category)
        if acronyms:
            statement = statement.where(
                func.lower(Investigation.acronym).in_([name.lower() for name in acronyms])
            )
        return [
            FindingRow(finding, acronym) for finding, acronym in self._session.execute(statement)
        ]

    def publications(self, investigation_id: int) -> list[Publication]:
        statement = (
            select(Publication)
            .where(Publication.investigation_id == investigation_id)
            .order_by(Publication.year.desc().nulls_last(), Publication.id)
        )
        return list(self._session.scalars(statement))

    def measurements(self, investigation_id: int) -> list[Measurement]:
        statement = (
            select(Measurement)
            .where(Measurement.investigation_id == investigation_id)
            .order_by(Measurement.id)
        )
        return list(self._session.scalars(statement))

    def hardware_links(self) -> HardwareLinks:
        hardware = list(self._session.scalars(select(Hardware).order_by(Hardware.name)))
        link_rows = self._session.execute(
            select(Investigation.acronym, Hardware.name, InvestigationHardware.role)
            .join(Investigation, Investigation.id == InvestigationHardware.investigation_id)
            .join(Hardware, Hardware.id == InvestigationHardware.hardware_id)
            .order_by(*ACRONYM_ORDER, Hardware.name)
        )
        project_rows = self._session.execute(
            select(Investigation.acronym, Project.name)
            .outerjoin(Project, Project.id == Investigation.project_id)
            .order_by(*ACRONYM_ORDER)
        )
        return HardwareLinks(
            hardware=hardware,
            links=[(acronym, name, role) for acronym, name, role in link_rows],
            projects=dict(project_rows.tuples().all()),
        )

    def projects(self) -> list[tuple[Project, list[str]]]:
        """Every project with the acronyms of its investigations."""
        projects = list(self._session.scalars(select(Project).order_by(Project.name)))
        members = self._session.execute(
            select(Investigation.project_id, Investigation.acronym).order_by(*ACRONYM_ORDER)
        )
        by_project: dict[int, list[str]] = {}
        for project_id, acronym in members:
            if project_id is not None:
                by_project.setdefault(project_id, []).append(acronym)
        return [(project, by_project.get(project.id, [])) for project in projects]

    def stats(self) -> CorpusStats:
        def count(
            model: type[Hardware | Publication | Finding | Investigation | TestRun | Chunk],
        ) -> int:
            return self._session.scalar(select(func.count()).select_from(model)) or 0

        phase_counts = dict.fromkeys(FUEL_PHASES, 0)
        phase_counts.update(dict(self._unnest_counts(Investigation.fuel_phases)))
        return CorpusStats(
            investigations=count(Investigation),
            test_runs=count(TestRun),
            publications=count(Publication),
            findings=count(Finding),
            hardware=count(Hardware),
            chunks=count(Chunk),
            fuel_phase_counts=phase_counts,
            o2_range=self._bounds(Investigation.o2_min, Investigation.o2_max),
            pressure_range_kpa=self._bounds(
                Investigation.pressure_min_kpa, Investigation.pressure_max_kpa
            ),
        )

    def last_ingest_run(self) -> IngestRun | None:
        statement = select(IngestRun).order_by(IngestRun.started_at.desc()).limit(1)
        return self._session.scalar(statement)

    def schema_revision(self) -> str | None:
        """The applied Alembic revision, or None when migrations have not run."""
        try:
            revision: str | None = self._session.scalar(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            return revision
        except Exception:  # the table is missing before the first migration
            self._session.rollback()
            return None

    def ping(self) -> bool:
        try:
            self._session.execute(select(1))
        except Exception:  # any driver error means the database is unreachable
            self._session.rollback()
            return False
        return True

    def _rows(self, investigations: list[Investigation]) -> list[InvestigationRow]:
        if not investigations:
            return []
        ids = [item.id for item in investigations]
        project_ids = {item.project_id for item in investigations if item.project_id is not None}
        # `Result` exposes `keys()`, so `dict()` would treat it as a mapping; materialize tuples.
        project_names = dict(
            self._session.execute(
                select(Project.id, Project.name).where(Project.id.in_(project_ids))
            )
            .tuples()
            .all()
        )
        hardware = self._hardware_by_investigation(ids)
        return [
            InvestigationRow(
                investigation=item,
                project=project_names.get(item.project_id) if item.project_id else None,
                hardware=tuple(hardware.get(item.id, [])),
            )
            for item in investigations
        ]

    def _hardware_by_investigation(self, ids: list[int]) -> dict[int, list[str]]:
        rows = self._session.execute(
            select(
                InvestigationHardware.investigation_id, Hardware.name, InvestigationHardware.role
            )
            .join(Hardware, Hardware.id == InvestigationHardware.hardware_id)
            .where(InvestigationHardware.investigation_id.in_(ids))
        )
        ordered = sorted(rows, key=lambda row: (HARDWARE_ROLE_ORDER.get(row.role, 9), row.name))
        names: dict[int, list[str]] = {}
        for investigation_id, name, _role in ordered:
            names.setdefault(investigation_id, []).append(name)
        return names

    def _unnest_counts(self, array_column: QueryableAttribute[Any]) -> list[tuple[str, int]]:
        unnested = select(func.unnest(array_column).label("value")).subquery()
        value = unnested.c.value
        statement = (
            select(value, func.count()).group_by(value).order_by(func.count().desc(), value)
        )
        return [(str(name), count) for name, count in self._session.execute(statement)]

    def _column_counts(self, column: QueryableAttribute[Any]) -> list[tuple[str, int]]:
        statement = (
            select(column, func.count())
            .where(column.is_not(None))
            .group_by(column)
            .order_by(func.count().desc(), column)
        )
        return [(str(name), count) for name, count in self._session.execute(statement)]

    def _hardware_counts(self) -> list[tuple[str, int]]:
        statement = (
            select(Hardware.name, func.count(InvestigationHardware.investigation_id))
            .join(InvestigationHardware, InvestigationHardware.hardware_id == Hardware.id)
            .group_by(Hardware.name)
            .order_by(func.count(InvestigationHardware.investigation_id).desc(), Hardware.name)
        )
        return [(name, count) for name, count in self._session.execute(statement)]

    def _project_counts(self) -> list[tuple[str, int]]:
        statement = (
            select(Project.name, func.count(Investigation.id))
            .join(Investigation, Investigation.project_id == Project.id)
            .group_by(Project.name)
            .order_by(func.count(Investigation.id).desc(), Project.name)
        )
        return [(name, count) for name, count in self._session.execute(statement)]

    def _bounds(
        self, low: QueryableAttribute[Any], high: QueryableAttribute[Any]
    ) -> tuple[float | None, float | None]:
        statement = select(_open_or(func.min(low), low, high), _open_or(func.max(high), high, low))
        row = self._session.execute(statement).one()
        return (_optional_float(row[0]), _optional_float(row[1]))


def _open_or(
    extent: ColumnElement[Any], end: QueryableAttribute[Any], other: QueryableAttribute[Any]
) -> ColumnElement[Any]:
    """Null when any range is open on this side (doc 04 s2), else the corpus extent."""
    is_open = func.bool_or(and_(end.is_(None), other.is_not(None)))
    return case((is_open, null()), else_=extent)


def _optional_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)
