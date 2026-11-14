"""`ScenarioService`: match a scenario to catalog runs (document 08 section 4).

The pure functions `distance`, `coverage` and `gravity_bounding` live in `scenario_math` and
are re-exported here (DC-15).
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Collection, Mapping, Sequence

import structlog

from flamescope_agents.citation_verifier import CitationVerifier, ContextEntry
from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_api.repositories.investigations import InvestigationRepo
from flamescope_api.repositories.runs import RunRecord, RunRepo
from flamescope_api.services.scenario_math import (
    NUMERIC_DIMENSIONS,
    coverage,
    distance,
    gravity_bounding,
    rank_matches,
)
from flamescope_common.errors import LLMError, ValidationError
from flamescope_common.rubric import Presets
from flamescope_common.schemas.agents import (
    TOP_MATCHES_FOR_INTERPRETATION,
    Fact,
    ScenarioInterpreterInput,
    ScenarioInterpreterOutput,
)
from flamescope_common.schemas.api import (
    CoverageEntry,
    GravityAnalogue,
    GravityBounding,
    InvestigationFilters,
    Narrative,
    NarrativeSentence,
    RangePair,
    ResolvedScenario,
    ScenarioMatch,
    ScenarioRequest,
    ScenarioResponse,
    ScenarioWeights,
)
from flamescope_common.schemas.card import CoverageState, FireSafetyTag
from flamescope_common.sources import SourceRef

logger = structlog.get_logger(__name__)

ANALOGUE_TAG: FireSafetyTag = "partial_gravity_analogue"
VALUE_FIELDS = (
    "o2_fraction",
    "pressure_kpa",
    "gravity_g",
    "flow_speed_cm_s",
    "fuel_phase",
    "material",
)
DIMENSION_LABELS = {
    "o2_fraction": "Oxygen fraction",
    "pressure_kpa": "Pressure (kPa)",
    "flow_speed_cm_s": "Flow speed (cm/s)",
    "gravity_g": "Gravity (g)",
}

BASE64_BLOCK = 4
BASE64_PAD = "="
CANONICAL_SEPARATORS = (",", ":")


def resolve_scenario(request: ScenarioRequest, presets: Presets) -> ResolvedScenario:
    """Preset values overridden by explicit values (document 05 section 7)."""
    values: dict[str, object] = {}
    assumed_default = False
    if request.preset is not None:
        preset = presets.scenario.get(request.preset)
        if preset is None:
            raise ValidationError(
                f"Unknown scenario preset {request.preset!r}", {"known": sorted(presets.scenario)}
            )
        values = {
            "o2_fraction": preset.o2_fraction,
            "pressure_kpa": preset.pressure_kpa,
            "gravity_g": preset.gravity_g,
            "flow_speed_cm_s": preset.flow_speed_cm_s,
        }
        assumed_default = preset.assumed_default
    explicit = request.model_dump(include=set(VALUE_FIELDS), exclude_none=True)
    if explicit:
        assumed_default = False
    values.update(explicit)
    if not values:
        raise ValidationError("Give a preset or at least one scenario value")
    return ResolvedScenario.model_validate(
        {
            **values,
            "preset": request.preset,
            "weights": request.weights or ScenarioWeights(),
            "assumed_default": assumed_default,
        }
    )


def scenario_id_of(scenario: ResolvedScenario) -> str:
    """Unpadded URL-safe base64 of the canonical JSON of the resolved scenario (doc 05 s7)."""
    canonical = json.dumps(
        scenario.model_dump(mode="json"), sort_keys=True, separators=CANONICAL_SEPARATORS
    )
    return base64.urlsafe_b64encode(canonical.encode()).decode().rstrip(BASE64_PAD)


def scenario_from_id(scenario_id: str) -> ResolvedScenario:
    """Invert `scenario_id_of`; any undecodable or invalid id is a `bad_request` (doc 05 s8)."""
    padding = BASE64_PAD * (-len(scenario_id) % BASE64_BLOCK)
    # binascii, Unicode and Pydantic validation errors all subclass ValueError.
    try:
        canonical = base64.urlsafe_b64decode(scenario_id + padding).decode()
        return ResolvedScenario.model_validate_json(canonical)
    except ValueError as error:
        raise ValidationError(
            "Invalid scenario_id; use the scenario_id returned by POST /scenario",
            {"scenario_id": scenario_id},
        ) from error


def _has_distance_dimension(scenario: ResolvedScenario) -> bool:
    return any(
        getattr(scenario, name) is not None for name in NUMERIC_DIMENSIONS.values()
    ) or bool(scenario.material or scenario.fuel_phase)


def _coverage_entries(
    states: Mapping[str, CoverageState],
    ranges: Mapping[str, RangePair],
    gravity_values: Collection[float],
) -> dict[str, CoverageEntry]:
    entries = {}
    for dimension, state in states.items():
        if dimension == "gravity_g":
            entries[dimension] = CoverageEntry(state=state, catalog_values=sorted(gravity_values))
        else:
            entries[dimension] = CoverageEntry(state=state, catalog_range=ranges.get(dimension))
    return entries


def coverage_caveats(
    scenario: ResolvedScenario, entries: Mapping[str, CoverageEntry], statement: str | None
) -> list[str]:
    """Deterministic caveats for every `extrapolated` or `no_data` dimension."""
    caveats = []
    for dimension, entry in entries.items():
        if entry.state == "covered":
            continue
        label = DIMENSION_LABELS[dimension]
        value = getattr(scenario, dimension)
        reason = (
            "lies outside the catalog range"
            if entry.state == "extrapolated"
            else "has no catalog data"
        )
        caveats.append(f"{label} {value:g} {reason} ({entry.state}).")
    if statement:
        caveats.append(statement)
    return caveats


def _run_facts(matches: Sequence[ScenarioMatch], runs: Sequence[RunRecord]) -> list[Fact]:
    by_id = {run.run_id: run for run in runs}
    facts: list[Fact] = []
    for match in matches[:TOP_MATCHES_FOR_INTERPRETATION]:
        run = by_id.get(match.best_run.id) if match.best_run else None
        if run is None or not run.source:
            continue
        parts = [
            f"{label} {value:g}"
            for label, value in (
                ("oxygen fraction", run.o2_fraction),
                ("pressure (kPa)", run.pressure_kpa),
                ("flow speed (cm/s)", run.flow_speed_cm_s),
                ("gravity (g)", run.gravity_g),
            )
            if value is not None
        ]
        text = f"{run.investigation} run {run.label}: " + ", ".join(parts) + "."
        facts.append(
            Fact(id=f"R{len(facts) + 1}", text=text, source=SourceRef.model_validate(run.source))
        )
    return facts


class ScenarioService:
    """Match a scenario against catalog runs; the explanation is the only LLM call."""

    def __init__(
        self,
        runs: RunRepo,
        investigations: InvestigationRepo,
        presets: Presets,
        orchestrator: AgentOrchestrator,
        verifier: CitationVerifier,
    ) -> None:
        self._runs = runs
        self._investigations = investigations
        self._presets = presets
        self._orchestrator = orchestrator
        self._verifier = verifier

    async def match(self, scenario: ScenarioRequest, explain: bool) -> ScenarioResponse:
        resolved = resolve_scenario(scenario, self._presets)
        ranges, runs, analogue = await asyncio.to_thread(self._load)
        gravity_values = {run.gravity_g for run in runs if run.gravity_g is not None}
        states = coverage(resolved, ranges, gravity_values)
        entries = _coverage_entries(states, ranges, gravity_values)
        matches = rank_matches(resolved, runs, ranges) if _has_distance_dimension(resolved) else []
        top = matches[: scenario.limit]
        bounding = self._bounding(resolved, runs, top, analogue)
        explanation = Narrative(status="skipped")
        if explain and top:
            explanation = await self._explain(resolved, entries, top, bounding, runs)
        return ScenarioResponse(
            scenario=resolved,
            coverage=entries,
            matches=top,
            gravity_bounding=bounding,
            explanation=explanation,
            scenario_id=scenario_id_of(resolved),
        )

    def _load(self) -> tuple[dict[str, RangePair], list[RunRecord], GravityAnalogue | None]:
        ranges = self._runs.condition_ranges()
        runs = self._runs.query(None)
        tagged = self._investigations.search(InvestigationFilters(tag=[ANALOGUE_TAG]), None)
        analogue = None
        if tagged.rows:
            item = tagged.rows[0].investigation
            objectives = item.objectives or []
            note = (
                (objectives[0].get("text") if objectives else None) or item.summary or item.title
            )
            analogue = GravityAnalogue(acronym=item.acronym, note=note)
        return ranges, runs, analogue

    def _bounding(
        self,
        scenario: ResolvedScenario,
        runs: Sequence[RunRecord],
        top: Sequence[ScenarioMatch],
        analogue: GravityAnalogue | None,
    ) -> GravityBounding:
        statement = None
        if scenario.gravity_g is not None:
            statement = self._presets.gravity_bounding_statement(scenario.gravity_g)
        return gravity_bounding(
            scenario,
            runs,
            top_acronyms={match.acronym for match in top},
            analogue=analogue,
            statement=statement,
        )

    async def _explain(
        self,
        scenario: ResolvedScenario,
        entries: Mapping[str, CoverageEntry],
        matches: Sequence[ScenarioMatch],
        bounding: GravityBounding,
        runs: Sequence[RunRecord],
    ) -> Narrative:
        facts = _run_facts(matches, runs)
        payload = ScenarioInterpreterInput(
            scenario=scenario,
            coverage=dict(entries),
            matches=list(matches[:TOP_MATCHES_FOR_INTERPRETATION]),
            gravity_bounding=bounding,
            facts=facts,
        )
        try:
            output = await self._orchestrator.run("scenario_interpreter", payload)
        except LLMError as error:
            logger.warning("scenario_explanation_unavailable", error=error.message)
            return Narrative(status="unavailable")
        if not isinstance(output, ScenarioInterpreterOutput):
            return Narrative(status="unavailable")
        context = {fact.id: ContextEntry(fact.text, fact.source) for fact in facts}
        verified = [
            item
            for item in self._verifier.verify(output.sentences, context).sentences
            if item.citations
        ]
        if not verified:
            return Narrative(status="unavailable")
        sentences = [
            NarrativeSentence(text=item.text, citations=item.citations) for item in verified
        ]
        sentences += [
            NarrativeSentence(text=caveat)
            for caveat in coverage_caveats(scenario, entries, bounding.statement)
        ]
        return Narrative(
            text=" ".join(item.text for item in sentences), sentences=sentences, status="ok"
        )


__all__ = [
    "ScenarioService",
    "coverage",
    "distance",
    "gravity_bounding",
    "scenario_from_id",
    "scenario_id_of",
]
