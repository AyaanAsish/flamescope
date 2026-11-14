"""FR-03, FR-04: lens aggregation, weights, presets and ordering (document 08 sections 2, 3, 6)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from flamescope_api.repositories.scores import CriterionRating, InvestigationRatings
from flamescope_api.services.ranking import (
    RankingService,
    WeightOverrides,
    aggregate,
    overall,
    resolve_weights,
)
from flamescope_common.errors import ValidationError
from flamescope_common.rubric import Lens, Presets, Rubric
from flamescope_common.schemas.api import InvestigationFilters, LensScore

pytestmark = pytest.mark.unit

HABITAT_DEFAULTS = {
    "fuel_realism": 0.25,
    "atmosphere_match": 0.25,
    "flow_regime": 0.15,
    "phenomenon": 0.20,
    "gravity_bounding": 0.15,
}
# Document 08 section 6 worked example.
WORKED_VALUES: dict[str, float | None] = {
    "fuel_realism": 5,
    "atmosphere_match": 3,
    "flow_regime": None,
    "phenomenon": 4,
    "gravity_bounding": 2,
}
WORKED_SCORE = 72.9
WORKED_CONFIDENCE = 0.85
DISCLAIMER = "Scores are relative decision aids, not safety certifications."
FLOAT_TOLERANCE = 1e-9
ROUNDING_TOLERANCE_PER_ITEM = 0.05


def _ratings(values: Mapping[str, float | None]) -> dict[str, CriterionRating]:
    return {criterion: CriterionRating(value=value) for criterion, value in values.items()}


def _habitat_entry(acronym: str, values: Mapping[str, float | None]) -> InvestigationRatings:
    identifier = sum(ord(char) for char in acronym)
    return InvestigationRatings(
        identifier, acronym, f"{acronym} title", {"habitat": _ratings(values)}
    )


class FakeScoreRepo:
    """`ScoreRepo` stand-in returning fixed ratings and recording the filters it got."""

    def __init__(self, entries: list[InvestigationRatings]) -> None:
        self._entries = entries
        self.received_filters: list[InvestigationFilters | None] = []

    def all_scores(
        self, filters: InvestigationFilters | None = None
    ) -> list[InvestigationRatings]:
        self.received_filters.append(filters)
        return list(self._entries)

    def for_investigation(self, investigation_id: int) -> InvestigationRatings:
        return next(entry for entry in self._entries if entry.investigation_id == investigation_id)


def _service(entries: list[InvestigationRatings], rubric: Rubric, presets: Presets) -> Any:
    return RankingService(FakeScoreRepo(entries), rubric, presets)  # type: ignore[arg-type]


class TestWorkedExample:
    def test_fr03_worked_example_gives_72_9_with_confidence_0_85(self) -> None:
        """FR-03: document 08 section 6 gives 72.9 and confidence 0.85."""
        result = aggregate(_ratings(WORKED_VALUES), HABITAT_DEFAULTS)
        assert result.score is not None
        assert round(result.score, 1) == WORKED_SCORE
        assert result.confidence == pytest.approx(WORKED_CONFIDENCE)

    def test_fr03_worked_example_score_is_unrounded(self) -> None:
        """FR-03: computation in float; 20 * 3.10 / 0.85 = 72.94 (rounding only in responses)."""
        result = aggregate(_ratings(WORKED_VALUES), HABITAT_DEFAULTS)
        assert result.score == pytest.approx(20 * 3.10 / 0.85)

    def test_fr03_contributions_sum_to_the_lens_score(self) -> None:
        """FR-03: contribution_i = 20 w_i v_i / sum(w_N) adds up to the lens score."""
        result = aggregate(_ratings(WORKED_VALUES), HABITAT_DEFAULTS)
        assert sum(item.contribution for item in result.breakdown) == pytest.approx(result.score)

    def test_fr03_null_criterion_contributes_zero_and_keeps_null_value(self) -> None:
        """FR-03: a null criterion stays null in the breakdown and adds nothing."""
        result = aggregate(_ratings(WORKED_VALUES), HABITAT_DEFAULTS)
        flow = next(item for item in result.breakdown if item.criterion == "flow_regime")
        assert flow.value is None
        assert flow.contribution == 0.0

    def test_fr03_breakdown_uses_given_labels(self) -> None:
        """FR-03: `labels` maps criterion IDs to display labels."""
        result = aggregate(
            _ratings(WORKED_VALUES), HABITAT_DEFAULTS, labels={"fuel_realism": "Fuel realism"}
        )
        fuel = next(item for item in result.breakdown if item.criterion == "fuel_realism")
        assert fuel.label == "Fuel realism"


class TestNullAndNormalization:
    def test_fr03_all_null_criteria_give_null_score(self) -> None:
        """FR-03: N empty -> lens score null, confidence 0."""
        result = aggregate(_ratings(dict.fromkeys(HABITAT_DEFAULTS)), HABITAT_DEFAULTS)
        assert result.score is None
        assert result.confidence == 0.0

    def test_fr03_missing_ratings_count_as_null(self) -> None:
        """FR-03: a criterion without a stored rating is treated like a null value."""
        result = aggregate({}, HABITAT_DEFAULTS)
        assert result.score is None
        partial = aggregate(_ratings({"fuel_realism": 4}), HABITAT_DEFAULTS)
        assert partial.score == pytest.approx(80.0)
        assert partial.confidence == pytest.approx(0.25)

    def test_fr04_weights_are_normalized(self) -> None:
        """FR-04: weights need not sum to 1; scaling them leaves the score unchanged."""
        doubled = {key: weight * 2 for key, weight in HABITAT_DEFAULTS.items()}
        reference = aggregate(_ratings(WORKED_VALUES), HABITAT_DEFAULTS)
        scaled = aggregate(_ratings(WORKED_VALUES), doubled)
        assert scaled.score == pytest.approx(reference.score)
        assert scaled.confidence == pytest.approx(reference.confidence)
        assert sum(item.weight for item in scaled.breakdown) == pytest.approx(1.0)

    def test_fr04_unequal_raw_weights(self) -> None:
        """FR-04: raw weights 1 and 3 normalize to 0.25 and 0.75."""
        result = aggregate(_ratings({"a": 5, "b": 1}), {"a": 1, "b": 3})
        assert result.score == pytest.approx(20 * (0.25 * 5 + 0.75 * 1))


class TestOverall:
    def test_fr03_overall_is_weighted_mean_of_non_null_lenses(self) -> None:
        """FR-03: overall = sum W_l s_l / sum W_l over lenses with a score."""
        scores: dict[Lens, LensScore] = {
            "habitat": LensScore(score=80.0, confidence=1.0),
            "modeling": LensScore(score=None, confidence=0.0),
            "controls": LensScore(score=50.0, confidence=0.5),
        }
        score, confidence = overall(scores, {"habitat": 0.4, "modeling": 0.3, "controls": 0.3})
        assert score == pytest.approx((0.4 * 80 + 0.3 * 50) / 0.7)
        assert confidence == pytest.approx(0.4 * 1.0 + 0.3 * 0.0 + 0.3 * 0.5)

    def test_fr03_overall_is_null_when_every_lens_is_null(self) -> None:
        """FR-03: no lens score -> overall null."""
        empty = LensScore(score=None, confidence=0.0)
        scores: dict[Lens, LensScore] = {"habitat": empty, "modeling": empty, "controls": empty}
        score, _ = overall(scores, {"habitat": 0.4, "modeling": 0.3, "controls": 0.3})
        assert score is None


class TestWeightResolution:
    def test_fr04_rubric_defaults_without_preset(self, rubric: Rubric, presets: Presets) -> None:
        """FR-04: default lens weights 0.4 / 0.3 / 0.3 and rubric criterion weights."""
        used = resolve_weights(rubric, presets, None, WeightOverrides())
        assert used.lens_weights == pytest.approx(
            {"habitat": 0.4, "modeling": 0.3, "controls": 0.3}
        )
        assert used.criterion_weights["habitat"] == pytest.approx(HABITAT_DEFAULTS)

    def test_fr04_preset_overrides_rubric(self, rubric: Rubric, presets: Presets) -> None:
        """FR-04: `lunar_habitat` lens weights 0.6 / 0.2 / 0.2 and habitat emphasis."""
        used = resolve_weights(rubric, presets, "lunar_habitat", WeightOverrides())
        assert used.lens_weights == pytest.approx(
            {"habitat": 0.6, "modeling": 0.2, "controls": 0.2}
        )
        assert used.criterion_weights["habitat"]["atmosphere_match"] == pytest.approx(0.35)
        assert used.criterion_weights["habitat"]["flow_regime"] == pytest.approx(0.05)

    def test_fr04_explicit_weights_override_preset(self, rubric: Rubric, presets: Presets) -> None:
        """FR-04: explicit weights win over the preset, which wins over the rubric."""
        overrides = WeightOverrides(
            lens_weights={"habitat": 0.5, "modeling": 0.25, "controls": 0.25},
            criterion_weights={"habitat": {"fuel_realism": 0.5}},
        )
        used = resolve_weights(rubric, presets, "lunar_habitat", overrides)
        assert used.lens_weights["habitat"] == pytest.approx(0.5)
        # lunar_habitat habitat weights with fuel_realism replaced by 0.5 sum to 1.25.
        assert used.criterion_weights["habitat"]["fuel_realism"] == pytest.approx(0.5 / 1.25)
        assert used.criterion_weights["habitat"]["atmosphere_match"] == pytest.approx(0.35 / 1.25)

    def test_fr04_explicit_weights_are_normalized(self, rubric: Rubric, presets: Presets) -> None:
        """FR-04: explicit lens weights 2 / 1 / 1 normalize to 0.5 / 0.25 / 0.25."""
        overrides = WeightOverrides(lens_weights={"habitat": 2, "modeling": 1, "controls": 1})
        used = resolve_weights(rubric, presets, None, overrides)
        assert used.lens_weights == pytest.approx(
            {"habitat": 0.5, "modeling": 0.25, "controls": 0.25}
        )

    def test_fr04_unknown_preset_is_bad_request(self, rubric: Rubric, presets: Presets) -> None:
        """FR-04: an unknown preset is `ValidationError` (HTTP 400, document 05 section 2)."""
        with pytest.raises(ValidationError):
            resolve_weights(rubric, presets, "no_such_preset", WeightOverrides())

    def test_fr04_unknown_criterion_is_bad_request(self, rubric: Rubric, presets: Presets) -> None:
        """FR-04: explicit weights may only name criteria of the rubric."""
        overrides = WeightOverrides(criterion_weights={"habitat": {"no_such_criterion": 1.0}})
        with pytest.raises(ValidationError):
            resolve_weights(rubric, presets, None, overrides)


class TestOrdering:
    def test_fr03_orders_by_score_then_confidence_then_acronym(
        self, rubric: Rubric, presets: Presets
    ) -> None:
        """FR-03: descending score, then descending confidence, then acronym; nulls last."""
        all_three = dict.fromkeys(HABITAT_DEFAULTS, 3)
        entries = [
            _habitat_entry("NULLSCORE", dict.fromkeys(HABITAT_DEFAULTS)),
            _habitat_entry("LOWCONF", {"fuel_realism": 3}),
            _habitat_entry("DELTA", all_three),
            _habitat_entry("CHARLIE", all_three),
            _habitat_entry("TOP", dict.fromkeys(HABITAT_DEFAULTS, 5)),
        ]
        response = _service(entries, rubric, presets).rank(
            "habitat", WeightOverrides(), None, None
        )
        assert [item.acronym for item in response.items] == [
            "TOP",
            "CHARLIE",
            "DELTA",
            "LOWCONF",
            "NULLSCORE",
        ]
        assert [item.rank for item in response.items] == [1, 2, 3, 4, 5]
        assert response.items[-1].score is None

    def test_fr03_response_rounds_worked_example(self, rubric: Rubric, presets: Presets) -> None:
        """FR-03: responses carry the score to one decimal (72.9) and confidence 0.85."""
        entries = [_habitat_entry("ALPHA", WORKED_VALUES)]
        item = (
            _service(entries, rubric, presets)
            .rank("habitat", WeightOverrides(), None, None)
            .items[0]
        )
        assert item.score == WORKED_SCORE
        assert item.confidence == pytest.approx(WORKED_CONFIDENCE)
        assert item.lens_scores["habitat"] == WORKED_SCORE
        assert item.lens_scores["modeling"] is None

    @pytest.mark.parametrize("lens", ["habitat", "overall"])
    def test_fr03_response_contributions_sum_to_score(
        self, lens: str, rubric: Rubric, presets: Presets
    ) -> None:
        """FR-03: breakdown contributions add up to the item score (within rounding)."""
        entry = InvestigationRatings(
            1,
            "ALPHA",
            "ALPHA title",
            {
                "habitat": _ratings(WORKED_VALUES),
                "modeling": _ratings({"quantitative_outputs": 4, "parameter_sweep": 2}),
            },
        )
        item = (
            _service([entry], rubric, presets).rank(lens, WeightOverrides(), None, None).items[0]
        )
        assert item.score is not None
        tolerance = ROUNDING_TOLERANCE_PER_ITEM * (len(item.breakdown) + 1)
        assert sum(part.contribution for part in item.breakdown) == pytest.approx(
            item.score, abs=tolerance
        )

    def test_fr03_rank_metadata(self, rubric: Rubric, presets: Presets) -> None:
        """FR-03: rubric version, disclaimer and weights used are reported (document 05 s5)."""
        response = _service([], rubric, presets).rank("overall", WeightOverrides(), None, None)
        assert response.rubric_version == rubric.rubric_version == "2026.11-1"
        assert response.disclaimer == DISCLAIMER
        assert response.weights_used.lens_weights["habitat"] == pytest.approx(0.4)
        assert response.items == []

    def test_fr03_rank_is_deterministic(self, rubric: Rubric, presets: Presets) -> None:
        """FR-03: identical input gives an identical response."""
        entries = [
            _habitat_entry("ALPHA", WORKED_VALUES),
            _habitat_entry("BRAVO", {"phenomenon": 1}),
        ]
        service = _service(entries, rubric, presets)
        first = service.rank("overall", WeightOverrides(), "lunar_habitat", None)
        second = service.rank("overall", WeightOverrides(), "lunar_habitat", None)
        assert first == second

    def test_fr04_preset_changes_order(self, rubric: Rubric, presets: Presets) -> None:
        """FR-04: `lunar_habitat` emphasises atmosphere_match over flow_regime."""
        entries = [
            _habitat_entry("ATMOS", {"atmosphere_match": 5, "flow_regime": 1}),
            _habitat_entry("FLOWY", {"atmosphere_match": 1, "flow_regime": 5}),
        ]
        service = _service(entries, rubric, presets)
        cabin = service.rank("habitat", WeightOverrides(), "spacecraft_cabin", None)
        lunar = service.rank("habitat", WeightOverrides(), "lunar_habitat", None)
        assert [item.acronym for item in cabin.items] == ["FLOWY", "ATMOS"]
        assert [item.acronym for item in lunar.items] == ["ATMOS", "FLOWY"]

    def test_fr02_filters_are_passed_to_the_repository(
        self, rubric: Rubric, presets: Presets
    ) -> None:
        """FR-02: rank filters reach `ScoreRepo.all_scores`."""
        repo = FakeScoreRepo([])
        filters = InvestigationFilters(fuel_phase=["solid"])
        RankingService(repo, rubric, presets).rank("habitat", WeightOverrides(), None, filters)  # type: ignore[arg-type]
        assert repo.received_filters == [filters]


class TestServiceScores:
    def test_fr03_breakdown_uses_rubric_defaults(self, rubric: Rubric, presets: Presets) -> None:
        """FR-03: `breakdown(id)` scores every lens with the rubric default weights."""
        entry = _habitat_entry("ALPHA", WORKED_VALUES)
        lenses = _service([entry], rubric, presets).breakdown(entry.investigation_id)
        assert set(lenses) == {"habitat", "modeling", "controls"}
        assert lenses["habitat"].score == pytest.approx(20 * 3.10 / 0.85)
        assert lenses["modeling"].score is None

    def test_fr01_score_sets_round_to_one_decimal(self, rubric: Rubric, presets: Presets) -> None:
        """FR-01: summary scores per investigation, default weights, one decimal."""
        alpha = _habitat_entry("ALPHA", WORKED_VALUES)
        bravo = _habitat_entry("BRAVO", {"phenomenon": 1})
        sets = _service([alpha, bravo], rubric, presets).score_sets([alpha.investigation_id])
        assert list(sets) == [alpha.investigation_id]
        assert sets[alpha.investigation_id].habitat == WORKED_SCORE
        assert sets[alpha.investigation_id].overall == WORKED_SCORE
        assert sets[alpha.investigation_id].controls is None

    @pytest.mark.parametrize("weights", [{"a": 0.0, "b": 0.0}, {"a": -1.0, "b": 2.0}])
    def test_fr04_weights_that_cannot_be_normalized_are_bad_request(
        self, weights: dict[str, float]
    ) -> None:
        """FR-04: weights are normalized, so a zero sum or a negative weight is HTTP 400."""
        with pytest.raises(ValidationError):
            aggregate(_ratings({"a": 1, "b": 2}), weights)
