"""Ranking (document 12 section 2; document 05 section 5; document 08 sections 2 and 3).

Requirements: FR-03 (ranking with breakdown, evidence and confidence), FR-04 (presets and
custom weights without an LLM call), FR-15 (evidence `SourceRef`s), NFR-09 (disclaimer).
Call flow: CF-05 (Ranking).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(12)]

LENSES = ("habitat", "modeling", "controls")
OVERALL = "overall"
SCORE_SCALE = 20.0
SCORE_TOLERANCE = 0.05
# Half a unit of the last decimal is exact only in decimal; binary floats add a hair.
HALF_UNIT_TOLERANCE = SCORE_TOLERANCE + 1e-9
# Doc 08 s2 rounding of the returned values that the ordering compares.
SCORE_DECIMALS = 1
CONFIDENCE_DECIMALS = 3
CONFIDENCE_TOLERANCE = 0.001
DISCLAIMER = "Scores are relative decision aids, not safety certifications."
RESPONSE_FIELDS = {"lens", "rubric_version", "weights_used", "items", "disclaimer"}
ITEM_FIELDS = {"rank", "acronym", "title", "score", "confidence", "lens_scores", "breakdown"}
BREAKDOWN_FIELDS = {
    "criterion", "label", "value", "weight", "contribution", "rationale", "evidence", "origin",
}  # fmt: skip
LIMITED = 3
# Doc 05 s1: page sizes are at most 100; `limit` shares that bound.
FULL_LIST_LIMIT = 100
OVERRIDDEN_CRITERION = ("habitat", "fuel_realism", 1.0)
LensResult = tuple[float | None, float]


def _rank(api: httpx.Client, body: Mapping[str, Any]) -> dict[str, Any]:
    """POST /rank for the full ordering unless the case sets its own `limit` (the default 24
    truncates a larger catalog)."""
    response = api.post("/rank", json={"limit": FULL_LIST_LIMIT, **body})
    assert response.status_code == httpx.codes.OK, response.text
    return dict(response.json())


def _normalized(weights: Mapping[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {key: weight / total for key, weight in weights.items()}


def _lens_result(breakdown: list[dict[str, Any]]) -> LensResult:
    """Document 08 section 2: lens score and confidence from the criterion breakdown."""
    weights = _normalized({item["criterion"]: item["weight"] for item in breakdown})
    rated = [item for item in breakdown if item["value"] is not None]
    rated_weight = sum(weights[item["criterion"]] for item in rated)
    if not rated:
        return None, 0.0
    weighted = sum(weights[item["criterion"]] * item["value"] for item in rated)
    return SCORE_SCALE * weighted / rated_weight, rated_weight


def _overall(results: Mapping[str, LensResult], lens_weights: Mapping[str, float]) -> LensResult:
    """Document 08 section 2: weighted mean of non-null lens scores; weighted confidence."""
    weights = _normalized(lens_weights)
    scored = {lens: score for lens, (score, _) in results.items() if score is not None}
    confidence = sum(weights[lens] * result[1] for lens, result in results.items())
    scored_weight = sum(weights[lens] for lens in scored)
    if not scored or scored_weight == 0:
        return None, confidence
    return sum(weights[lens] * score for lens, score in scored.items()) / scored_weight, confidence


def _order_key(
    item: Mapping[str, Any], acronym_key: Callable[[str], Any]
) -> tuple[bool, float, float, Any]:
    """Descending score, then descending confidence (both as returned), then the doc 05 s4
    acronym order; null scores last."""
    score = item["score"]
    return (score is None, -(score or 0.0), -item["confidence"], acronym_key(item["acronym"]))


def _expected_contributions(breakdown: list[dict[str, Any]]) -> list[float]:
    """Document 08 section 2: `contribution_i = 20 * w_i * v_i / sum_{i in N} w_i`."""
    weights = _normalized({item["criterion"]: item["weight"] for item in breakdown})
    rated_weight = sum(
        weights[item["criterion"]] for item in breakdown if item["value"] is not None
    )
    return [
        0.0
        if item["value"] is None
        else SCORE_SCALE * weights[item["criterion"]] * item["value"] / rated_weight
        for item in breakdown
    ]


def _contributions_consistent(breakdown: list[dict[str, Any]], score: float | None) -> bool:
    """Each contribution follows the formula to response rounding; their sum equals the score
    to the accumulated rounding of the rated terms."""
    if score is None:
        return True
    returned = [item["contribution"] for item in breakdown]
    expected = _expected_contributions(breakdown)
    rated = sum(1 for item in breakdown if item["value"] is not None)
    return all(map(_close, returned, expected, [HALF_UNIT_TOLERANCE] * len(returned))) and _close(
        sum(returned), score, HALF_UNIT_TOLERANCE * (rated + 1)
    )


def _close(actual: float | None, expected: float | None, tolerance: float) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return math.isclose(actual, expected, abs_tol=tolerance)


def _lens_results(api: httpx.Client, body: Mapping[str, Any]) -> dict[str, dict[str, LensResult]]:
    by_lens = {lens: _rank(api, {**body, "lens": lens})["items"] for lens in LENSES}
    acronyms = {item["acronym"] for item in by_lens[LENSES[0]]}
    return {
        acronym: {
            lens: _lens_result(next(i for i in items if i["acronym"] == acronym)["breakdown"])
            for lens, items in by_lens.items()
        }
        for acronym in acronyms
    }


def _expected_weights(
    preset: Mapping[str, Any], rubric_criteria: Mapping[str, Mapping[str, float]]
) -> dict[str, Any]:
    criterion_weights = {
        lens: _normalized({**defaults, **preset["criterion_weights"].get(lens, {})})
        for lens, defaults in rubric_criteria.items()
    }
    return {
        "lens_weights": _normalized(preset["lens_weights"]),
        "criterion_weights": criterion_weights,
    }


def _flatten(weights: Mapping[str, Any]) -> dict[tuple[str, ...], float]:
    """`weights_used` as `{(lens,): W}` plus `{(lens, criterion): w}`."""
    flat: dict[tuple[str, ...], float] = {
        (lens,): float(weight) for lens, weight in weights["lens_weights"].items()
    }
    for lens, criteria in weights["criterion_weights"].items():
        flat.update({(lens, criterion): float(w) for criterion, w in criteria.items()})
    return flat


def _weights_match(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    flat_actual, flat_expected = _flatten(actual), _flatten(expected)
    if flat_actual.keys() != flat_expected.keys():
        return False
    return all(math.isclose(flat_actual[key], flat_expected[key]) for key in flat_expected)


@pytest.mark.parametrize("lens", [*LENSES, OVERALL])
def test_fr03_response_shape_and_disclaimer(
    lens: str, stack: str, api: httpx.Client, seed_acronyms: list[str]
) -> None:
    """FR-03, NFR-09, doc 05 s5: response and item fields, ranks 1..n, disclaimer text."""
    body = _rank(api, {"lens": lens, "limit": len(seed_acronyms)})
    assert set(body) == RESPONSE_FIELDS
    assert (body["lens"], body["disclaimer"]) == (lens, DISCLAIMER)
    assert {frozenset(item) for item in body["items"]} == {frozenset(ITEM_FIELDS)}
    assert {frozenset(b) for item in body["items"] for b in item["breakdown"]} <= {
        frozenset(BREAKDOWN_FIELDS)
    }
    assert [item["rank"] for item in body["items"]] == list(range(1, len(seed_acronyms) + 1))
    assert sorted(item["acronym"] for item in body["items"]) == sorted(seed_acronyms)


@pytest.mark.parametrize("lens", [*LENSES, OVERALL])
def test_fr03_descending_order_with_documented_tie_breaks(
    lens: str, stack: str, api: httpx.Client, acronym_key: Callable[[str], Any]
) -> None:
    """FR-03, doc 08 s2: score desc, confidence desc, acronym; null scores last."""
    items = _rank(api, {"lens": lens})["items"]
    assert items == sorted(items, key=lambda item: _order_key(item, acronym_key))


@pytest.mark.parametrize("lens", LENSES)
def test_fr03_lens_scores_recomputed_from_breakdown(
    lens: str, stack: str, api: httpx.Client
) -> None:
    """FR-03, doc 08 s2: score, confidence and contributions follow the formulas."""
    wrong = []
    for item in _rank(api, {"lens": lens})["items"]:
        score, confidence = _lens_result(item["breakdown"])
        consistent = (
            _close(item["score"], score, SCORE_TOLERANCE)
            and _close(item["confidence"], confidence, CONFIDENCE_TOLERANCE)
            and _contributions_consistent(item["breakdown"], score)
        )
        if not consistent:
            wrong.append(item["acronym"])
    assert wrong == []


def test_fr03_overall_recomputed_from_lenses(stack: str, api: httpx.Client) -> None:
    """FR-03, doc 08 s2: overall is the lens-weighted mean of non-null lens scores."""
    overall = _rank(api, {"lens": OVERALL})
    lens_weights = overall["weights_used"]["lens_weights"]
    results = _lens_results(api, {})
    wrong = [
        item["acronym"]
        for item in overall["items"]
        if not all(
            map(
                _close,
                (item["score"], item["confidence"]),
                _overall(results[item["acronym"]], lens_weights),
                (SCORE_TOLERANCE, CONFIDENCE_TOLERANCE),
            )
        )
    ]
    assert wrong == []


def test_fr04_presets_set_documented_weights(
    stack: str,
    api: httpx.Client,
    ranking_presets: dict[str, dict[str, Any]],
    rubric_criteria: dict[str, dict[str, float]],
) -> None:
    """FR-04, doc 08 s3: each preset's lens weights and criterion emphasis (normalized)."""
    mismatched = [
        name
        for name, preset in ranking_presets.items()
        if not _weights_match(
            _rank(api, {"lens": OVERALL, "preset": name})["weights_used"],
            _expected_weights(preset, rubric_criteria),
        )
    ]
    assert mismatched == []


@pytest.mark.parametrize("preset", ["lunar_habitat", "modeler", "equipment_designer"])
def test_fr04_preset_order_follows_reweighted_scores(
    preset: str, stack: str, api: httpx.Client, acronym_key: Callable[[str], Any]
) -> None:
    """FR-04, CF-05: a preset re-ranks by the overall score recomputed with its weights."""
    ranked = _rank(api, {"lens": OVERALL, "preset": preset})
    results = _lens_results(api, {"preset": preset})
    expected = [
        {
            "acronym": acronym,
            "score": None if score is None else round(score, SCORE_DECIMALS),
            "confidence": round(confidence, CONFIDENCE_DECIMALS),
        }
        for acronym, (score, confidence) in (
            (a, _overall(r, ranked["weights_used"]["lens_weights"])) for a, r in results.items()
        )
    ]
    assert [item["acronym"] for item in ranked["items"]] == [
        item["acronym"]
        for item in sorted(expected, key=lambda item: _order_key(item, acronym_key))
    ]


def test_fr04_explicit_weights_override_preset(
    stack: str,
    api: httpx.Client,
    ranking_presets: dict[str, dict[str, Any]],
    rubric_criteria: dict[str, dict[str, float]],
) -> None:
    """FR-04, doc 05 s5: explicit weights override the preset, which overrides the rubric."""
    lens, criterion, weight = OVERRIDDEN_CRITERION
    explicit_lens_weights = {"habitat": 1.0, "modeling": 0.0, "controls": 0.0}
    body = {
        "lens": OVERALL,
        "preset": "lunar_habitat",
        "lens_weights": explicit_lens_weights,
        "criterion_weights": {lens: {criterion: weight}},
    }
    preset = ranking_presets["lunar_habitat"]
    merged = {
        "lens_weights": explicit_lens_weights,
        "criterion_weights": {lens: {**preset["criterion_weights"][lens], criterion: weight}},
    }
    assert _weights_match(
        _rank(api, body)["weights_used"], _expected_weights(merged, rubric_criteria)
    )


def test_fr04_filters_restrict_the_ranking(
    stack: str,
    api: httpx.Client,
    listed: Callable[..., list[str]],
    sql: Callable[..., list[dict[str, Any]]],
    acronym_key: Callable[[str], Any],
) -> None:
    """FR-04, doc 05 s5: `filters` keep the investigations the catalog filter returns."""
    hardware = sql("SELECT name FROM hardware ORDER BY name LIMIT 1")[0]["name"]
    items = _rank(api, {"lens": OVERALL, "filters": {"hardware": [hardware]}})["items"]
    assert sorted((item["acronym"] for item in items), key=acronym_key) == listed(
        {"hardware": hardware}
    )
    assert [item["rank"] for item in items] == list(range(1, len(items) + 1))


def test_fr04_limit_truncates_after_ranking(stack: str, api: httpx.Client) -> None:
    """FR-04, doc 05 s5: `limit` keeps the head of the full ordering with its ranks."""
    full = _rank(api, {"lens": OVERALL})["items"]
    assert _rank(api, {"lens": OVERALL, "limit": LIMITED})["items"] == full[:LIMITED]


def test_fr04_identical_requests_give_identical_bodies(stack: str, api: httpx.Client) -> None:
    """FR-04, doc 05 s5: no LLM call, deterministic for identical input."""
    body = {"lens": OVERALL, "preset": "spacecraft_cabin"}
    assert api.post("/rank", json=body).content == api.post("/rank", json=body).content


@pytest.mark.parametrize("lens", LENSES)
def test_fr15_evidence_for_every_rated_criterion(
    lens: str, stack: str, api: httpx.Client, source_ref_is_valid: Callable[..., bool]
) -> None:
    """FR-03, FR-15: every non-null criterion value carries at least one valid `SourceRef`."""
    rated = [
        entry
        for item in _rank(api, {"lens": lens})["items"]
        for entry in item["breakdown"]
        if entry["value"] is not None
    ]
    unsupported = [
        entry["criterion"]
        for entry in rated
        if not entry["evidence"] or not all(map(source_ref_is_valid, entry["evidence"]))
    ]
    assert unsupported == []


def test_fr04_unknown_preset_is_bad_request(
    stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """FR-04, doc 05 s2: an unknown preset is HTTP 400 `bad_request`."""
    assert_error_envelope(
        api.post("/rank", json={"lens": OVERALL, "preset": "no_such_preset"}), 400, "bad_request"
    )
