"""Pure scenario maths: distance, coverage, gravity bounding and run matching (doc 08 s4)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence

from flamescope_api.repositories.runs import RunRecord, known_endpoints
from flamescope_api.services.catalog import to_run_item
from flamescope_common.schemas.api import (
    GravityAnalogue,
    GravityBound,
    GravityBounding,
    RangePair,
    ResolvedScenario,
    ScenarioMatch,
    ScenarioWeights,
)
from flamescope_common.schemas.card import CoverageState, acronym_sort_key

EPSILON = 1e-9
MATCHING_SIMILARITY = 0.6
GRAVITY_TOLERANCE = 0.02
MICROGRAVITY_G = 0.0
NORMAL_GRAVITY_G = 1.0
SAME_CLASS_FUEL_DISTANCE = 0.3
PHASE_ONLY_FUEL_DISTANCE = 0.6
WORST_DISTANCE = 1.0
NUMERIC_DIMENSIONS = {"o2": "o2_fraction", "pressure": "pressure_kpa", "flow": "flow_speed_cm_s"}


def _numeric_distance(
    target: float, condition: RunRecord, dimension: str, ranges: Mapping[str, RangePair]
) -> float:
    span = condition.span_of(dimension)
    if span is None:
        return WORST_DISTANCE
    endpoints = known_endpoints(span)
    low, high = ranges.get(dimension, (min(endpoints), max(endpoints)))
    return min(1.0, _gap_to_span(target, span) / max(high - low, EPSILON))


def _gap_to_span(target: float, span: RangePair) -> float:
    """0 inside the span (open sides included), else the distance to the nearest known end."""
    if span[0] <= target <= span[1]:
        return 0.0
    return min(abs(target - endpoint) for endpoint in known_endpoints(span))


def _same(left: str | None, right: str | None) -> bool:
    return left is not None and right is not None and left.lower() == right.lower()


def _fuel_distance(
    scenario: ResolvedScenario, condition: RunRecord, material_class: str | None
) -> float | None:
    if not scenario.material and not scenario.fuel_phase:
        return None
    if condition.fuel_name is None:
        return WORST_DISTANCE
    if _same(scenario.material, condition.fuel_name):
        return 0.0
    if _same(material_class, condition.material_class):
        return SAME_CLASS_FUEL_DISTANCE
    if scenario.fuel_phase and condition.fuel_phase == scenario.fuel_phase:
        return PHASE_ONLY_FUEL_DISTANCE if scenario.material else 0.0
    return WORST_DISTANCE


def dimension_distances(
    scenario: ResolvedScenario,
    condition: RunRecord,
    ranges: Mapping[str, RangePair],
    material_class: str | None = None,
) -> dict[str, float]:
    """Distance 0..1 per dimension the scenario sets (`o2`, `pressure`, `flow`, `fuel`)."""
    distances: dict[str, float] = {}
    for key, dimension in NUMERIC_DIMENSIONS.items():
        target = getattr(scenario, dimension)
        if target is not None:
            distances[key] = _numeric_distance(target, condition, dimension, ranges)
    fuel = _fuel_distance(scenario, condition, material_class)
    if fuel is not None:
        distances["fuel"] = fuel
    return distances


def distance(
    scenario: ResolvedScenario,
    condition: RunRecord,
    ranges: Mapping[str, RangePair],
    weights: ScenarioWeights,
    material_class: str | None = None,
) -> float:
    """Weighted mean of the per-dimension distances; unset dimensions drop out (section 4.2)."""
    distances = dimension_distances(scenario, condition, ranges, material_class)
    weight_of: dict[str, float] = weights.model_dump()
    total_weight = sum(weight_of[key] for key in distances)
    if total_weight <= 0:
        return WORST_DISTANCE
    return sum(weight_of[key] * value for key, value in distances.items()) / total_weight


def coverage(
    scenario: ResolvedScenario,
    ranges: Mapping[str, RangePair],
    gravity_values: Collection[float] = (),
) -> dict[str, CoverageState]:
    """`covered`, `extrapolated` or `no_data` per dimension the scenario sets (section 4.3)."""
    states: dict[str, CoverageState] = {}
    for dimension in NUMERIC_DIMENSIONS.values():
        target = getattr(scenario, dimension)
        if target is None:
            continue
        bounds = ranges.get(dimension)
        if bounds is None:
            states[dimension] = "no_data"
        else:
            states[dimension] = "covered" if bounds[0] <= target <= bounds[1] else "extrapolated"
    if scenario.gravity_g is not None:
        near = any(
            abs(value - scenario.gravity_g) <= GRAVITY_TOLERANCE for value in gravity_values
        )
        states["gravity_g"] = "covered" if near else "no_data"
    return states


def _investigations_at(
    runs: Sequence[RunRecord], gravity: float, only: Collection[str] | None
) -> list[str]:
    return sorted(
        {
            run.investigation
            for run in runs
            if run.gravity_g is not None
            and abs(run.gravity_g - gravity) <= GRAVITY_TOLERANCE
            and (only is None or run.investigation in only)
        }
    )


def _is_reference_gravity(gravity: float) -> bool:
    """0 g and 1 g (within tolerance) are the bounds themselves, not partial gravity."""
    return any(
        abs(gravity - reference) <= GRAVITY_TOLERANCE
        for reference in (MICROGRAVITY_G, NORMAL_GRAVITY_G)
    )


def gravity_bounding(
    scenario: ResolvedScenario,
    runs: Sequence[RunRecord],
    *,
    top_acronyms: Collection[str] | None = None,
    analogue: GravityAnalogue | None = None,
    statement: str | None = None,
) -> GravityBounding:
    """Partial-gravity availability or the 0 g / 1 g bounds among the top matches (4.4)."""
    gravity = scenario.gravity_g
    if gravity is None or _is_reference_gravity(gravity):
        return GravityBounding(partial_gravity_data=False)
    catalog_values = {run.gravity_g for run in runs if run.gravity_g is not None}
    if any(abs(value - gravity) <= GRAVITY_TOLERANCE for value in catalog_values):
        return GravityBounding(partial_gravity_data=MICROGRAVITY_G < gravity < NORMAL_GRAVITY_G)
    return GravityBounding(
        partial_gravity_data=False,
        lower_bound=GravityBound(
            gravity_g=MICROGRAVITY_G,
            investigations=_investigations_at(runs, MICROGRAVITY_G, top_acronyms),
        ),
        upper_bound=GravityBound(
            gravity_g=NORMAL_GRAVITY_G,
            investigations=_investigations_at(runs, NORMAL_GRAVITY_G, top_acronyms),
        ),
        analogue=analogue,
        statement=statement,
    )


def _fuel_traits(
    scenario: ResolvedScenario, runs: Sequence[RunRecord]
) -> tuple[ResolvedScenario, str | None]:
    """Fill the scenario fuel phase and class from the catalog fuel of the same name."""
    if not scenario.material:
        return scenario, None
    for run in runs:
        if _same(scenario.material, run.fuel_name):
            phase = scenario.fuel_phase or run.fuel_phase
            return scenario.model_copy(update={"fuel_phase": phase}), run.material_class
    return scenario, None


def score_runs(
    scenario: ResolvedScenario, runs: Sequence[RunRecord], ranges: Mapping[str, RangePair]
) -> list[tuple[RunRecord, float, dict[str, float]]]:
    """Each run with its similarity and per-dimension similarities."""
    effective, material_class = _fuel_traits(scenario, runs)
    scored = []
    for run in runs:
        per_dimension = dimension_distances(effective, run, ranges, material_class)
        total = distance(effective, run, ranges, scenario.weights, material_class)
        scored.append(
            (run, 1.0 - total, {key: 1.0 - value for key, value in per_dimension.items()})
        )
    return scored


def matching_runs(
    scenario: ResolvedScenario, runs: Sequence[RunRecord], ranges: Mapping[str, RangePair]
) -> list[RunRecord]:
    """Runs whose similarity reaches the matching threshold."""
    return [
        run
        for run, similarity, _ in score_runs(scenario, runs, ranges)
        if similarity >= MATCHING_SIMILARITY
    ]


def rank_matches(
    scenario: ResolvedScenario, runs: Sequence[RunRecord], ranges: Mapping[str, RangePair]
) -> list[ScenarioMatch]:
    """Investigation-level matches sorted by best then median similarity (section 4.2)."""
    grouped: dict[str, list[tuple[RunRecord, float, dict[str, float]]]] = defaultdict(list)
    for entry in score_runs(scenario, runs, ranges):
        grouped[entry[0].investigation].append(entry)
    matches = []
    for acronym, entries in grouped.items():
        best_run, best, per_dimension = max(entries, key=lambda entry: entry[1])
        similarities = [entry[1] for entry in entries]
        matches.append(
            ScenarioMatch(
                acronym=acronym,
                similarity=best,
                best_run=to_run_item(best_run),
                median_similarity=statistics.median(similarities),
                per_dimension=per_dimension,
                matching_runs=sum(1 for value in similarities if value >= MATCHING_SIMILARITY),
            )
        )
    matches.sort(
        key=lambda match: (
            -match.similarity,
            -match.median_similarity,
            acronym_sort_key(match.acronym),
        )
    )
    return matches
