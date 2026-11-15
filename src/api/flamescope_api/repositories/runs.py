"""`RunRepo`: test runs with their condition and fuel, as flat `RunRecord` rows."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from flamescope_api.repositories import ACRONYM_ORDER, to_float
from flamescope_common.models import Condition, Fuel, Investigation, TestRun
from flamescope_common.schemas.api import ExtractFilters, RangePair
from flamescope_common.schemas.card import RunOutcome

CONDITION_DIMENSIONS = ("o2_fraction", "pressure_kpa", "flow_speed_cm_s")
OUTCOME_KEYS = frozenset(RunOutcome.model_fields)


@dataclass(frozen=True)
class RunRecord:
    """One run with its condition columns, fuel, outcome and provenance."""

    run_id: int = 0
    investigation_id: int = 0
    investigation: str = ""
    label: str = ""
    fuel_name: str | None = None
    fuel_phase: str | None = None
    material_class: str | None = None
    geometry: dict[str, Any] = field(default_factory=dict)
    varied_parameters: dict[str, Any] = field(default_factory=dict)
    fixed_parameters: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    is_aggregate: bool = False
    o2_fraction: float | None = None
    diluent: str | None = None
    pressure_kpa: float | None = None
    flow_speed_cm_s: float | None = None
    flow_direction: str | None = None
    gravity_g: float | None = None
    e_field_kv: float | None = None
    temperature_k: float | None = None

    def value_of(self, dimension: str) -> float | None:
        """The condition value of a dimension (`o2_fraction`, `pressure_kpa`, ...)."""
        value: float | None = getattr(self, dimension)
        return value

    def range_of(self, dimension: str) -> RangePair | None:
        """The stated range of an aggregate run (`varied_parameters[dim] = {min, max}`).

        A half-open range is open on the missing side (document 08 section 4.2), so a null
        endpoint becomes minus or plus infinity.
        """
        if not self.is_aggregate:
            return None
        stated = self.varied_parameters.get(dimension)
        if not isinstance(stated, dict):
            return None
        low, high = _number(stated.get("min")), _number(stated.get("max"))
        if low is None and high is None:
            return None
        return (-math.inf if low is None else low, math.inf if high is None else high)

    def span_of(self, dimension: str) -> RangePair | None:
        """The aggregate range when stated, else the single condition value as a point."""
        stated = self.range_of(dimension)
        if stated is not None:
            return stated
        value = self.value_of(dimension)
        return None if value is None else (value, value)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def known_endpoints(span: RangePair | None) -> list[float]:
    """The finite endpoints of a span; the open side of a half-open range has none."""
    return [] if span is None else [endpoint for endpoint in span if math.isfinite(endpoint)]


def ranges_from_records(records: Iterable[RunRecord]) -> dict[str, RangePair]:
    """Catalog range per dimension over all runs, widened only by known range endpoints."""
    ranges: dict[str, RangePair] = {}
    for record in records:
        for dimension in CONDITION_DIMENSIONS:
            for endpoint in known_endpoints(record.span_of(dimension)):
                low, high = ranges.get(dimension, (endpoint, endpoint))
                ranges[dimension] = (min(low, endpoint), max(high, endpoint))
    return ranges


def _filter_clauses(filters: ExtractFilters) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.investigations:
        wanted = [name.lower() for name in filters.investigations]
        clauses.append(func.lower(Investigation.acronym).in_(wanted))
    if filters.fuel_phase:
        clauses.append(Fuel.phase.in_(list(filters.fuel_phase)))
    bounds = (
        (Condition.o2_fraction, filters.o2_min, filters.o2_max),
        (Condition.pressure_kpa, filters.pressure_min_kpa, filters.pressure_max_kpa),
    )
    for column, low, high in bounds:
        if low is not None:
            clauses.append(column >= low)
        if high is not None:
            clauses.append(column <= high)
    for key in filters.has_outcome:
        if key in OUTCOME_KEYS:
            clauses.append(TestRun.outcome[key].astext.is_not(None))
    return clauses


class RunRepo:
    """Read access to test runs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def for_investigation(self, investigation_id: int) -> list[RunRecord]:
        return self._records([TestRun.investigation_id == investigation_id])

    def query(self, filters: ExtractFilters | None = None) -> list[RunRecord]:
        """Runs matching the extract filters (`scenario_id` is resolved by the service)."""
        return self._records(_filter_clauses(filters) if filters else [])

    def condition_ranges(self) -> dict[str, RangePair]:
        return ranges_from_records(self._records([]))

    def _records(self, clauses: Sequence[ColumnElement[bool]]) -> list[RunRecord]:
        statement = (
            select(TestRun, Investigation.acronym, Fuel, Condition)
            .join(Investigation, Investigation.id == TestRun.investigation_id)
            .outerjoin(Fuel, Fuel.id == TestRun.fuel_id)
            .outerjoin(Condition, Condition.test_run_id == TestRun.id)
            .where(*clauses)
            .order_by(*ACRONYM_ORDER, TestRun.id)
        )
        return [
            _to_record(run, acronym, fuel, condition)
            for run, acronym, fuel, condition in self._session.execute(statement)
        ]


def _to_record(
    run: TestRun, acronym: str, fuel: Fuel | None, condition: Condition | None
) -> RunRecord:
    return RunRecord(
        run_id=run.id,
        investigation_id=run.investigation_id,
        investigation=acronym,
        label=run.label,
        fuel_name=fuel.name if fuel else None,
        fuel_phase=fuel.phase if fuel else None,
        material_class=fuel.material_class if fuel else None,
        geometry=run.geometry,
        varied_parameters=run.varied_parameters,
        fixed_parameters=run.fixed_parameters,
        outcome=run.outcome,
        source=run.source,
        confidence=float(run.confidence),
        is_aggregate=run.is_aggregate,
        **_condition_fields(condition),
    )


def _condition_fields(condition: Condition | None) -> dict[str, Any]:
    if condition is None:
        return {}
    return {
        "o2_fraction": to_float(condition.o2_fraction),
        "diluent": condition.diluent,
        "pressure_kpa": to_float(condition.pressure_kpa),
        "flow_speed_cm_s": to_float(condition.flow_speed_cm_s),
        "flow_direction": condition.flow_direction,
        "gravity_g": to_float(condition.gravity_g),
        "e_field_kv": to_float(condition.e_field_kv),
        "temperature_k": to_float(condition.temperature_k),
    }
