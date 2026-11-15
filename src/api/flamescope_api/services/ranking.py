"""`RankingService`: lens scores, overall score and ordering (document 08 sections 2 and 3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from flamescope_api.repositories.scores import CriterionRating, InvestigationRatings, ScoreRepo
from flamescope_common.errors import ValidationError
from flamescope_common.rubric import LENSES, Lens, Presets, Rubric
from flamescope_common.schemas.api import (
    SCORE_DISCLAIMER,
    BreakdownItem,
    InvestigationFilters,
    LensScore,
    RankItem,
    RankLens,
    RankResponse,
    ScoreSet,
    WeightsUsed,
)
from flamescope_common.schemas.card import acronym_sort_key

POINTS_PER_RATING_STEP = 20.0  # a 0..5 rating scales to 0..100
SCORE_DECIMALS = 1
CONFIDENCE_DECIMALS = 3
WEIGHT_DECIMALS = 4


@dataclass(frozen=True)
class WeightOverrides:
    """Explicit weights of a rank request; they win over the preset and the rubric."""

    lens_weights: Mapping[Lens, float] | None = None
    criterion_weights: Mapping[Lens, Mapping[str, float]] | None = None


def _normalized[K](weights: Mapping[K, float], label: str) -> dict[K, float]:
    if any(weight < 0 for weight in weights.values()):
        raise ValidationError(f"{label} weights must not be negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValidationError(f"{label} weights must have a positive sum")
    return {key: weight / total for key, weight in weights.items()}


def aggregate(
    criterion_scores: Mapping[str, CriterionRating],
    weights: Mapping[str, float],
    labels: Mapping[str, str] | None = None,
) -> LensScore:
    """Lens score 0-100 and confidence of one lens (document 08 section 2); unrounded.

    Criteria without a rating or with a null value are excluded and the rest renormalized.
    """
    normalized = _normalized(weights, "criterion")
    rated = {
        key: rating.value
        for key, rating in criterion_scores.items()
        if key in normalized and rating.value is not None
    }
    rated_weight = sum(normalized[key] for key in rated)
    score = None
    if rated_weight > 0:
        weighted = sum(normalized[key] * value for key, value in rated.items())
        score = POINTS_PER_RATING_STEP * weighted / rated_weight
    breakdown = [
        _breakdown_item(key, weight, criterion_scores.get(key), rated_weight, labels)
        for key, weight in normalized.items()
    ]
    return LensScore(score=score, confidence=rated_weight, breakdown=breakdown)


def _breakdown_item(
    key: str,
    weight: float,
    rating: CriterionRating | None,
    rated_weight: float,
    labels: Mapping[str, str] | None,
) -> BreakdownItem:
    value = rating.value if rating else None
    contribution = 0.0
    if value is not None and rated_weight > 0:
        contribution = POINTS_PER_RATING_STEP * weight * value / rated_weight
    return BreakdownItem(
        criterion=key,
        label=(labels or {}).get(key, key),
        value=value,
        weight=weight,
        contribution=contribution,
        rationale=rating.rationale if rating else "",
        evidence=list(rating.evidence) if rating else [],
        origin=rating.origin if rating else "seed",
    )


def overall(
    lens_scores: Mapping[Lens, LensScore], lens_weights: Mapping[Lens, float]
) -> tuple[float | None, float]:
    """Weighted mean of the non-null lens scores and the weighted confidence."""
    normalized = _normalized(lens_weights, "lens")
    scored = [
        lens for lens in LENSES if lens in lens_scores and lens_scores[lens].score is not None
    ]
    scored_weight = sum(normalized[lens] for lens in scored)
    confidence = sum(
        normalized[lens] * lens_scores[lens].confidence for lens in LENSES if lens in lens_scores
    )
    if scored_weight <= 0:
        return None, confidence
    total = sum(normalized[lens] * (lens_scores[lens].score or 0.0) for lens in scored)
    return total / scored_weight, confidence


def resolve_weights(
    rubric: Rubric, presets: Presets, preset: str | None, overrides: WeightOverrides
) -> WeightsUsed:
    """Rubric defaults, then the preset, then explicit weights; each lens normalized."""
    lens_weights: dict[Lens, float] = dict(rubric.lens_weights)
    criterion_weights = {lens: rubric.default_criterion_weights(lens) for lens in LENSES}
    if preset is not None:
        chosen = presets.ranking.get(preset)
        if chosen is None:
            raise ValidationError(
                f"Unknown ranking preset {preset!r}", {"known": sorted(presets.ranking)}
            )
        lens_weights.update(chosen.lens_weights)
        _merge_criteria(rubric, criterion_weights, chosen.criterion_weights)
    lens_weights.update(overrides.lens_weights or {})
    _merge_criteria(rubric, criterion_weights, overrides.criterion_weights or {})
    return WeightsUsed(
        lens_weights=_normalized(lens_weights, "lens"),
        criterion_weights={
            lens: _normalized(weights, f"{lens} criterion")
            for lens, weights in criterion_weights.items()
        },
    )


def _merge_criteria(
    rubric: Rubric,
    target: dict[Lens, dict[str, float]],
    updates: Mapping[Lens, Mapping[str, float]],
) -> None:
    for lens, weights in updates.items():
        known = set(rubric.criterion_ids(lens))
        unknown = set(weights) - known
        if unknown:
            raise ValidationError(
                f"Unknown criteria {sorted(unknown)} for lens {lens!r}", {"known": sorted(known)}
            )
        target[lens].update(weights)


def score_lenses(
    ratings: Mapping[Lens, Mapping[str, CriterionRating]],
    rubric: Rubric,
    criterion_weights: Mapping[Lens, Mapping[str, float]] | None = None,
) -> dict[Lens, LensScore]:
    """Every lens scored with the given (default: rubric) criterion weights."""
    result: dict[Lens, LensScore] = {}
    for lens in LENSES:
        weights = (criterion_weights or {}).get(lens) or rubric.default_criterion_weights(lens)
        labels = {criterion.id: criterion.label for criterion in rubric.criteria(lens)}
        result[lens] = aggregate(ratings.get(lens, {}), weights, labels)
    return result


def _round(value: float | None, decimals: int) -> float | None:
    return None if value is None else round(value, decimals)


def _rounded_breakdown(
    items: Sequence[BreakdownItem], lens_factor: float = 1.0
) -> list[BreakdownItem]:
    return [
        item.model_copy(
            update={
                "weight": round(item.weight * lens_factor, WEIGHT_DECIMALS),
                "contribution": round(item.contribution * lens_factor, SCORE_DECIMALS),
            }
        )
        for item in items
    ]


def _score_set(lens_scores: Mapping[Lens, LensScore], overall_score: float | None) -> ScoreSet:
    return ScoreSet(
        habitat=_round(lens_scores["habitat"].score, SCORE_DECIMALS),
        modeling=_round(lens_scores["modeling"].score, SCORE_DECIMALS),
        controls=_round(lens_scores["controls"].score, SCORE_DECIMALS),
        overall=_round(overall_score, SCORE_DECIMALS),
    )


def _rank_item(
    lens: RankLens,
    entry: InvestigationRatings,
    scored: Mapping[Lens, LensScore],
    weights: WeightsUsed,
) -> RankItem:
    overall_score, overall_confidence = overall(scored, weights.lens_weights)
    if lens == "overall":
        score, confidence = overall_score, overall_confidence
        breakdown = _overall_breakdown(scored, weights.lens_weights, overall_score is not None)
    else:
        score, confidence = scored[lens].score, scored[lens].confidence
        breakdown = _rounded_breakdown(scored[lens].breakdown)
    return RankItem(
        rank=0,
        acronym=entry.acronym,
        title=entry.title,
        score=_round(score, SCORE_DECIMALS),
        confidence=round(confidence, CONFIDENCE_DECIMALS),
        lens_scores={name: _round(scored[name].score, SCORE_DECIMALS) for name in LENSES},
        breakdown=breakdown,
    )


def _rank_order(item: RankItem) -> tuple[bool, float, float, tuple[str, str]]:
    """Document 08 section 2 order on the returned, rounded values (null scores last)."""
    return (
        item.score is None,
        -(item.score or 0.0),
        -(item.confidence or 0.0),
        acronym_sort_key(item.acronym),
    )


def _overall_breakdown(
    scored: Mapping[Lens, LensScore], lens_weights: Mapping[Lens, float], has_score: bool
) -> list[BreakdownItem]:
    """Criteria of all lenses, scaled so contributions add up to the overall score."""
    if not has_score:
        return []
    active = {lens: lens_weights[lens] for lens in LENSES if scored[lens].score is not None}
    total = sum(active.values())
    items: list[BreakdownItem] = []
    for lens, weight in active.items():
        items.extend(_rounded_breakdown(scored[lens].breakdown, weight / total))
    return items


class RankingService:
    """Scores and ranks investigations from stored criterion ratings; no LLM."""

    def __init__(self, scores: ScoreRepo, rubric: Rubric, presets: Presets) -> None:
        self._scores = scores
        self._rubric = rubric
        self._presets = presets

    def rank(
        self,
        lens: RankLens,
        weights: WeightOverrides,
        preset: str | None,
        filters: InvestigationFilters | None,
    ) -> RankResponse:
        """All matching investigations ordered by score, confidence, acronym (nulls last)."""
        used = resolve_weights(self._rubric, self._presets, preset, weights)
        ranked = [
            _rank_item(lens, entry, self._lens_scores(entry, used), used)
            for entry in self._scores.all_scores(filters)
        ]
        ranked.sort(key=_rank_order)
        items = [
            item.model_copy(update={"rank": position}) for position, item in enumerate(ranked, 1)
        ]
        return RankResponse(
            lens=lens,
            rubric_version=self._rubric.rubric_version,
            weights_used=used,
            items=items,
            disclaimer=SCORE_DISCLAIMER,
        )

    def _lens_scores(
        self, entry: InvestigationRatings, used: WeightsUsed
    ) -> dict[Lens, LensScore]:
        return score_lenses(entry.ratings, self._rubric, used.criterion_weights)

    def breakdown(self, investigation_id: int) -> dict[Lens, LensScore]:
        """Per-lens score breakdown with the rubric default weights."""
        entry = self._scores.for_investigation(investigation_id)
        return score_lenses(entry.ratings, self._rubric)

    def score_sets(self, investigation_ids: Sequence[int] | None = None) -> dict[int, ScoreSet]:
        """Default-weight scores per investigation ID (all when no IDs are given)."""
        sets: dict[int, ScoreSet] = {}
        for entry in self._scores.all_scores(None):
            if investigation_ids is not None and entry.investigation_id not in investigation_ids:
                continue
            scored = score_lenses(entry.ratings, self._rubric)
            overall_score, _ = overall(scored, self._rubric.lens_weights)
            sets[entry.investigation_id] = _score_set(scored, overall_score)
        return sets
