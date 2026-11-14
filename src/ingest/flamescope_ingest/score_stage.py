"""Stage 7, score: seed scores or `ScorerAgent` per lens (document 06 section 3.7)."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

import structlog
from pydantic import BaseModel, Field

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import IngestError, LLMError
from flamescope_common.rubric import LENSES, Lens, Rubric
from flamescope_common.schemas.agents import (
    CriterionSpec,
    ScorerCriterionScore,
    ScorerEvidence,
    ScorerExcerpt,
    ScorerInput,
    ScorerOutput,
)
from flamescope_common.schemas.card import InvestigationCard, SeedInvestigation, SeedScore
from flamescope_common.sources import SourceRef, truncate_quote
from flamescope_ingest.normalizer import card_json
from flamescope_ingest.overrides import OverrideResult

logger = structlog.get_logger(__name__)

SCORER_AGENT = "scorer"
ORIGIN_LLM = "llm"
ORIGIN_SEED = "seed"
ORIGIN_OVERRIDE = "override"
MAX_EXCERPTS = 8


class ScoreRow(BaseModel):
    """One `relevance_score` row ready to upsert."""

    lens: str
    criterion: str
    value: float | None
    rationale: str = ""
    evidence: list[SourceRef] = Field(default_factory=list)
    rubric_version: str
    origin: str


class ChunkExcerpt(BaseModel):
    """A stored chunk offered to the scorer as evidence."""

    chunk_id: int
    text: str
    source: SourceRef


@dataclass
class ScoreOutcome:
    rows: list[ScoreRow] = field(default_factory=list)
    llm_calls: int = 0
    skipped_lenses: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unknown_criteria: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreRequest:
    """Everything one scoring pass needs besides the record."""

    overrides: OverrideResult
    scored_lenses: Collection[str] = ()
    excerpts: Sequence[ChunkExcerpt] = ()
    force: bool = False


class ScoreStage:
    """Produces `ScoreRow`s per lens; writing them is the loader's job."""

    def __init__(self, orchestrator: AgentOrchestrator, rubric: Rubric) -> None:
        self._orchestrator = orchestrator
        self._rubric = rubric

    @property
    def rubric_version(self) -> str:
        return self._rubric.rubric_version

    @property
    def prompt_version(self) -> str:
        return self._orchestrator.prompt_version(SCORER_AGENT)

    def score(self, record: SeedInvestigation, request: ScoreRequest) -> ScoreOutcome:
        outcome = ScoreOutcome()
        for lens in LENSES:
            given = self._seed_rows(record, lens, request.overrides, outcome)
            outcome.rows += given
            missing = self._missing_criteria(lens, given)
            if not missing:
                continue
            if lens in request.scored_lenses and not request.force:
                outcome.skipped_lenses.append(lens)
                continue
            self._score_with_agent(record, lens, missing, request, outcome)
        return outcome

    def _missing_criteria(self, lens: Lens, given: Sequence[ScoreRow]) -> list[str]:
        present = {row.criterion for row in given}
        return [cid for cid in self._rubric.criterion_ids(lens) if cid not in present]

    def _seed_rows(
        self,
        record: SeedInvestigation,
        lens: Lens,
        overrides: OverrideResult,
        outcome: ScoreOutcome,
    ) -> list[ScoreRow]:
        known = set(self._rubric.criterion_ids(lens))
        rows: list[ScoreRow] = []
        for criterion, score in record.scores.get(lens, {}).items():
            if criterion not in known:
                outcome.unknown_criteria.append(f"{lens}.{criterion}")
                continue
            origin = (
                ORIGIN_OVERRIDE if overrides.covers(f"scores.{lens}.{criterion}") else ORIGIN_SEED
            )
            rows.append(self._row_from_seed(lens, criterion, score, origin))
        return rows

    def _row_from_seed(
        self, lens: Lens, criterion: str, score: SeedScore, origin: str
    ) -> ScoreRow:
        return ScoreRow(
            lens=lens,
            criterion=criterion,
            value=score.value,
            rationale=score.rationale,
            evidence=score.evidence,
            rubric_version=self._rubric.rubric_version,
            origin=origin,
        )

    def _score_with_agent(
        self,
        record: SeedInvestigation,
        lens: Lens,
        missing: Sequence[str],
        request: ScoreRequest,
        outcome: ScoreOutcome,
    ) -> None:
        outcome.llm_calls += 1
        try:
            output = self._run_scorer(record, lens, request.excerpts)
        except LLMError as error:
            logger.warning("score_failed", acronym=record.acronym, lens=lens, error=str(error))
            outcome.errors.append(f"scorer {lens}: {error.message}")
            return
        sources = {excerpt.chunk_id: excerpt.source for excerpt in request.excerpts}
        returned = {item.criterion: item for item in output.scores}
        for criterion in missing:
            outcome.rows.append(self._row_from_agent(record, lens, criterion, returned, sources))

    def _run_scorer(
        self, record: SeedInvestigation, lens: Lens, excerpts: Sequence[ChunkExcerpt]
    ) -> ScorerOutput:
        payload = ScorerInput(
            acronym=record.acronym,
            lens=lens,
            criteria=[
                CriterionSpec(id=c.id, label=c.label, description=c.description, anchors=c.anchors)
                for c in self._rubric.criteria(lens)
            ],
            card=InvestigationCard.model_validate(card_json(record)),
            excerpts=[
                ScorerExcerpt(chunk_id=e.chunk_id, text=e.text) for e in excerpts[:MAX_EXCERPTS]
            ],
        )
        output = asyncio.run(self._orchestrator.run(SCORER_AGENT, payload))
        if not isinstance(output, ScorerOutput):
            raise IngestError("Scorer returned an unexpected output type", {"lens": lens})
        return output

    def _row_from_agent(
        self,
        record: SeedInvestigation,
        lens: Lens,
        criterion: str,
        returned: Mapping[str, ScorerCriterionScore],
        sources: Mapping[int, SourceRef],
    ) -> ScoreRow:
        """A criterion the agent skipped is stored as null: no evidence."""
        item = returned.get(criterion)
        value = float(item.value) if item is not None and item.value is not None else None
        evidence = [_evidence_source(e, record, sources) for e in item.evidence] if item else []
        return ScoreRow(
            lens=lens,
            criterion=criterion,
            value=value,
            rationale=item.rationale if item else "",
            evidence=evidence if value is not None else [],
            rubric_version=self._rubric.rubric_version,
            origin=ORIGIN_LLM,
        )


def _evidence_source(
    evidence: ScorerEvidence, record: SeedInvestigation, chunk_sources: Mapping[int, SourceRef]
) -> SourceRef:
    quote = truncate_quote(evidence.quote)
    known = chunk_sources.get(evidence.chunk_id) if evidence.chunk_id is not None else None
    if known is not None:
        return known.model_copy(update={"chunk_id": evidence.chunk_id, "quote": quote})
    locator = (
        f"card.{evidence.field_path}" if evidence.field_path else f"chunk {evidence.chunk_id}"
    )
    return SourceRef(
        kind="psi_page",
        uri=record.psi_url,
        title=record.title,
        locator=locator,
        quote=quote,
    )
