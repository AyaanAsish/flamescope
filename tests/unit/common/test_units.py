"""Unit conversion to canonical units (document 03 section 2 `units.py`; document 08 4.1)."""

from __future__ import annotations

import pytest

from flamescope_common.errors import ValidationError
from flamescope_common.units import (
    cm_s_to_mm_s,
    fraction_to_percent,
    gravity_label_to_g,
    kpa_to_psi,
    mm_s_to_cm_s,
    percent_to_fraction,
    psi_to_kpa,
    to_cm_s,
    to_fraction,
    to_kpa,
)

pytestmark = pytest.mark.unit

KPA_TOLERANCE = 0.1
FLOAT_TOLERANCE = 1e-9


@pytest.mark.parametrize(
    ("psi", "kpa"),
    [(14.7, 101.35), (10.2, 70.3), (8.2, 56.5), (4.3, 29.6)],
)
def test_psi_to_kpa_matches_the_preset_table(psi: float, kpa: float) -> None:
    """FR-07: the psi / kPa pairs of document 08 section 4.1."""
    assert psi_to_kpa(psi) == pytest.approx(kpa, abs=KPA_TOLERANCE)


@pytest.mark.parametrize("kpa", [101.3, 70.3, 56.5, 29.6])
def test_kpa_to_psi_round_trips(kpa: float) -> None:
    """FR-07: the UI kPa / psi toggle is lossless."""
    assert psi_to_kpa(kpa_to_psi(kpa)) == pytest.approx(kpa, abs=FLOAT_TOLERANCE)


@pytest.mark.parametrize(
    ("value", "unit", "kpa"),
    [
        (101325.0, "Pa", 101.325),
        (101.3, "kPa", 101.3),
        (1.0, "atm", 101.325),
        (1.0, "bar", 100.0),
        (760.0, "torr", 101.325),
        (14.7, "psi", 101.35),
    ],
)
def test_to_kpa_converts_named_pressure_units(value: float, unit: str, kpa: float) -> None:
    """FR-07: pressure in any stated unit becomes kPa."""
    assert to_kpa(value, unit) == pytest.approx(kpa, abs=KPA_TOLERANCE)


def test_unknown_pressure_unit_is_rejected() -> None:
    """FR-01: an unparseable unit is a validation error, never a guessed value."""
    with pytest.raises(ValidationError):
        to_kpa(1.0, "furlongs")


@pytest.mark.parametrize(("percent", "fraction"), [(21.0, 0.21), (30.0, 0.30), (100.0, 1.0)])
def test_percent_to_fraction(percent: float, fraction: float) -> None:
    """FR-07: oxygen is stored as a fraction 0 to 1 (document 04 `condition.o2_fraction`)."""
    assert percent_to_fraction(percent) == pytest.approx(fraction)
    assert fraction_to_percent(fraction) == pytest.approx(percent)


@pytest.mark.parametrize(
    ("value", "unit", "fraction"),
    [(0.34, "fraction", 0.34), (34.0, "%", 0.34), (34.0, "percent", 0.34)],
)
def test_to_fraction_accepts_fraction_and_percent(
    value: float, unit: str, fraction: float
) -> None:
    """FR-07: concentrations given as fraction or percent become a fraction."""
    assert to_fraction(value, unit) == pytest.approx(fraction)


def test_unknown_concentration_unit_is_rejected() -> None:
    """FR-01: an unknown concentration unit is not silently accepted."""
    with pytest.raises(ValidationError):
        to_fraction(1.0, "ppm-ish")


@pytest.mark.parametrize(
    ("value", "unit", "cm_s"),
    [(10.0, "mm/s", 1.0), (5.0, "cm/s", 5.0), (0.5, "m/s", 50.0)],
)
def test_flow_units_convert_to_cm_per_second(value: float, unit: str, cm_s: float) -> None:
    """FR-07: flow speed is stored in cm/s (document 04 `condition.flow_speed_cm_s`)."""
    assert to_cm_s(value, unit) == pytest.approx(cm_s)


def test_mm_and_cm_per_second_helpers_are_inverse() -> None:
    """FR-06: spread rates in mm/s and flow speeds in cm/s convert both ways."""
    assert mm_s_to_cm_s(55.0) == pytest.approx(5.5)
    assert cm_s_to_mm_s(5.5) == pytest.approx(55.0)


def test_unknown_speed_unit_is_rejected() -> None:
    """FR-01: an unknown speed unit raises."""
    with pytest.raises(ValidationError):
        to_cm_s(1.0, "knots")


@pytest.mark.parametrize(
    ("label", "gravity_g"),
    [
        ("microgravity", 0.0),
        ("normal gravity", 1.0),
        ("Normal", 1.0),
        ("lunar", 0.166),
        ("Mars", 0.38),
        ("0.166 g", 0.166),
        ("0.38g", 0.38),
    ],
)
def test_gravity_labels_map_to_g(label: str, gravity_g: float) -> None:
    """FR-16: gravity labels map to g; lunar 0.166 and Mars 0.38 (document 08 section 4.1)."""
    assert gravity_label_to_g(label) == pytest.approx(gravity_g)


def test_unrecognized_gravity_label_is_unknown() -> None:
    """FR-01: unknown is null, never guessed."""
    assert gravity_label_to_g("somewhere in orbit") is None
