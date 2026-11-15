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
    acronym_sort_key,
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


def _range_or_point(stated: JsonValue) -> JsonValue:
    """A stated `{min, max}` as a range; equal endpoints are one value, two nulls none."""
    if not isinstance(stated, dict):
        return stated
    low, high = stated.get("min"), stated.get("max")
    if low is None and high is None:
        return None
    return low if low == high else {"min": low, "max": high}


def _run_value(run: RunRecord, name: str) -> JsonValue:
    """The stated range of an aggregate run replaces its condition midpoint (doc 08 s4.2)."""
    if run.range_of(name) is None:
        return run.value_of(name)
    return _range_or_point(run.varied_parameters[name])


def _stated_values(stated: JsonValue) -> builtins.list[JsonValue]:
    return [_range_or_point(value) for value in (stated if isinstance(stated, list) else [stated])]


def _add_observed(
    observed: dict[str, builtins.list[JsonValue]], name: str, value: JsonValue
) -> None:
    if value is not None and not any(_same(value, known) for known in observed.get(name, [])):
        observed.setdefault(name, []).append(value)


def _observed_values(runs: Sequence[RunRecord]) -> dict[str, builtins.list[JsonValue]]:
    """Distinct values per parameter: condition columns (or aggregate ranges), other
    `varied_parameters` keys."""
    observed: dict[str, builtins.list[JsonValue]] = {}
    for run in runs:
        for name in CONDITION_UNITS:
            _add_observed(observed, name, _run_value(run, name))
        extra = {k: v for k, v in run.varied_parameters.items() if k not in CONDITION_UNITS}
        for name, stated in extra.items():
            for value in _stated_values(stated):
                _add_observed(observed, name, value)
    return observed


def _is_varied(values: builtins.list[JsonValue]) -> bool:
    """Several distinct values, or one stated range that spans more than a point (FR-06)."""
    return len(values) > 1 or any(isinstance(value, dict) for value in values)


def derive_variables(runs: Sequence[RunRecord], declared: CardVariables) -> VariablesResponse:
    """Split parameters into varied and fixed (one point value), FR-06, document 05 s4."""
    observed = _observed_values(runs)
    varied = [
        VariedParameter(name=name, values=_ordered(values), unit=CONDITION_UNITS.get(name))
        for name, values in observed.items()
        if _is_varied(values)
    ]
    fixed = [
        FixedParameter(name=name, value=values[0], unit=CONDITION_UNITS.get(name))
        for name, values in observed.items()
        if not _is_varied(values)
    ]
    varied += [VariedParameter(name=name) for name in declared.varied if name not in observed]
    fixed += [FixedParameter(name=name) for name in declared.fixed if name not in observed]
    return VariablesResponse(varied=varied, fixed=fixed, run_count=len(runs))


def _same(left: JsonValue, right: JsonValue) -> bool:
    if isinstance(left, float | int) and isinstance(right, float | int):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)
    return left == right


def _span_key(value: JsonValue) -> tuple[float, float]:
    """Points sort by value, ranges by their low then high end; an open end is infinite."""
    if isinstance(value, dict):
        low, high = value.get("min"), value.get("max")
        return (
            -math.inf if not isinstance(low, float | int) else float(low),
            math.inf if not isinstance(high, float | int) else float(high),
        )
    number = float(value) if isinstance(value, float | int) else 0.0
    return (number, number)


def _is_number_or_range(value: JsonValue) -> bool:
    return isinstance(value, dict) or (
        isinstance(value, float | int) and not isinstance(value, bool)
    )


def _ordered(values: list[JsonValue]) -> list[JsonValue]:
    if all(_is_number_or_range(value) for value in values):
        return sorted(values, key=_span_key)
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
    ) -> tuple[bool, float, tuple[str, str]]:
        value = getattr(scores.get(row.investigation.id, ScoreSet()), sort)
        return (value is None, -(value or 0.0), acronym_sort_key(row.investigation.acronym))


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
