"""Rule-based synthesizers behind `MockLlm`: one deterministic answer per agent contract."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, NamedTuple, get_args

from flamescope_common.schemas.agents import (
    INSUFFICIENT_INFORMATION_SENTENCE,
    MAX_COMPARATOR_SENTENCES,
    MIN_COMPARATOR_SENTENCES,
    ComparatorInput,
    ComparatorOutput,
    DraftSource,
    DraftText,
    EarthAppCandidate,
    EarthAppsInput,
    EarthAppsOutput,
    ExtractorInput,
    ExtractorOutput,
    InsightQAInput,
    ScenarioInterpreterInput,
    ScenarioInterpreterOutput,
    ScorerCriterionScore,
    ScorerEvidence,
    ScorerInput,
    ScorerOutput,
    SentenceWithFacts,
)
from flamescope_common.schemas.api import EarthSector, MatrixRow
from flamescope_common.schemas.card import FireSafetyTag, InvestigationCard
from flamescope_common.sources import MAX_QUOTE_CHARS, truncate_quote

QA_MAX_CHUNK_SENTENCES = 3
QA_MAX_FACT_SENTENCES = 1
SCENARIO_MAX_FACT_SENTENCES = 4
EARTH_APP_CONFIDENCE = 0.3
FULL_GRAVITY_G = 1.0
NO_CITED_FACTS_SENTENCE = "No further cited facts were supplied."
EXTRACTOR_OPEN_QUESTION = (
    "Mock extractor: only tags and the first sentence of the first document were derived."
)

AIR_O2_FRACTION = 0.21
LUNAR_ENVELOPE_O2_FRACTION = 0.30
SEA_LEVEL_KPA = 101.3
TABULAR_FILE_TYPES = {"csv", "tsv", "xlsx"}
SWEEP_FULL_VARIED_COUNT = 2
QUANTITATIVE_KEYWORDS = ("spread", "burn rate", "limit")

_TOKEN = re.compile(r"[a-z0-9]+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_ISS_MENTION = re.compile(r"\bISS\b|international space station", re.IGNORECASE)


# --- extractor -----------------------------------------------------------------------------


def _first_sentence(text: str) -> str:
    return _SENTENCE_END.split(text.strip(), maxsplit=1)[0][:MAX_QUOTE_CHARS]


def _derive_tags(text: str) -> list[FireSafetyTag]:
    lowered = text.lower()
    tags: list[FireSafetyTag] = []
    for tag in get_args(FireSafetyTag):
        if tag.replace("_", " ") in lowered:
            tags.append(tag)
    return tags


def _extractor_output(request: ExtractorInput) -> str:
    combined = "\n".join(item.text for item in request.context)
    first = request.context[0] if request.context else None
    objectives = []
    if first is not None and first.text.strip():
        sentence = _first_sentence(first.text)
        objectives.append(
            DraftText(text=sentence, source=DraftSource(doc_id=first.doc_id, quote=sentence))
        )
    output = ExtractorOutput(
        platform="ISS" if _ISS_MENTION.search(combined) else None,
        gravity_level="microgravity" if "microgravity" in combined.lower() else None,
        objectives=objectives,
        fire_safety_tags=_derive_tags(combined),
        open_questions=[EXTRACTOR_OPEN_QUESTION],
    )
    return output.model_dump_json()


# --- scorer --------------------------------------------------------------------------------


class _Rating(NamedTuple):
    value: int
    field_path: str
    quote: str


_Rule = Callable[[InvestigationCard], _Rating | None]


def _fuel_realism(card: InvestigationCard) -> _Rating | None:
    if not card.fuels:
        return None
    phases = {fuel.phase for fuel in card.fuels}
    value = 4 if "solid" in phases else 3 if "liquid" in phases else 0
    return _Rating(value, "fuels", ", ".join(f"{f.name} ({f.phase})" for f in card.fuels))


def _atmosphere_match(card: InvestigationCard) -> _Rating | None:
    conditions = card.conditions
    if conditions is None:
        return None
    o2_max = conditions.o2_fraction.max if conditions.o2_fraction else None
    pressure_min = conditions.pressure_kpa.min if conditions.pressure_kpa else None
    if o2_max is None and pressure_min is None:
        return None
    value = _atmosphere_value(o2_max, pressure_min)
    return _Rating(value, "conditions", f"o2 max {o2_max}, pressure min {pressure_min} kPa")


def _atmosphere_value(o2_max: float | None, pressure_min: float | None) -> int:
    elevated = o2_max is not None and o2_max > AIR_O2_FRACTION
    reduced = pressure_min is not None and pressure_min < SEA_LEVEL_KPA
    lunar = o2_max is not None and o2_max >= LUNAR_ENVELOPE_O2_FRACTION
    if lunar and reduced:
        return 5
    return 3 if elevated or reduced else 0


def _flow_regime(card: InvestigationCard) -> _Rating | None:
    flow = card.conditions.flow_speed_cm_s if card.conditions else None
    if flow is None or flow.min is None or flow.max is None:
        return None
    value = (5 if flow.min <= 0 else 4) if flow.max > flow.min else 3
    return _Rating(value, "conditions.flow_speed_cm_s", f"flow {flow.min} to {flow.max} cm/s")


def _gravity_bounding(card: InvestigationCard) -> _Rating | None:
    if "partial_gravity_analogue" in card.fire_safety_tags:
        return _Rating(5, "fire_safety_tags", "partial_gravity_analogue")
    levels = card.conditions.gravity_g if card.conditions else []
    if not levels:
        return None
    has_normal = FULL_GRAVITY_G in levels
    return _Rating(3 if has_normal else 0, "conditions.gravity_g", f"gravity {levels} g")


def _quantitative_outputs(card: InvestigationCard) -> _Rating | None:
    if not card.measurements:
        return None
    quantities = [m.quantity for m in card.measurements]
    quantified = any(k in q.lower() for q in quantities for k in QUANTITATIVE_KEYWORDS)
    return _Rating(5 if quantified else 3, "measurements", "; ".join(quantities))


def _parameter_sweep(card: InvestigationCard) -> _Rating | None:
    varied = card.variables.varied
    if not varied and not card.variables.fixed:
        return None
    value = 5 if len(varied) >= SWEEP_FULL_VARIED_COUNT else 3 if varied else 0
    return _Rating(value, "variables", f"varied: {', '.join(varied) or 'none'}")


def _geometry_definition(card: InvestigationCard) -> _Rating | None:
    if not card.fuels:
        return None
    shaped = [f for f in card.fuels if f.geometry and f.geometry.shape]
    complete = [f for f in shaped if f.geometry and any(f.geometry.dimensions_mm.values())]
    value = 5 if len(complete) == len(card.fuels) else 3 if shaped else 0
    return _Rating(value, "fuels", f"{len(complete)} of {len(card.fuels)} fuels fully specified")


def _data_accessibility(card: InvestigationCard) -> _Rating | None:
    types_present = {file_type.lower() for file_type in card.data.file_types}
    if not types_present:
        return None
    tabular = types_present & TABULAR_FILE_TYPES
    value = 5 if types_present <= TABULAR_FILE_TYPES else 3 if tabular else 0
    return _Rating(value, "data.file_types", ", ".join(sorted(types_present)))


def _model_validation(card: InvestigationCard) -> _Rating | None:
    if not card.publications:
        return None
    return _Rating(3, "publications", f"{len(card.publications)} publications referenced")


def _hardware_heritage(card: InvestigationCard) -> _Rating | None:
    if not card.hardware:
        return None
    value = 5 if any(item.role == "instrument" for item in card.hardware) else 3
    return _Rating(value, "hardware", ", ".join(item.name for item in card.hardware))


def _tag_rule(strong: set[str], related: set[str]) -> _Rule:
    def rule(card: InvestigationCard) -> _Rating | None:
        tags = set(card.fire_safety_tags)
        if not tags:
            return None
        value = 5 if tags & strong else 3 if tags & related else 0
        return _Rating(value, "fire_safety_tags", ", ".join(sorted(tags)))

    return rule


SCORING_RULES: dict[str, _Rule] = {
    "fuel_realism": _fuel_realism,
    "atmosphere_match": _atmosphere_match,
    "flow_regime": _flow_regime,
    "phenomenon": _tag_rule(
        {"ignition", "flame_spread", "flammability_limit", "extinction"}, {"soot", "cool_flame"}
    ),
    "gravity_bounding": _gravity_bounding,
    "quantitative_outputs": _quantitative_outputs,
    "parameter_sweep": _parameter_sweep,
    "geometry_definition": _geometry_definition,
    "data_accessibility": _data_accessibility,
    "model_validation": _model_validation,
    "detection": _tag_rule({"smoke_detection", "aerosol"}, {"soot"}),
    "suppression": _tag_rule({"suppression"}, {"extinction"}),
    "material_screening": _tag_rule({"material_screening"}, {"solid_fuel", "flammability_limit"}),
    "post_fire": _tag_rule({"post_fire", "cool_flame"}, {"soot", "aerosol"}),
    "hardware_heritage": _hardware_heritage,
}


def _score_criterion(criterion_id: str, card: InvestigationCard) -> ScorerCriterionScore:
    rule = SCORING_RULES.get(criterion_id)
    rating = rule(card) if rule else None
    if rating is None:
        return ScorerCriterionScore(criterion=criterion_id, rationale="No evidence in the card.")
    evidence = ScorerEvidence(field_path=rating.field_path, quote=truncate_quote(rating.quote))
    return ScorerCriterionScore(
        criterion=criterion_id,
        value=rating.value,
        rationale=f"Mock rule applied to card field {rating.field_path}.",
        evidence=[evidence],
    )


def _scorer_output(request: ScorerInput) -> str:
    scores = [_score_criterion(spec.id, request.card) for spec in request.criteria]
    return ScorerOutput(lens=request.lens, scores=scores).model_dump_json()


# --- comparator and scenario interpreter ---------------------------------------------------


def _matrix_sentence(row: MatrixRow) -> str:
    relation = "is the same" if row.same else "differs"
    return f"{row.label} {relation} across the compared investigations."


def _comparator_output(request: ComparatorInput) -> str:
    sentences = [SentenceWithFacts(text=f.text, fact_ids=[f.id]) for f in request.facts]
    sentences = sentences[:MAX_COMPARATOR_SENTENCES]
    fillers = [_matrix_sentence(row) for row in request.matrix] + [NO_CITED_FACTS_SENTENCE]
    index = 0
    while len(sentences) < MIN_COMPARATOR_SENTENCES:
        sentences.append(SentenceWithFacts(text=fillers[index % len(fillers)]))
        index += 1
    return ComparatorOutput(sentences=sentences).model_dump_json()


def _gravity_statement_sentence(request: ScenarioInterpreterInput) -> list[SentenceWithFacts]:
    gravity = request.scenario.gravity_g
    statement = request.gravity_bounding.statement
    if gravity is None or gravity in (0.0, FULL_GRAVITY_G) or not statement:
        return []
    matching = [fact.id for fact in request.facts if fact.text == statement]
    return [SentenceWithFacts(text=statement, fact_ids=matching)]


def _scenario_output(request: ScenarioInterpreterInput) -> str:
    sentences = _gravity_statement_sentence(request)
    cited = [SentenceWithFacts(text=f.text, fact_ids=[f.id]) for f in request.facts]
    sentences += cited[:SCENARIO_MAX_FACT_SENTENCES]
    if not sentences:
        sentences = [SentenceWithFacts(text=NO_CITED_FACTS_SENTENCE)]
    caveats = [
        f"{name} is {entry.state.replace('_', ' ')} in the catalog."
        for name, entry in request.coverage.items()
        if entry.state != "covered"
    ]
    return ScenarioInterpreterOutput(sentences=sentences, caveats=caveats).model_dump_json()


# --- insight QA ----------------------------------------------------------------------------


def _best_sentence(text: str, question_tokens: set[str]) -> str:
    sentences = [s for s in _SENTENCE_END.split(text.strip()) if s]
    if not sentences:
        return ""
    best = max(sentences, key=lambda s: len(question_tokens & set(_TOKEN.findall(s.lower()))))
    return truncate_quote(best)


def _insight_answer(request: InsightQAInput) -> str:
    question_tokens = set(_TOKEN.findall(request.question.lower()))
    cited = [
        f"{_best_sentence(chunk.text, question_tokens)} [c:{chunk.chunk_id}]"
        for chunk in request.chunks[:QA_MAX_CHUNK_SENTENCES]
    ]
    cited += [
        f"{truncate_quote(fact.text)} [f:{fact.id}]"
        for fact in request.card_facts[:QA_MAX_FACT_SENTENCES]
    ]
    return " ".join(cited) if cited else INSUFFICIENT_INFORMATION_SENTENCE


# --- Earth applications --------------------------------------------------------------------

CATEGORY_SECTORS: dict[str, EarthSector] = {
    "detection": "detection",
    "suppression": "firefighting",
    "material_screening": "building_safety",
    "post_fire": "industrial",
    "atmosphere_design": "building_safety",
    "fundamental": "industrial",
}


def _earth_apps_output(request: EarthAppsInput) -> str:
    known = {app.title for app in request.known_applications}
    by_category: dict[str, list[int]] = {}
    for finding in request.findings:
        by_category.setdefault(finding.category, []).append(finding.id)
    candidates = [
        EarthAppCandidate(
            title=f"Candidate from {category.replace('_', ' ')} findings",
            sector=CATEGORY_SECTORS[category],
            description=f"Mock candidate grouped from {len(ids)} finding(s); needs curation.",
            finding_ids=ids,
            confidence=EARTH_APP_CONFIDENCE,
        )
        for category, ids in sorted(by_category.items())
    ]
    kept = [item for item in candidates if item.title not in known]
    return EarthAppsOutput(applications=kept).model_dump_json()


SYNTHESIZERS: dict[str, Callable[[Any], str]] = {
    "extractor": _extractor_output,
    "scorer": _scorer_output,
    "comparator": _comparator_output,
    "scenario_interpreter": _scenario_output,
    "insight_qa": _insight_answer,
    "earth_apps": _earth_apps_output,
}
