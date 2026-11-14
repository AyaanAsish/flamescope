"""Stage 5, normalize: fuel taxonomy, tag vocabulary and run rows (document 06 section 3.5).

Cards already use canonical units: the extractor and seed schemas name canonical-unit fields
(`pressure_kpa`, `o2_fraction`, `flow_speed_cm_s`), so no value conversion happens here; the
parser records the units found in table headers and the original wording stays in `source.quote`.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, get_args

from flamescope_common.schemas.card import (
    CardFuel,
    FireSafetyTag,
    InvestigationCard,
    RunCondition,
    SeedInvestigation,
    SeedRun,
    ValueRange,
)
from flamescope_ingest.seed import FuelTaxonomy

TAG_VOCABULARY = frozenset(get_args(FireSafetyTag))
FALLBACK_AGGREGATE_CONFIDENCE = 0.3
CONDITIONS_CONFIDENCE_KEY = "conditions"
RANGE_DIMENSIONS: dict[str, tuple[str, str]] = {
    "o2_fraction": ("o2_min", "o2_max"),
    "pressure_kpa": ("pressure_min_kpa", "pressure_max_kpa"),
    "flow_speed_cm_s": ("flow_min_cm_s", "flow_max_cm_s"),
}
CARD_FIELDS = (
    "schema_version",
    "acronym",
    "title",
    "project",
    "platform",
    "gravity_level",
    "hardware",
    "objectives",
    "approach",
    "fuels",
    "conditions",
    "variables",
    "measurements",
    "findings",
    "publications",
    "fire_safety_tags",
    "data",
    "field_confidence",
    "open_questions",
)


@dataclass
class NormalizationNotes:
    """What normalization changed, for the ingest report."""

    dropped_tags: list[str] = field(default_factory=list)
    renamed_fuels: dict[str, str] = field(default_factory=dict)
    aggregate_runs: int = 0


@dataclass
class NormalizedCard:
    record: SeedInvestigation
    notes: NormalizationNotes


def _range_bounds(value_range: ValueRange | None) -> dict[str, float | None] | None:
    if value_range is None or (value_range.min is None and value_range.max is None):
        return None
    return {"min": value_range.min, "max": value_range.max}


def _single_value(value_range: ValueRange | None) -> float | None:
    if value_range is None or value_range.min != value_range.max:
        return None
    return value_range.min


def _varied_ranges(card: InvestigationCard) -> dict[str, Any]:
    conditions = card.conditions
    if conditions is None:
        return {}
    ranges: dict[str, Any] = {
        "o2_fraction": _range_bounds(conditions.o2_fraction),
        "pressure_kpa": _range_bounds(conditions.pressure_kpa),
        "flow_speed_cm_s": _range_bounds(conditions.flow_speed_cm_s),
    }
    if conditions.gravity_g:
        ranges["gravity_g"] = {"min": min(conditions.gravity_g), "max": max(conditions.gravity_g)}
    return {dimension: bounds for dimension, bounds in ranges.items() if bounds is not None}


def _aggregate_condition(card: InvestigationCard) -> RunCondition:
    conditions = card.conditions
    if conditions is None:
        return RunCondition()
    only_gravity = set(conditions.gravity_g)
    only_direction = set(conditions.flow_direction)
    return RunCondition(
        o2_fraction=_single_value(conditions.o2_fraction),
        pressure_kpa=_single_value(conditions.pressure_kpa),
        flow_speed_cm_s=_single_value(conditions.flow_speed_cm_s),
        flow_direction=next(iter(only_direction)) if len(only_direction) == 1 else None,
        gravity_g=next(iter(only_gravity)) if len(only_gravity) == 1 else None,
    )


def _aggregate_run(fuel: CardFuel, card: InvestigationCard) -> SeedRun:
    """One run per fuel; the stated ranges live in `varied_parameters` (document 04 / DC-05)."""
    confidence = card.field_confidence.get(
        CONDITIONS_CONFIDENCE_KEY, FALLBACK_AGGREGATE_CONFIDENCE
    )
    return SeedRun(
        label=f"{fuel.name} (aggregate)",
        fuel=fuel.name,
        geometry=fuel.geometry,
        condition=_aggregate_condition(card),
        varied_parameters=_varied_ranges(card),
        is_aggregate=True,
        confidence=confidence,
        source=fuel.source,
    )


def aggregate_runs(card: InvestigationCard) -> list[SeedRun]:
    return [_aggregate_run(fuel, card) for fuel in card.fuels]


class Normalizer:
    """Turns a raw seed or draft mapping into a validated `SeedInvestigation`."""

    def __init__(self, taxonomy: FuelTaxonomy) -> None:
        self._taxonomy = taxonomy

    def normalize(self, raw: Mapping[str, Any]) -> NormalizedCard:
        working = copy.deepcopy(dict(raw))
        notes = NormalizationNotes()
        self._restrict_tags(working, notes)
        self._canonical_fuel_names(working, notes)
        record = SeedInvestigation.model_validate(working)
        if not record.runs and record.fuels:
            record = record.model_copy(update={"runs": aggregate_runs(record)})
            notes.aggregate_runs = len(record.runs)
        return NormalizedCard(record=record, notes=notes)

    @staticmethod
    def _restrict_tags(working: dict[str, Any], notes: NormalizationNotes) -> None:
        kept: list[str] = []
        for tag in working.get("fire_safety_tags") or []:
            if tag not in TAG_VOCABULARY:
                notes.dropped_tags.append(str(tag))
            elif tag not in kept:
                kept.append(tag)
        working["fire_safety_tags"] = kept

    def _canonical_fuel_names(self, working: dict[str, Any], notes: NormalizationNotes) -> None:
        for fuel in working.get("fuels") or []:
            self._canonicalize(fuel, "name", notes)
            entry = self._taxonomy.resolve(fuel["name"])
            if entry is not None and not fuel.get("material_class"):
                fuel["material_class"] = entry.material_class
        for run in working.get("runs") or []:
            if run.get("fuel"):
                self._canonicalize(run, "fuel", notes)

    def _canonicalize(self, holder: dict[str, Any], key: str, notes: NormalizationNotes) -> None:
        entry = self._taxonomy.resolve(holder[key])
        if entry is not None and entry.name != holder[key]:
            notes.renamed_fuels[holder[key]] = entry.name
            holder[key] = entry.name


def to_decimal(value: float | None) -> Decimal | None:
    """Exact decimal from a float's shortest repr, so repeated loads compare equal."""
    return None if value is None else Decimal(str(value))


def card_json(record: SeedInvestigation) -> dict[str, Any]:
    """The `InvestigationCard` part of a seed record, as stored in `investigation.card`."""
    return record.model_dump(mode="json", include=set(CARD_FIELDS))


Span = tuple[float | None, float | None]


def _outer(ends: list[float | None], pick: Callable[[list[float]], float]) -> float | None:
    """The outermost end; any open (null) end keeps the union open on that side."""
    known = [end for end in ends if end is not None]
    return None if len(known) < len(ends) else pick(known)


def _union(spans: Iterable[Span]) -> Span:
    """Extent of the spans; a null end is open (doc 04 s2) and stays null in the union."""
    collected = list(spans)
    if not collected:
        return (None, None)
    return (
        _outer([low for low, _ in collected], min),
        _outer([high for _, high in collected], max),
    )


def _span(low: float | None, high: float | None) -> Span | None:
    """A range as a span; both ends null is no stated range."""
    return None if low is None and high is None else (low, high)


def _varied_span(value: Any) -> Span | None:
    return _span(value.get("min"), value.get("max")) if isinstance(value, dict) else None


def _dimension_spans(record: SeedInvestigation, dimension: str) -> list[Span]:
    stated = getattr(record.conditions, dimension, None) if record.conditions else None
    candidates: list[Span | None] = [_span(stated.min, stated.max) if stated else None]
    for run in record.runs:
        point = getattr(run.condition, dimension)
        candidates.append(None if point is None else (point, point))
        candidates.append(_varied_span(run.varied_parameters.get(dimension)))
    return [span for span in candidates if span is not None]


def derive_columns(record: SeedInvestigation) -> dict[str, Any]:
    """`fuel_phases` and the range columns, recomputed from fuels, stated ranges and runs."""
    derived: dict[str, Any] = {"fuel_phases": sorted({fuel.phase for fuel in record.fuels})}
    for dimension, (low_column, high_column) in RANGE_DIMENSIONS.items():
        low, high = _union(_dimension_spans(record, dimension))
        derived[low_column] = to_decimal(low)
        derived[high_column] = to_decimal(high)
    return derived
