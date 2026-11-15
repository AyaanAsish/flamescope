"""Scenario Lab (document 12 section 2; document 05 section 7; document 08 section 4).

Requirements: FR-07 (closest runs, per-dimension coverage, gravity bounding), FR-16 (the
partial-gravity gap and the E-FIELD Flames analogue). Call flow: CF-07 (Scenario Lab; one
scenario-interpreter call for `explain=true`).
"""

from __future__ import annotations

import base64
import json
import math
import re
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(14)]

Rows = Callable[..., list[dict[str, Any]]]
DOC_08 = "08-scoring-and-scenario.md"
NUMBER = re.compile(r"\d+(?:\.\d+)?")
NUMERIC_DIMENSIONS = {"o2_fraction": "o2", "pressure_kpa": "pressure", "flow_speed_cm_s": "flow"}
GRAVITY_TOLERANCE = 0.02
LUNAR_GRAVITY = 0.166
MARS_GRAVITY = 0.38
ANALOGUE_ACRONYM = "E-FIELD-Flames"  # doc 06 s5 key of "E-FIELD Flames"
ASSUMED_DEFAULT_PRESETS = {"lunar_habitat", "mars_habitat"}
SIMILARITY_TOLERANCE = 0.001
EPSILON = 1e-9
INSIDE_FRACTION = 0.5
OUTSIDE_MARGIN = 1.0
# Doc 05 s1: oxygen is a fraction 0 to 1; pressure and flow are non-negative.
REQUEST_BOUNDS = {
    "o2_fraction": (0.0, 1.0),
    "pressure_kpa": (0.0, math.inf),
    "flow_speed_cm_s": (0.0, math.inf),
}
# Condition values plus the known endpoints of aggregate-run ranges (doc 08 s4.2).
CATALOG_VALUES = (
    "SELECT c.{dimension} AS v FROM condition c WHERE c.{dimension} IS NOT NULL "
    "UNION ALL SELECT (t.varied_parameters -> '{dimension}' ->> e)::numeric "
    "FROM test_run t, unnest(ARRAY['min', 'max']) e "
    "WHERE t.is_aggregate AND t.varied_parameters -> '{dimension}' ->> e IS NOT NULL"
)


def _scenario(api: httpx.Client, body: Mapping[str, Any]) -> dict[str, Any]:
    response = api.post("/scenario", json=body)
    assert response.status_code == httpx.codes.OK, response.text
    return dict(response.json())


def _decode(scenario_id: str) -> dict[str, Any]:
    padded = scenario_id + "=" * (-len(scenario_id) % 4)
    return dict(json.loads(base64.urlsafe_b64decode(padded)))


def _canonical_id(scenario: Mapping[str, Any]) -> str:
    canonical = json.dumps(scenario, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(canonical.encode()).decode().rstrip("=")


def _match_order(
    match: Mapping[str, Any], acronym_key: Callable[[str], Any]
) -> tuple[float, float, Any]:
    """Doc 08 s4.2: similarity, median (descending), then the doc 05 s4 acronym order."""
    return (-match["similarity"], -match["median_similarity"], acronym_key(match["acronym"]))


@pytest.fixture(scope="module")
def presets_doc(
    doc_table: Callable[[str, str], list[dict[str, str]]],
) -> dict[str, dict[str, float]]:
    """Document 08 section 4.1 scenario presets."""
    columns = {
        "o2_fraction": "O2 fraction",
        "pressure_kpa": "Pressure",
        "gravity_g": "Gravity",
        "flow_speed_cm_s": "Flow",
    }
    return {
        row["Preset"].strip("`"): {
            field: float(NUMBER.findall(row[column])[0]) for field, column in columns.items()
        }
        for row in doc_table(DOC_08, "### 4.1 Scenario presets")
    }


@pytest.fixture(scope="module")
def catalog_ranges(stack: str, sql: Rows) -> dict[str, list[float] | None]:
    """Document 08 s4.2: condition values widened by known aggregate-range endpoints."""
    ranges: dict[str, list[float] | None] = {}
    for dimension in NUMERIC_DIMENSIONS:
        values = [float(row["v"]) for row in sql(CATALOG_VALUES.format(dimension=dimension))]
        ranges[dimension] = [min(values), max(values)] if values else None
    return ranges


@pytest.fixture(scope="module")
def gravity_values(stack: str, sql: Rows) -> list[float]:
    rows = sql(
        "SELECT DISTINCT gravity_g AS g FROM condition WHERE gravity_g IS NOT NULL ORDER BY 1"
    )
    return [float(row["g"]) for row in rows]


def _has_gravity(values: list[float], gravity: float) -> bool:
    return any(abs(value - gravity) <= GRAVITY_TOLERANCE for value in values)


def test_fr07_each_preset_resolves_documented_values(
    stack: str, api: httpx.Client, presets_doc: dict[str, dict[str, float]]
) -> None:
    """FR-07, doc 08 s4.1: each preset resolves to its values; `assumed_default` as documented."""
    resolved = {name: _scenario(api, {"preset": name})["scenario"] for name in presets_doc}
    actual = {
        name: ({field: scenario[field] for field in values}, scenario["assumed_default"])
        for (name, values), scenario in zip(presets_doc.items(), resolved.values(), strict=True)
    }
    assert actual == {
        name: (values, name in ASSUMED_DEFAULT_PRESETS) for name, values in presets_doc.items()
    }


def test_fr07_matches_bounded_and_sorted(
    stack: str,
    api: httpx.Client,
    presets_doc: dict[str, dict[str, float]],
    seed_acronyms: list[str],
    acronym_key: Callable[[str], Any],
) -> None:
    """FR-07, doc 08 s4.2: similarity in [0, 1]; sorted by similarity, median, acronym."""
    for name in presets_doc:
        matches = _scenario(api, {"preset": name, "limit": len(seed_acronyms)})["matches"]
        assert all(0.0 <= match["similarity"] <= 1.0 for match in matches)
        assert matches == sorted(matches, key=lambda match: _match_order(match, acronym_key))


def test_fr07_explicit_values_override_preset(
    stack: str, api: httpx.Client, presets_doc: dict[str, dict[str, float]]
) -> None:
    """FR-07, doc 05 s7: explicit values override the preset and clear `assumed_default`."""
    scenario = _scenario(api, {"preset": "lunar_habitat", "o2_fraction": 0.4})["scenario"]
    expected = {**presets_doc["lunar_habitat"], "o2_fraction": 0.4}
    assert {field: scenario[field] for field in expected} == expected
    assert scenario["assumed_default"] is False


@pytest.mark.parametrize("body", [{"preset": "no_such_preset"}, {}])
def test_fr07_unknown_preset_or_empty_is_bad_request(
    body: dict[str, Any], stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """FR-07, doc 05 s7: an unknown preset, or neither preset nor value, is HTTP 400."""
    assert_error_envelope(api.post("/scenario", json=body), 400, "bad_request")


def _outside(catalog: list[float], bounds: tuple[float, float]) -> float:
    """A valid request value outside the catalog range: above it when the request bound
    leaves room, else below it."""
    low_bound, high_bound = bounds
    if catalog[1] + OUTSIDE_MARGIN <= high_bound:
        return catalog[1] + OUTSIDE_MARGIN
    if catalog[1] < high_bound:
        return (catalog[1] + high_bound) / 2
    if catalog[0] <= low_bound:
        pytest.skip("precondition absent: the catalog range spans every valid request value")
    return (low_bound + catalog[0]) / 2


@pytest.mark.parametrize("dimension", sorted(NUMERIC_DIMENSIONS))
def test_fr07_numeric_coverage_states(
    dimension: str, stack: str, api: httpx.Client, catalog_ranges: dict[str, list[float] | None]
) -> None:
    """FR-07, doc 08 s4.3: in-range is `covered`, outside `extrapolated`, no values `no_data`."""
    catalog = catalog_ranges[dimension]
    probes = (
        {"no_data": 1.0}
        if catalog is None
        else {
            "covered": catalog[0] + (catalog[1] - catalog[0]) * INSIDE_FRACTION,
            "extrapolated": _outside(catalog, REQUEST_BOUNDS[dimension]),
        }
    )
    for state, value in probes.items():
        coverage = _scenario(api, {dimension: value})["coverage"][dimension]
        assert (coverage["state"], coverage["catalog_range"]) == (state, catalog)


def test_fr16_gravity_coverage(stack: str, api: httpx.Client, gravity_values: list[float]) -> None:
    """FR-16, doc 08 s4.3: gravity is `covered` only with a run within 0.02 g, else `no_data`."""
    coverage = _scenario(api, {"preset": "lunar_habitat"})["coverage"]["gravity_g"]
    state = "covered" if _has_gravity(gravity_values, LUNAR_GRAVITY) else "no_data"
    assert (coverage["state"], sorted(coverage["catalog_values"])) == (state, gravity_values)


def test_fr16_lunar_gravity_states_the_gap(
    stack: str,
    api: httpx.Client,
    gravity_values: list[float],
    presets_file: dict[str, Any],
    seed_acronyms: list[str],
) -> None:
    """FR-16, doc 08 s4.4: lunar gravity names E-FIELD Flames and states the gap."""
    if _has_gravity(gravity_values, LUNAR_GRAVITY):
        pytest.skip("precondition absent: the catalog holds lunar-gravity runs")
    bounding = _scenario(api, {"preset": "lunar_habitat"})["gravity_bounding"]
    statement = presets_file["texts"]["gravity_bounding"].format(gravity_g=f"{LUNAR_GRAVITY:g}")
    assert (bounding["partial_gravity_data"], bounding["statement"]) == (False, statement)
    assert (bounding["lower_bound"]["gravity_g"], bounding["upper_bound"]["gravity_g"]) == (0, 1)
    if ANALOGUE_ACRONYM not in seed_acronyms:
        pytest.skip(f"precondition absent: {ANALOGUE_ACRONYM} is not in the seed set")
    assert bounding["analogue"]["acronym"] == ANALOGUE_ACRONYM


@pytest.mark.parametrize("preset", ["iss_cabin", "spacesuit"])
def test_fr16_zero_gravity_has_no_gap_statement(
    stack: str, api: httpx.Client, preset: str
) -> None:
    """FR-16, doc 08 s4.4: 0 g is not partial gravity, so no bounds and no statement."""
    bounding = _scenario(api, {"preset": preset})["gravity_bounding"]
    actual = tuple(
        bounding.get(key) for key in ("partial_gravity_data", "lower_bound", "statement")
    )
    assert actual == (False, None, None)


def test_fr07_gravity_never_changes_similarity(
    stack: str, api: httpx.Client, seed_acronyms: list[str]
) -> None:
    """FR-07, ADR-08: changing only gravity leaves every similarity unchanged."""

    def similarities(gravity: float) -> list[tuple[str, float, float]]:
        body = {"preset": "lunar_habitat", "gravity_g": gravity, "limit": len(seed_acronyms)}
        return [
            (m["acronym"], m["similarity"], m["median_similarity"])
            for m in _scenario(api, body)["matches"]
        ]

    assert similarities(LUNAR_GRAVITY) == similarities(MARS_GRAVITY) == similarities(0.0)


def test_fr07_scenario_id_is_stable_and_invertible(stack: str, api: httpx.Client) -> None:
    """FR-07, doc 05 s7: `scenario_id` is unpadded base64url of the canonical scenario JSON."""
    body = {"preset": "mars_habitat", "material": "PMMA"}
    first, second = _scenario(api, body), _scenario(api, body)
    assert first["scenario_id"] == second["scenario_id"] == _canonical_id(first["scenario"])
    assert _decode(first["scenario_id"]) == first["scenario"]


def _span_of(run: Mapping[str, Any], dimension: str) -> tuple[float, float] | None:
    """The run's interval: its stated aggregate range (open where null) or its point value."""
    stated = run["range"].get(dimension)
    if stated is not None:
        low = -math.inf if stated["min"] is None else stated["min"]
        high = math.inf if stated["max"] is None else stated["max"]
        return low, high
    value = run["condition"].get(dimension)
    return None if value is None else (value, value)


def _numeric_distance(
    target: float, span: tuple[float, float] | None, catalog: list[float]
) -> float:
    """Doc 08 s4.2 `num_d`: 0 inside the span, else distance to the nearest endpoint, scaled."""
    if span is None:
        return 1.0
    gap = (
        0.0 if span[0] <= target <= span[1] else min(abs(target - span[0]), abs(target - span[1]))
    )
    return min(1.0, gap / max(catalog[1] - catalog[0], EPSILON))


def _stated_ranges(sql: Rows, run: Mapping[str, Any]) -> dict[str, Any]:
    if not run["is_aggregate"]:
        return {}
    statement = "SELECT varied_parameters AS v FROM test_run WHERE id = :id"
    return dict(sql(statement, id=run["id"])[0]["v"])


def test_fr07_top_match_similarity_recomputed(
    api: httpx.Client, sql: Rows, fixture_runs: list[int]
) -> None:
    """FR-07, doc 08 s4.2: the top similarity follows the distance formula (no fuel given)."""
    response = _scenario(api, {"preset": "iss_cabin"})
    assert response["matches"], "fixture runs must produce a match"
    assert response["matches"][0]["best_run"]["id"] in fixture_runs
    scenario, top = response["scenario"], response["matches"][0]
    run = {**top["best_run"], "range": _stated_ranges(sql, top["best_run"])}
    weights = scenario["weights"]
    parts = {
        key: _numeric_distance(
            scenario[dim], _span_of(run, dim), response["coverage"][dim]["catalog_range"]
        )
        for dim, key in NUMERIC_DIMENSIONS.items()
        if scenario[dim] is not None
    }
    weighted = sum(weights[key] * part for key, part in parts.items())
    distance = weighted / sum(weights[key] for key in parts)
    assert math.isclose(top["similarity"], 1 - distance, abs_tol=SIMILARITY_TOLERANCE)


def test_fr07_explain_without_matches_is_skipped(stack: str, api: httpx.Client) -> None:
    """FR-07, doc 05 s7: the explanation is requested only when there is a match."""
    response = _scenario(api, {"gravity_g": LUNAR_GRAVITY, "explain": True})
    assert response["matches"] == []
    assert response["explanation"]["status"] == "skipped"


def test_fr07_explain_returns_verified_sentences_and_caveats(
    api: httpx.Client, fixture_runs: list[int]
) -> None:
    """FR-07, doc 08 s4.4: cited agent sentences, then one caveat per extrapolated/no_data
    dimension, then the gravity-bounding statement."""
    response = _scenario(api, {"preset": "lunar_habitat", "explain": True})
    assert response["matches"], "fixture runs must produce a match"
    explanation = response["explanation"]
    assert explanation["status"] == "ok"
    weak = [dim for dim, entry in response["coverage"].items() if entry["state"] != "covered"]
    caveats = len(weak) + (1 if response["gravity_bounding"]["statement"] else 0)
    split = len(explanation["sentences"]) - caveats
    cited, uncited = explanation["sentences"][:split], explanation["sentences"][split:]
    assert cited and all(sentence["citations"] for sentence in cited)
    assert [sentence["citations"] for sentence in uncited] == [[]] * caveats
