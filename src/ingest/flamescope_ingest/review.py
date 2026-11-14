"""Stage 9, review: fields a curator should look at (document 06 section 3.9).

In harvest mode the stage also asks `EarthAppsAgent` for candidate Earth applications and
writes them to the raw volume for a human to curate; they never reach the database.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, get_args

from pydantic import BaseModel, Field

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.errors import IngestError, LLMError
from flamescope_common.models import Finding
from flamescope_common.schemas.agents import (
    EarthAppCandidate,
    EarthAppsInput,
    EarthAppsOutput,
    EarthFinding,
    KnownApplication,
)
from flamescope_common.schemas.api import EarthSector
from flamescope_common.schemas.card import SeedInvestigation
from flamescope_ingest.discover import RawLayout, read_json, write_json
from flamescope_ingest.seed import EarthApplicationCatalog

REQUIRED_FIELDS = (
    "platform",
    "gravity_level",
    "summary",
    "approach",
    "objectives",
    "fuels",
    "conditions",
    "measurements",
    "findings",
    "publications",
)
LOW_CONFIDENCE_THRESHOLD = 0.5
KIND_NULL_FIELD = "null_required_field"
KIND_LOW_CONFIDENCE = "low_confidence"
KIND_QUOTE_FAILURE = "quote_verification_failure"
KIND_NO_RUNS = "no_runs"
KIND_NULL_SCORE = "null_score"
KIND_EARTH_CANDIDATE = "earth_candidate"
TABLE_COLUMNS = ("acronym", "kind", "field", "detail")
EARTH_APPS_AGENT = "earth_apps"
EARTH_SECTORS = frozenset(get_args(EarthSector))


class ReviewItem(BaseModel):
    acronym: str
    kind: str
    field: str
    detail: str = ""


@dataclass
class ReviewFacts:
    """What the database and the extract stage know beyond the card itself."""

    run_count: int
    null_scores: Sequence[str] = ()
    quote_failures: Sequence[str] = field(default_factory=list)


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, list | dict) and not value)


def _null_fields(record: SeedInvestigation) -> list[ReviewItem]:
    return [
        ReviewItem(acronym=record.acronym, kind=KIND_NULL_FIELD, field=name)
        for name in REQUIRED_FIELDS
        if _is_missing(getattr(record, name))
    ]


def _low_confidence(record: SeedInvestigation) -> list[ReviewItem]:
    return [
        ReviewItem(
            acronym=record.acronym,
            kind=KIND_LOW_CONFIDENCE,
            field=name,
            detail=f"confidence {confidence:g}",
        )
        for name, confidence in sorted(record.field_confidence.items())
        if confidence < LOW_CONFIDENCE_THRESHOLD
    ]


def review_record(record: SeedInvestigation, facts: ReviewFacts) -> list[ReviewItem]:
    """Review items for one investigation; never raises, the pipeline always continues."""
    items = _null_fields(record) + _low_confidence(record)
    items += [
        ReviewItem(acronym=record.acronym, kind=KIND_QUOTE_FAILURE, field=path)
        for path in facts.quote_failures
    ]
    if facts.run_count == 0:
        items.append(ReviewItem(acronym=record.acronym, kind=KIND_NO_RUNS, field="runs"))
    items += [
        ReviewItem(acronym=record.acronym, kind=KIND_NULL_SCORE, field=key)
        for key in facts.null_scores
    ]
    return items


class EarthCandidates(BaseModel):
    """`/data/raw/<acronym>/earth_candidates.json`: unreviewed `EarthAppsAgent` output."""

    acronym: str
    prompt_version: str
    input_hash: str
    applications: list[EarthAppCandidate] = Field(default_factory=list)


@dataclass
class EarthCandidateOutcome:
    candidates: list[EarthAppCandidate]
    llm_calls: int = 0
    errors: list[str] = field(default_factory=list)


def known_applications(catalog: EarthApplicationCatalog) -> list[KnownApplication]:
    """Curated applications the agent must not repeat; off-vocabulary sectors are left out."""
    return [
        KnownApplication.model_validate({"title": entry.title, "sector": entry.sector})
        for entry in catalog.applications
        if entry.sector in EARTH_SECTORS
    ]


def earth_findings(acronym: str, rows: Iterable[Finding]) -> list[EarthFinding]:
    return [
        EarthFinding.model_validate(
            {
                "id": row.id,
                "acronym": acronym,
                "statement": row.statement,
                "category": row.category,
            }
        )
        for row in rows
    ]


def _grounded(
    candidates: Iterable[EarthAppCandidate], finding_ids: set[int]
) -> list[EarthAppCandidate]:
    """Keep only candidates citing supplied findings; unknown ids are removed, not trusted."""
    kept = []
    for candidate in candidates:
        cited = [finding_id for finding_id in candidate.finding_ids if finding_id in finding_ids]
        if cited:
            kept.append(candidate.model_copy(update={"finding_ids": cited}))
    return kept


def _input_hash(payload: EarthAppsInput, prompt_version: str) -> str:
    """Idempotency key: the candidates are reused while findings and prompt are unchanged."""
    return hashlib.sha256(f"{prompt_version}\n{payload.model_dump_json()}".encode()).hexdigest()


class EarthCandidateWriter:
    """Calls `EarthAppsAgent` for one investigation and writes the candidates to the raw volume."""

    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        layout: RawLayout,
        known: Sequence[KnownApplication],
    ) -> None:
        self._orchestrator = orchestrator
        self._layout = layout
        self._known = list(known)

    def propose(
        self, acronym: str, findings: Sequence[EarthFinding], *, force: bool = False
    ) -> EarthCandidateOutcome:
        if not findings:
            return EarthCandidateOutcome(candidates=[])
        payload = EarthAppsInput(findings=list(findings), known_applications=self._known)
        version = self._orchestrator.prompt_version(EARTH_APPS_AGENT)
        artifact = EarthCandidates(
            acronym=acronym, prompt_version=version, input_hash=_input_hash(payload, version)
        )
        stored = None if force else self._stored(acronym, artifact.input_hash)
        if stored is not None:
            return EarthCandidateOutcome(candidates=stored.applications)
        try:
            proposed = self._call_agent(payload)
        except LLMError as error:
            # Review always completes (document 06 section 3.9); the failure is reported.
            return EarthCandidateOutcome(
                candidates=[], errors=[f"earth candidates: {error.message}"]
            )
        artifact.applications = _grounded(proposed, {finding.id for finding in findings})
        write_json(self._layout.earth_candidates_path(acronym), artifact.model_dump(mode="json"))
        return EarthCandidateOutcome(candidates=artifact.applications, llm_calls=1)

    def _stored(self, acronym: str, input_hash: str) -> EarthCandidates | None:
        path = self._layout.earth_candidates_path(acronym)
        if not path.is_file():
            return None
        stored = EarthCandidates.model_validate(read_json(path))
        return stored if stored.input_hash == input_hash else None

    def _call_agent(self, payload: EarthAppsInput) -> list[EarthAppCandidate]:
        output = asyncio.run(self._orchestrator.run(EARTH_APPS_AGENT, payload))
        if not isinstance(output, EarthAppsOutput):
            raise IngestError("Earth applications agent returned an unexpected output type")
        return output.applications


def candidate_items(acronym: str, candidates: Iterable[EarthAppCandidate]) -> list[ReviewItem]:
    """One review line per unreviewed Earth application candidate."""
    return [
        ReviewItem(
            acronym=acronym,
            kind=KIND_EARTH_CANDIDATE,
            field=candidate.title,
            detail=(
                f"{candidate.sector}; findings "
                f"{', '.join(str(i) for i in candidate.finding_ids)}; "
                f"confidence {candidate.confidence:g}"
            ),
        )
        for candidate in candidates
    ]


def render_table(items: Iterable[ReviewItem]) -> str:
    """A fixed-width console table; an empty review renders a single line."""
    rows = [tuple(getattr(item, column) for column in TABLE_COLUMNS) for item in items]
    if not rows:
        return "No review items."
    widths = [
        max(len(str(row[i])) for row in [TABLE_COLUMNS, *rows]) for i in range(len(TABLE_COLUMNS))
    ]
    lines = [
        "  ".join(str(cell).ljust(width) for cell, width in zip(row, widths, strict=True))
        for row in [TABLE_COLUMNS, *rows]
    ]
    return "\n".join(lines)
