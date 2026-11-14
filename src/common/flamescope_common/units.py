"""Unit conversion to the canonical units: kPa, fraction 0-1, cm/s, g (document 05 section 1)."""

from __future__ import annotations

import re

from flamescope_common.errors import ValidationError

PA_PER_PSI = 6894.757293168361
PA_PER_KPA = 1000.0
PA_PER_ATM = 101325.0
PA_PER_BAR = 100000.0
PA_PER_TORR = PA_PER_ATM / 760.0
PERCENT_PER_FRACTION = 100.0
MM_PER_CM = 10.0
CM_PER_M = 100.0
LUNAR_GRAVITY_G = 0.166
MARS_GRAVITY_G = 0.38

_PASCALS_PER_UNIT: dict[str, float] = {
    "pa": 1.0,
    "kpa": PA_PER_KPA,
    "mpa": PA_PER_KPA * PA_PER_KPA,
    "psi": PA_PER_PSI,
    "atm": PA_PER_ATM,
    "bar": PA_PER_BAR,
    "torr": PA_PER_TORR,
    "mmhg": PA_PER_TORR,
}
_CM_PER_S_PER_UNIT: dict[str, float] = {
    "mm/s": 1.0 / MM_PER_CM,
    "cm/s": 1.0,
    "m/s": CM_PER_M,
}
_NAMED_GRAVITY_G: dict[str, float] = {
    "microgravity": 0.0,
    "zero gravity": 0.0,
    "weightlessness": 0.0,
    "normal gravity": 1.0,
    "normal": 1.0,
    "earth": 1.0,
    "terrestrial": 1.0,
    "lunar": LUNAR_GRAVITY_G,
    "moon": LUNAR_GRAVITY_G,
    "mars": MARS_GRAVITY_G,
}
_GRAVITY_NUMBER = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*g\s*$", re.IGNORECASE)
_FRACTION_UNITS = {"", "fraction", "frac", "mole fraction", "vol fraction"}
_PERCENT_UNITS = {"%", "percent", "pct", "vol%", "% o2", "%o2"}


def _lookup(table: dict[str, float], unit: str, kind: str) -> float:
    factor = table.get(unit.strip().lower())
    if factor is None:
        raise ValidationError(f"Unknown {kind} unit {unit!r}", {"unit": unit})
    return factor


def psi_to_kpa(value: float) -> float:
    return value * PA_PER_PSI / PA_PER_KPA


def kpa_to_psi(value: float) -> float:
    return value * PA_PER_KPA / PA_PER_PSI


def to_kpa(value: float, unit: str) -> float:
    """Convert a pressure in Pa, kPa, MPa, psi, atm, bar, torr or mmHg to kPa."""
    return value * _lookup(_PASCALS_PER_UNIT, unit, "pressure") / PA_PER_KPA


def percent_to_fraction(value: float) -> float:
    return value / PERCENT_PER_FRACTION


def fraction_to_percent(value: float) -> float:
    return value * PERCENT_PER_FRACTION


def to_fraction(value: float, unit: str) -> float:
    """Convert a concentration given as a fraction or a percent to a fraction 0-1."""
    key = unit.strip().lower()
    if key in _FRACTION_UNITS:
        return value
    if key in _PERCENT_UNITS:
        return percent_to_fraction(value)
    raise ValidationError(f"Unknown concentration unit {unit!r}", {"unit": unit})


def mm_s_to_cm_s(value: float) -> float:
    return value / MM_PER_CM


def cm_s_to_mm_s(value: float) -> float:
    return value * MM_PER_CM


def to_cm_s(value: float, unit: str) -> float:
    """Convert a speed in mm/s, cm/s or m/s to cm/s."""
    return value * _lookup(_CM_PER_S_PER_UNIT, unit, "speed")


def gravity_label_to_g(label: str) -> float | None:
    """Map a gravity label ("microgravity", "lunar", "0.166 g") to g; None when not recognized."""
    key = label.strip().lower()
    if key in _NAMED_GRAVITY_G:
        return _NAMED_GRAVITY_G[key]
    match = _GRAVITY_NUMBER.match(key)
    return float(match.group(1)) if match else None
