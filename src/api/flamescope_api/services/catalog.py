"""`CatalogService`: browse investigations, runs, variables, facets and lineage."""

from __future__ import annotations

import builtins
import math
from collections.abc import Sequence

from pydantic import JsonValue

from flamescope_api.repositories import range_pair
from flamescope_api.repositories.investigations import (
    InvestigationRepo,
    InvestigationRow,
)
from flamescope_api.repositories.runs import RunRecord, RunRepo
from flamescope_api.services.ranking import RankingService
from flamescope_common.models import Finding, Hardware, Measurement
from flamescope_common.schemas.api import (
    FacetsResponse,
    FacetValue,
    FindingOut,
    FixedParameter,
    FuelRef,
    InvestigationDetail,
    InvestigationFilters,
    InvestigationSummary,
    LineageEdge,
    LineageGraph,
    LineageNode,
    MeasurementOut,
    Page,
    PageRequest,
    ProjectOut,
    PublicationOut,
    RunItem,
    ScoreSet,
    VariablesResponse,
    VariedParameter,
)
from flamescope_common.schemas.card import (
    CardVariables,
    InvestigationCard,
    RunCondition,
    RunOutcome,
)
from flamescope_common.sources import SourceRef

CONDITION_UNITS = {
    "o2_fraction": "fraction",
    "pressure_kpa": "kPa",
    "flow_speed_cm_s": "cm/s",
    "gravity_g": "g",
    "e_field_kv": "kV",
    "temperature_k": "K",
}
SCORE_SORT_KEYS = ("overall", "habitat", "modeling", "controls")
HARDWARE_PREFIX = "hw"
INVESTIGATION_PREFIX = "inv"
PROJECT_PREFIX = "proj"


def build_summary(row: InvestigationRow, scores: ScoreSet | None = None) -> InvestigationSummary:
    """`InvestigationSummary` of document 05 section 4 from a repository row."""
    item = row.investigation
    return InvestigationSummary(
        id=item.id,
        acronym=item.acronym,
        title=item.title,
        project=row.project,
        platform=item.platform,
        gravity_level=item.gravity_level,
        fuel_phases=list(item.fuel_phases or []),
        hardware=list(row.hardware),
        summary=item.summary,
        fire_safety_tags=list(item.fire_safety_tags or []),
        o2_range=range_pair(item.o2_min, item.o2_max),
        pressure_range_kpa=range_pair(item.pressure_min_kpa, item.pressure_max_kpa),
        flow_range_cm_s=range_pair(item.flow_min_cm_s, item.flow_max_cm_s),
        scores=scores or ScoreSet(),
        reviewed=item.reviewed,
        psi_url=item.psi_url,
    )


def to_run_item(record: RunRecord) -> RunItem:
    """`RunItem` of document 05 section 4 from a flat run record."""
    fuel = None
    if record.fuel_name and record.fuel_phase:
        fuel = FuelRef.model_validate({"name": record.fuel_name, "phase": record.fuel_phase})
    return RunItem(
        id=record.run_id,
        label=record.label,
        fuel=fuel,
        geometry=record.geometry,
        condition=RunCondition.model_validate(
            {name: getattr(record, name) for name in RunCondition.model_fields}
        ),
        outcome=RunOutcome.model_validate(record.outcome),
        is_aggregate=record.is_aggregate,
        source=SourceRef.model_validate(record.source) if record.source else None,
        confidence=record.confidence,
    )


def _observed_values(runs: Sequence[RunRecord]) -> dict[str, builtins.list[JsonValue]]:
    """Distinct values per parameter across runs: condition columns and `varied_parameters`."""
    observed: dict[str, builtins.list[JsonValue]] = {}
    for run in runs:
        for name in CONDITION_UNITS:
            value = run.value_of(name)
            if value is not None:
                _add_distinct(observed.setdefault(name, []), value)
        for name, stated in run.varied_parameters.items():
            for value in stated if isinstance(stated, list) else [stated]:
                _add_distinct(observed.setdefault(name, []), value)
    return observed


def derive_variables(runs: Sequence[RunRecord], declared: CardVariables) -> VariablesResponse:
    """Split parameters into varied (several distinct values) and fixed (one value), FR-06."""
    observed = _observed_values(runs)
    varied = [
        VariedParameter(name=name, values=_ordered(values), unit=CONDITION_UNITS.get(name))
        for name, values in observed.items()
        if len(values) > 1
    ]
    fixed = [
        FixedParameter(name=name, value=values[0], unit=CONDITION_UNITS.get(name))
        for name, values in observed.items()
        if len(values) == 1
    ]
    varied += [VariedParameter(name=name) for name in declared.varied if name not in observed]
    fixed += [FixedParameter(name=name) for name in declared.fixed if name not in observed]
    return VariablesResponse(varied=varied, fixed=fixed, run_count=len(runs))


def _add_distinct(values: list[JsonValue], candidate: JsonValue) -> None:
    if not any(_same(candidate, known) for known in values):
        values.append(candidate)


def _same(left: JsonValue, right: JsonValue) -> bool:
    if isinstance(left, float | int) and isinstance(right, float | int):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)
    return left == right


def _numeric_key(value: JsonValue) -> float:
    return float(value) if isinstance(value, float | int) else 0.0


def _ordered(values: list[JsonValue]) -> list[JsonValue]:
    if all(isinstance(value, float | int) for value in values):
        return sorted(values, key=_numeric_key)
    return values


class CatalogService:
    """Catalog reads; deterministic, no LLM."""

    def __init__(
        self, investigations: InvestigationRepo, runs: RunRepo, ranking: RankingService
    ) -> None:
        self._investigations = investigations
        self._runs = runs
        self._ranking = ranking

    def list(self, filters: InvestigationFilters, page: PageRequest) -> Page[InvestigationSummary]:
        """A page of summaries sorted by `page.sort` (score sorts are descending, nulls last)."""
        if page.sort == "acronym":
            result = self._investigations.search(filters, page)
            scores = self._ranking.score_sets([row.investigation.id for row in result.rows])
            rows, total = result.rows, result.total
        else:
            result = self._investigations.search(filters, None)
            scores = self._ranking.score_sets([row.investigation.id for row in result.rows])
            ordered = sorted(
                result.rows, key=lambda row: self._score_order(row, scores, page.sort)
            )
            rows = ordered[page.offset : page.offset + page.page_size]
            total = result.total
        items = [build_summary(row, scores.get(row.investigation.id)) for row in rows]
        return Page[InvestigationSummary](
            items=items, page=page.page, page_size=page.page_size, total=total
        )

    def get(self, id_or_acronym: str) -> InvestigationDetail:
        row = self._investigations.get(id_or_acronym)
        item = row.investigation
        card = InvestigationCard.model_validate(item.card)
        breakdown = self._ranking.breakdown(item.id)
        summary = build_summary(row, self._ranking.score_sets([item.id]).get(item.id))
        runs = self._runs.for_investigation(item.id)
        findings = self._investigations.findings(None, [item.acronym])
        return InvestigationDetail(
            **summary.model_dump(),
            card=card,
            publications=self._publications(item.id),
            measurements=[
                _measurement(entry) for entry in self._investigations.measurements(item.id)
            ],
            findings=[_finding_out(entry.finding) for entry in findings],
            score_breakdown=breakdown,
            run_count=len(runs),
            data=card.data,
        )

    def runs(self, id_or_acronym: str, page: PageRequest) -> Page[RunItem]:
        row = self._investigations.get(id_or_acronym)
        records = self._runs.for_investigation(row.investigation.id)
        window = records[page.offset : page.offset + page.page_size]
        return Page[RunItem](
            items=[to_run_item(record) for record in window],
            page=page.page,
            page_size=page.page_size,
            total=len(records),
        )

    def variables(self, id_or_acronym: str) -> VariablesResponse:
        row = self._investigations.get(id_or_acronym)
        card = InvestigationCard.model_validate(row.investigation.card)
        return derive_variables(self._runs.for_investigation(row.investigation.id), card.variables)

    def publications(self, id_or_acronym: str) -> builtins.list[PublicationOut]:
        return self._publications(self._investigations.get(id_or_acronym).investigation.id)

    def facets(self) -> FacetsResponse:
        counts = self._investigations.facet_counts()
        return FacetsResponse(
            **{
                name: [FacetValue(value=value, count=count) for value, count in entries]
                for name, entries in counts.items()
            }
        )

    def hardware_lineage(self) -> LineageGraph:
        links = self._investigations.hardware_links()
        nodes = [
            LineageNode(
                id=f"{HARDWARE_PREFIX}:{item.name}",
                type="hardware",
                label=item.name,
                kind=item.kind,
            )
            for item in links.hardware
        ]
        nodes += [
            LineageNode(
                id=f"{INVESTIGATION_PREFIX}:{acronym}", type="investigation", label=acronym
            )
            for acronym in links.projects
        ]
        nodes += [
            LineageNode(id=f"{PROJECT_PREFIX}:{name}", type="project", label=name)
            for name in sorted({name for name in links.projects.values() if name})
        ]
        edges = [
            LineageEdge(
                source=f"{INVESTIGATION_PREFIX}:{acronym}",
                target=f"{HARDWARE_PREFIX}:{name}",
                role=role,
            )
            for acronym, name, role in links.links
        ]
        edges += _hosting_edges(links.hardware)
        edges += [
            LineageEdge(
                source=f"{INVESTIGATION_PREFIX}:{acronym}",
                target=f"{PROJECT_PREFIX}:{name}",
                role="member_of",
            )
            for acronym, name in links.projects.items()
            if name
        ]
        return LineageGraph(nodes=nodes, edges=edges)

    def projects(self) -> builtins.list[ProjectOut]:
        return [
            ProjectOut(name=project.name, description=project.description, investigations=members)
            for project, members in self._investigations.projects()
        ]

    def _publications(self, investigation_id: int) -> builtins.list[PublicationOut]:
        return [
            PublicationOut(
                doi=entry.doi,
                title=entry.title,
                authors=list(entry.authors or []),
                year=entry.year,
                venue=entry.venue,
                url=entry.url,
                key_findings=entry.key_findings,
            )
            for entry in self._investigations.publications(investigation_id)
        ]

    @staticmethod
    def _score_order(
        row: InvestigationRow, scores: dict[int, ScoreSet], sort: str
    ) -> tuple[bool, float, str]:
        value = getattr(scores.get(row.investigation.id, ScoreSet()), sort)
        return (value is None, -(value or 0.0), row.investigation.acronym)


def _finding_out(finding: Finding) -> FindingOut:
    return FindingOut.model_validate(
        {
            "id": finding.id,
            "statement": finding.statement,
            "category": finding.category,
            "source": finding.source,
            "confidence": float(finding.confidence),
        }
    )


def _measurement(entry: Measurement) -> MeasurementOut:
    return MeasurementOut(
        instrument=entry.instrument,
        quantity=entry.quantity,
        units=entry.units,
        file_pattern=entry.file_pattern,
        notes=entry.notes,
        source=SourceRef.model_validate(entry.source) if entry.source else None,
    )


def _hosting_edges(hardware: Sequence[Hardware]) -> list[LineageEdge]:
    by_id = {item.id: item.name for item in hardware}
    return [
        LineageEdge(
            source=f"{HARDWARE_PREFIX}:{item.name}",
            target=f"{HARDWARE_PREFIX}:{by_id[item.parent_id]}",
            role="hosted_in",
        )
        for item in hardware
        if item.parent_id in by_id
    ]
