"""`CompareService`: side-by-side matrix, shared facts and an optional cited narrative."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import structlog
from pydantic import JsonValue

from flamescope_agents.citation_verifier import CitationVerifier, ContextEntry
from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_api.repositories.investigations import InvestigationRepo
from flamescope_api.services.catalog import build_summary
from flamescope_api.services.ranking import RankingService
from flamescope_common.errors import LLMError, ValidationError
from flamescope_common.schemas.agents import ComparatorInput, ComparatorOutput, Fact
from flamescope_common.schemas.api import (
    CompareResponse,
    DiffMatrix,
    InvestigationSummary,
    MatrixRow,
    Narrative,
    NarrativeSentence,
    SharedFacts,
)
from flamescope_common.schemas.card import InvestigationCard, ValueRange
from flamescope_common.sources import SourceRef

logger = structlog.get_logger(__name__)

MIN_COMPARE_IDS = 2
MAX_COMPARE_IDS = 4


@dataclass(frozen=True)
class _Attribute:
    name: str
    label: str
    group: str
    extract: Callable[[InvestigationCard], JsonValue]


def _sorted_unique(values: Sequence[str]) -> list[JsonValue]:
    ordered: list[JsonValue] = [*sorted(set(values))]
    return ordered


def _range(stated: ValueRange | None) -> JsonValue:
    """`[min, max]`; a null end of a half-open range stays null (open, doc 04 s2)."""
    if stated is None or (stated.min is None and stated.max is None):
        return None
    return [stated.min, stated.max]


def _conditions_range(card: InvestigationCard, name: str) -> JsonValue:
    if card.conditions is None:
        return None
    return _range(getattr(card.conditions, name))


def _flow_directions(card: InvestigationCard) -> JsonValue:
    return _sorted_unique(card.conditions.flow_direction) if card.conditions else []


def _shapes(card: InvestigationCard) -> JsonValue:
    return _sorted_unique(
        [fuel.geometry.shape for fuel in card.fuels if fuel.geometry and fuel.geometry.shape]
    )


ATTRIBUTES: tuple[_Attribute, ...] = (
    _Attribute("project", "Project", "context", lambda card: card.project),
    _Attribute("platform", "Platform", "context", lambda card: card.platform),
    _Attribute("gravity_level", "Gravity level", "context", lambda card: card.gravity_level),
    _Attribute(
        "hardware",
        "Hardware",
        "hardware",
        lambda card: _sorted_unique([h.name for h in card.hardware]),
    ),
    _Attribute(
        "fuel_phase",
        "Fuel phase",
        "fuel",
        lambda card: _sorted_unique([f.phase for f in card.fuels]),
    ),
    _Attribute(
        "fuel_materials",
        "Fuel materials",
        "fuel",
        lambda card: _sorted_unique([f.name for f in card.fuels]),
    ),
    _Attribute("geometry", "Sample geometry", "fuel", _shapes),
    _Attribute(
        "o2_range",
        "Oxygen fraction range",
        "conditions",
        lambda card: _conditions_range(card, "o2_fraction"),
    ),
    _Attribute(
        "pressure_range_kpa",
        "Pressure range (kPa)",
        "conditions",
        lambda card: _conditions_range(card, "pressure_kpa"),
    ),
    _Attribute(
        "flow_range_cm_s",
        "Flow speed range (cm/s)",
        "conditions",
        lambda card: _conditions_range(card, "flow_speed_cm_s"),
    ),
    _Attribute("flow_direction", "Flow direction", "conditions", _flow_directions),
    _Attribute(
        "varied_parameters",
        "Varied parameters",
        "variables",
        lambda card: _sorted_unique(card.variables.varied),
    ),
    _Attribute(
        "measurements",
        "Measurements",
        "measurements",
        lambda card: _sorted_unique([m.quantity for m in card.measurements]),
    ),
    _Attribute(
        "phenomena",
        "Phenomena (tags)",
        "phenomena",
        lambda card: _sorted_unique(card.fire_safety_tags),
    ),
    _Attribute("data_volume", "Data volume (bytes)", "data", lambda card: card.data.volume_bytes),
)


def diff_matrix(cards: Sequence[InvestigationCard]) -> DiffMatrix:
    """One row per attribute of document 05 section 6, in the documented order."""
    rows: DiffMatrix = []
    for attribute in ATTRIBUTES:
        values = {card.acronym: attribute.extract(card) for card in cards}
        rows.append(
            MatrixRow(
                attribute=attribute.name,
                label=attribute.label,
                group=attribute.group,
                values=values,
                same=len({repr(value) for value in values.values()}) <= 1,
            )
        )
    return rows


def shared_facts(cards: Sequence[InvestigationCard]) -> SharedFacts:
    """Hardware, tags and instruments present in every compared investigation."""

    def common(selector: Callable[[InvestigationCard], set[str]]) -> list[str]:
        sets = [selector(card) for card in cards]
        return sorted(set.intersection(*sets)) if sets else []

    return SharedFacts(
        hardware=common(lambda card: {item.name for item in card.hardware}),
        tags=common(lambda card: set(card.fire_safety_tags)),
        instruments=common(lambda card: {item.instrument for item in card.measurements}),
    )


def card_facts(cards: Sequence[InvestigationCard]) -> list[Fact]:
    """Citable statements taken from source-bearing card fields."""
    statements: list[tuple[str, SourceRef]] = []
    for card in cards:
        statements += [(f"{card.acronym}: {item.text}", item.source) for item in card.objectives]
        statements += [
            (f"{card.acronym} burns {fuel.name} ({fuel.phase} fuel).", fuel.source)
            for fuel in card.fuels
        ]
        statements += _condition_statements(card)
        statements += [
            (f"{card.acronym} measures {item.quantity} with {item.instrument}.", item.source)
            for item in card.measurements
        ]
        statements += [
            (f"{card.acronym}: {item.statement}", item.source) for item in card.findings
        ]
    return [
        Fact(id=f"F{number}", text=text, source=source)
        for number, (text, source) in enumerate(statements, start=1)
    ]


def _condition_statements(card: InvestigationCard) -> list[tuple[str, SourceRef]]:
    if card.conditions is None:
        return []
    labelled = (
        ("oxygen fraction", card.conditions.o2_fraction),
        ("pressure (kPa)", card.conditions.pressure_kpa),
        ("flow speed (cm/s)", card.conditions.flow_speed_cm_s),
    )
    return [
        (f"{card.acronym} covers {label} from {stated.min:g} to {stated.max:g}.", stated.source)
        for label, stated in labelled
        if stated and stated.min is not None and stated.max is not None and stated.source
    ]


def _narrative(
    output: ComparatorOutput, facts: Sequence[Fact], verifier: CitationVerifier
) -> Narrative:
    context = {fact.id: ContextEntry(fact.text, fact.source) for fact in facts}
    verified = verifier.verify(output.sentences, context)
    kept = [item for item in verified.sentences if item.citations]
    if not kept:
        return Narrative(status="unavailable")
    return Narrative(
        text=" ".join(item.text for item in kept),
        sentences=[NarrativeSentence(text=item.text, citations=item.citations) for item in kept],
        status="ok",
    )


class CompareService:
    """Compare 2 to 4 investigations; the narrative is the only LLM call."""

    def __init__(
        self,
        investigations: InvestigationRepo,
        ranking: RankingService,
        orchestrator: AgentOrchestrator,
        verifier: CitationVerifier,
    ) -> None:
        self._investigations = investigations
        self._ranking = ranking
        self._orchestrator = orchestrator
        self._verifier = verifier

    async def compare(self, ids: Sequence[str], narrative: bool) -> CompareResponse:
        """Matrix and shared facts always; narrative when requested and the LLM answers."""
        if not MIN_COMPARE_IDS <= len(ids) <= MAX_COMPARE_IDS:
            raise ValidationError(
                f"Compare needs {MIN_COMPARE_IDS} to {MAX_COMPARE_IDS} investigations, "
                f"got {len(ids)}"
            )
        summaries, cards = await asyncio.to_thread(self._load, ids)
        matrix = diff_matrix(cards)
        shared = shared_facts(cards)
        result = Narrative(status="skipped")
        if narrative:
            result = await self._narrate(summaries, matrix, shared, cards)
        return CompareResponse(
            investigations=summaries, matrix=matrix, shared=shared, narrative=result
        )

    def _load(
        self, ids: Sequence[str]
    ) -> tuple[list[InvestigationSummary], list[InvestigationCard]]:
        rows = [self._investigations.get(identifier) for identifier in ids]
        if len({row.investigation.id for row in rows}) != len(rows):
            raise ValidationError(
                "Compare needs distinct investigations", {"investigations": list(ids)}
            )
        scores = self._ranking.score_sets([row.investigation.id for row in rows])
        summaries = [build_summary(row, scores.get(row.investigation.id)) for row in rows]
        cards = [InvestigationCard.model_validate(row.investigation.card) for row in rows]
        return summaries, cards

    async def _narrate(
        self,
        summaries: Sequence[InvestigationSummary],
        matrix: DiffMatrix,
        shared: SharedFacts,
        cards: Sequence[InvestigationCard],
    ) -> Narrative:
        facts = card_facts(cards)
        payload = ComparatorInput(
            investigations=[summary.model_dump(mode="json") for summary in summaries],
            matrix=matrix,
            shared=shared,
            facts=facts,
        )
        try:
            output = await self._orchestrator.run("comparator", payload)
        except LLMError as error:
            logger.warning("compare_narrative_unavailable", error=error.message)
            return Narrative(status="unavailable")
        if not isinstance(output, ComparatorOutput):
            return Narrative(status="unavailable")
        return _narrative(output, facts, self._verifier)
