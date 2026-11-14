"""FR-01: stage 5, normalize (document 06 section 3.5; aggregate runs, document 08 s4.2).

Fuel names through the taxonomy, tags restricted to the vocabulary, one aggregate run per
fuel when no test matrix exists, and no unit conversion.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError as SchemaValidationError

from flamescope_ingest.normalizer import Normalizer, card_json, derive_columns
from flamescope_ingest.seed import FuelTaxonomy

pytestmark = pytest.mark.unit

CardFactory = Callable[..., dict[str, Any]]
FuelFactory = Callable[..., dict[str, Any]]
AGGREGATE_DIMENSIONS = ("o2_fraction", "pressure_kpa", "flow_speed_cm_s")


@pytest.fixture
def normalizer(taxonomy: FuelTaxonomy) -> Normalizer:
    return Normalizer(taxonomy)


@pytest.fixture
def ranged_conditions(source: dict[str, str]) -> dict[str, Any]:
    """Synthetic stated ranges; pressure is a single stated value."""
    return {
        "o2_fraction": {"min": 0.2, "max": 0.4, "source": dict(source)},
        "pressure_kpa": {"min": 50.0, "max": 50.0, "source": dict(source)},
        "flow_speed_cm_s": {"min": 2.0, "max": 8.0, "source": dict(source)},
        "flow_direction": ["opposed"],
        "gravity_g": [0],
    }


def _run(source: dict[str, str], label: str, **condition: Any) -> dict[str, Any]:
    return {
        "label": label,
        "fuel": "acrylic",
        "condition": condition,
        "confidence": 0.9,
        "source": dict(source),
    }


def test_unknown_tags_are_dropped_and_reported(
    normalizer: Normalizer, make_card: CardFactory
) -> None:
    """Document 06 section 3.5: unknown tags dropped and reported."""
    result = normalizer.normalize(
        make_card(fire_safety_tags=["flame_spread", "made_up", "soot", "flame_spread"])
    )
    assert result.record.fire_safety_tags == ["flame_spread", "soot"]
    assert result.notes.dropped_tags == ["made_up"]


def test_fuel_alias_mapped_to_canonical_name(
    normalizer: Normalizer, make_card: CardFactory, make_fuel: FuelFactory
) -> None:
    """Fuel names and classes mapped through `fuel_taxonomy.yaml`."""
    result = normalizer.normalize(make_card(fuels=[make_fuel("Acrylic")]))
    fuel = result.record.fuels[0]
    assert fuel.name == "PMMA"
    assert fuel.material_class == "polymer"
    assert result.notes.renamed_fuels == {"Acrylic": "PMMA"}


def test_stated_material_class_is_kept(
    normalizer: Normalizer, make_card: CardFactory, make_fuel: FuelFactory
) -> None:
    result = normalizer.normalize(
        make_card(fuels=[make_fuel("PMMA", material_class="thermoplastic")])
    )
    assert result.record.fuels[0].material_class == "thermoplastic"


def test_unknown_fuel_name_is_left_unchanged(
    normalizer: Normalizer, make_card: CardFactory, make_fuel: FuelFactory
) -> None:
    result = normalizer.normalize(make_card(fuels=[make_fuel("Unlisted fuel")]))
    assert result.record.fuels[0].name == "Unlisted fuel"
    assert result.record.fuels[0].material_class is None
    assert result.notes.renamed_fuels == {}


def test_explicit_runs_are_kept_with_canonical_fuel(
    normalizer: Normalizer,
    make_card: CardFactory,
    make_fuel: FuelFactory,
    source: dict[str, str],
) -> None:
    """One run per explicit test point when a test matrix exists."""
    runs = [_run(source, "P1", o2_fraction=0.3), _run(source, "P2", o2_fraction=0.35)]
    result = normalizer.normalize(make_card(fuels=[make_fuel("PMMA")], runs=runs))
    assert [run.label for run in result.record.runs] == ["P1", "P2"]
    assert all(run.fuel == "PMMA" and not run.is_aggregate for run in result.record.runs)
    assert result.notes.aggregate_runs == 0


def test_one_aggregate_run_per_fuel_without_test_matrix(
    normalizer: Normalizer,
    make_card: CardFactory,
    make_fuel: FuelFactory,
    ranged_conditions: dict[str, Any],
) -> None:
    """Otherwise one aggregate run per fuel with range endpoints (`is_aggregate=true`)."""
    card = make_card(
        fuels=[make_fuel("PMMA"), make_fuel("n-heptane", phase="liquid")],
        conditions=ranged_conditions,
    )
    result = normalizer.normalize(card)
    runs = result.record.runs
    assert [run.fuel for run in runs] == ["PMMA", "n-heptane"]
    assert all(run.is_aggregate for run in runs)
    assert result.notes.aggregate_runs == len(runs)


def test_aggregate_run_follows_range_convention(
    normalizer: Normalizer,
    make_card: CardFactory,
    make_fuel: FuelFactory,
    ranged_conditions: dict[str, Any],
) -> None:
    """Document 08 s4.2: `varied_parameters[d] = {min, max}`; condition is midpoint or null."""
    card = make_card(fuels=[make_fuel("PMMA")], conditions=ranged_conditions)
    run = normalizer.normalize(card).record.runs[0]
    for dimension in AGGREGATE_DIMENSIONS:
        stated = ranged_conditions[dimension]
        assert run.varied_parameters[dimension] == {"min": stated["min"], "max": stated["max"]}
        value = getattr(run.condition, dimension)
        assert value is None or value == pytest.approx((stated["min"] + stated["max"]) / 2)
    assert run.source is not None


def test_half_open_range_keeps_its_null_endpoint(
    normalizer: Normalizer,
    make_card: CardFactory,
    make_fuel: FuelFactory,
    source: dict[str, str],
) -> None:
    """Docs 04 s2, 06 s3.5, 08 s4.2: the null endpoint stays null in runs and derived columns."""
    conditions = {"o2_fraction": {"min": None, "max": 0.85, "source": dict(source)}}
    card = make_card(fuels=[make_fuel("PMMA")], conditions=conditions)
    record = normalizer.normalize(card).record
    derived = derive_columns(record)
    observed = (
        record.runs[0].varied_parameters,
        record.runs[0].condition.o2_fraction,
        (derived["o2_min"], derived["o2_max"]),
    )
    assert observed == (
        {"o2_fraction": {"min": None, "max": 0.85}},
        None,
        (None, Decimal("0.85")),
    )


def test_half_open_range_stays_open_beside_run_points(
    normalizer: Normalizer,
    make_card: CardFactory,
    make_fuel: FuelFactory,
    source: dict[str, str],
) -> None:
    """Doc 04 s2: an open side stays open (null) when explicit runs lie inside the range."""
    conditions = {"o2_fraction": {"min": 0.21, "max": None, "source": dict(source)}}
    runs = [_run(source, "P1", o2_fraction=0.3), _run(source, "P2", o2_fraction=0.5)]
    card = make_card(fuels=[make_fuel("PMMA")], conditions=conditions, runs=runs)
    derived = derive_columns(normalizer.normalize(card).record)
    assert (derived["o2_min"], derived["o2_max"]) == (Decimal("0.21"), None)


def test_no_fuels_and_no_runs_gives_no_runs(
    normalizer: Normalizer, make_card: CardFactory
) -> None:
    assert normalizer.normalize(make_card()).record.runs == []


def test_values_are_not_unit_converted(
    normalizer: Normalizer,
    make_card: CardFactory,
    make_fuel: FuelFactory,
    source: dict[str, str],
) -> None:
    """Values already arrive in canonical units; the normalizer converts nothing."""
    run = _run(source, "P1", o2_fraction=0.34, pressure_kpa=56.5, flow_speed_cm_s=10.0)
    record = normalizer.normalize(make_card(fuels=[make_fuel("PMMA")], runs=[run])).record
    condition = record.runs[0].condition
    assert (condition.o2_fraction, condition.pressure_kpa, condition.flow_speed_cm_s) == (
        0.34,
        56.5,
        10.0,
    )


def test_input_mapping_is_not_mutated(
    normalizer: Normalizer, make_card: CardFactory, make_fuel: FuelFactory
) -> None:
    card = make_card(fuels=[make_fuel("acrylic")], fire_safety_tags=["made_up"])
    normalizer.normalize(card)
    assert card["fuels"][0]["name"] == "acrylic"
    assert card["fire_safety_tags"] == ["made_up"]


def test_invalid_card_is_rejected(normalizer: Normalizer, make_card: CardFactory) -> None:
    """Output must validate as a card: a fuel without a source is not accepted."""
    with pytest.raises(SchemaValidationError):
        normalizer.normalize(make_card(fuels=[{"name": "PMMA", "phase": "solid"}]))


def test_card_json_holds_only_card_fields(normalizer: Normalizer, make_card: CardFactory) -> None:
    """`investigation.card` stores the `InvestigationCard` (document 04 section 4)."""
    stored = card_json(normalizer.normalize(make_card(summary="Synthetic.")).record)
    assert stored["acronym"] == "TEST-1"
    assert not {"psi_url", "summary", "runs", "scores", "documents", "reviewed"} & set(stored)


def test_derive_columns_from_stated_ranges_and_runs(
    normalizer: Normalizer,
    make_card: CardFactory,
    make_fuel: FuelFactory,
    ranged_conditions: dict[str, Any],
    source: dict[str, str],
) -> None:
    """Document 04 section 2: `fuel_phases` and o2/pressure/flow min-max derived columns."""
    runs = [_run(source, "P1", o2_fraction=0.5, pressure_kpa=40.0)]
    card = make_card(
        fuels=[make_fuel("PMMA"), make_fuel("n-heptane", phase="liquid")],
        conditions=ranged_conditions,
        runs=runs,
    )
    derived = derive_columns(normalizer.normalize(card).record)
    assert derived["fuel_phases"] == ["liquid", "solid"]
    assert (derived["o2_min"], derived["o2_max"]) == (Decimal("0.2"), Decimal("0.5"))
    assert (derived["pressure_min_kpa"], derived["pressure_max_kpa"]) == (
        Decimal("40.0"),
        Decimal("50.0"),
    )
    assert (derived["flow_min_cm_s"], derived["flow_max_cm_s"]) == (Decimal("2.0"), Decimal("8.0"))


def test_derive_columns_unknown_stays_null(normalizer: Normalizer, make_card: CardFactory) -> None:
    """Unknown is null, never guessed (document 04 section 4)."""
    derived = derive_columns(normalizer.normalize(make_card()).record)
    assert derived["fuel_phases"] == []
    assert all(derived[column] is None for column in ("o2_min", "o2_max", "flow_max_cm_s"))
