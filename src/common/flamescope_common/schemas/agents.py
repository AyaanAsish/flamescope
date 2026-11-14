"""Input and output models for every agent (document 07 section 3)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from flamescope_common.rubric import Lens
from flamescope_common.schemas.api import (
    CoverageEntry,
    EarthSector,
    GravityBounding,
    MatrixRow,
    ResolvedScenario,
    ScenarioMatch,
    SharedFacts,
    VerifiedSentence,
)
from flamescope_common.schemas.card import (
    FindingCategory,
    FireSafetyTag,
    FlowDirection,
    FuelPhase,
    GravityLevel,
    HardwareRole,
    InvestigationCard,
    Platform,
)
from flamescope_common.sources import MAX_QUOTE_CHARS, SourceRef

INSUFFICIENT_INFORMATION_SENTENCE = (
    "The curated PSI corpus does not contain enough information to answer that."
)
MIN_COMPARATOR_SENTENCES = 4
MAX_COMPARATOR_SENTENCES = 7
SCORE_MIN = 0
SCORE_MAX = 5
TOP_MATCHES_FOR_INTERPRETATION = 5


class AgentModel(BaseModel):
    """Base for agent contracts; unknown keys are rejected so schema drift is caught."""

    model_config = ConfigDict(extra="forbid")


# --- shared --------------------------------------------------------------------------------


class Fact(AgentModel):
    """A citable statement supplied to the comparator and the scenario interpreter."""

    id: str
    text: str
    source: SourceRef


class SentenceWithFacts(AgentModel):
    text: str
    fact_ids: list[str] = Field(default_factory=list)


class VerifiedAnswer(AgentModel):
    """Result of `CitationVerifier.verify`: kept sentences and the number dropped."""

    sentences: list[VerifiedSentence]
    dropped: int = 0
    text: str = ""


# --- extractor -----------------------------------------------------------------------------


class ExtractorContextItem(AgentModel):
    doc_id: str
    title: str
    section: str | None = None
    text: str


class ExtractorInput(AgentModel):
    acronym: str
    title: str
    psi_url: str
    context: list[ExtractorContextItem]


class DraftSource(AgentModel):
    """Extractor source: the document ID given in the context and a verbatim quote."""

    doc_id: str
    quote: str | None = Field(default=None, max_length=MAX_QUOTE_CHARS)


class DraftRange(AgentModel):
    min: float | None = None
    max: float | None = None
    source: DraftSource | None = None


class DraftText(AgentModel):
    text: str
    source: DraftSource


class DraftFuel(AgentModel):
    name: str
    phase: FuelPhase
    material_class: str | None = None
    shape: str | None = None
    dimensions_mm: dict[str, float | None] = Field(default_factory=dict)
    source: DraftSource


class DraftConditions(AgentModel):
    o2_fraction: DraftRange | None = None
    pressure_kpa: DraftRange | None = None
    flow_speed_cm_s: DraftRange | None = None
    flow_direction: list[FlowDirection] = Field(default_factory=list)
    gravity_g: list[float] = Field(default_factory=list)


class DraftHardware(AgentModel):
    name: str
    role: HardwareRole


class DraftMeasurement(AgentModel):
    instrument: str
    quantity: str
    source: DraftSource


class DraftFinding(AgentModel):
    statement: str
    category: FindingCategory
    source: DraftSource
    confidence: float = Field(ge=0.0, le=1.0)


class DraftPublication(AgentModel):
    doi: str | None = None
    title: str
    year: int | None = None


class ExtractorOutput(AgentModel):
    """`InvestigationCard` draft; `extract_stage` swaps each `doc_id` for the document URI."""

    platform: Platform | None = None
    gravity_level: GravityLevel | None = None
    hardware: list[DraftHardware] = Field(default_factory=list)
    objectives: list[DraftText] = Field(default_factory=list)
    approach: DraftText | None = None
    fuels: list[DraftFuel] = Field(default_factory=list)
    conditions: DraftConditions | None = None
    varied: list[str] = Field(default_factory=list)
    fixed: list[str] = Field(default_factory=list)
    measurements: list[DraftMeasurement] = Field(default_factory=list)
    findings: list[DraftFinding] = Field(default_factory=list)
    publications: list[DraftPublication] = Field(default_factory=list)
    fire_safety_tags: list[FireSafetyTag] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)


# --- scorer --------------------------------------------------------------------------------


class CriterionSpec(AgentModel):
    id: str
    label: str
    description: str = ""
    anchors: dict[int, str] = Field(default_factory=dict)


class ScorerExcerpt(AgentModel):
    chunk_id: int
    text: str


class ScorerInput(AgentModel):
    acronym: str
    lens: Lens
    criteria: list[CriterionSpec]
    card: InvestigationCard
    excerpts: list[ScorerExcerpt] = Field(default_factory=list)


class ScorerEvidence(AgentModel):
    chunk_id: int | None = None
    field_path: str | None = None
    quote: str = Field(max_length=MAX_QUOTE_CHARS)

    @model_validator(mode="after")
    def _points_somewhere(self) -> Self:
        if self.chunk_id is None and not self.field_path:
            raise ValueError("evidence needs a chunk_id or a field_path")
        return self


class ScorerCriterionScore(AgentModel):
    criterion: str
    value: int | None = Field(default=None, ge=SCORE_MIN, le=SCORE_MAX)
    rationale: str = ""
    evidence: list[ScorerEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _value_needs_evidence(self) -> Self:
        if self.value is not None and not self.evidence:
            raise ValueError("a non-null value requires at least one evidence item")
        return self


class ScorerOutput(AgentModel):
    lens: Lens
    scores: list[ScorerCriterionScore]


# --- comparator ----------------------------------------------------------------------------


class ComparatorInput(AgentModel):
    investigations: list[dict[str, JsonValue]]
    matrix: list[MatrixRow]
    shared: SharedFacts
    facts: list[Fact]


class ComparatorOutput(AgentModel):
    sentences: list[SentenceWithFacts] = Field(
        min_length=MIN_COMPARATOR_SENTENCES, max_length=MAX_COMPARATOR_SENTENCES
    )


# --- scenario interpreter ------------------------------------------------------------------


class ScenarioInterpreterInput(AgentModel):
    scenario: ResolvedScenario
    coverage: dict[str, CoverageEntry]
    matches: list[ScenarioMatch] = Field(max_length=TOP_MATCHES_FOR_INTERPRETATION)
    gravity_bounding: GravityBounding
    facts: list[Fact]


class ScenarioInterpreterOutput(AgentModel):
    sentences: list[SentenceWithFacts] = Field(min_length=1)
    caveats: list[str] = Field(default_factory=list)


# --- insight QA ----------------------------------------------------------------------------


class QAChunk(AgentModel):
    chunk_id: int
    acronym: str
    doc_title: str
    text: str


class QACardFact(AgentModel):
    id: int
    acronym: str
    text: str


class InsightQAInput(AgentModel):
    """The streamed answer is plain text with `[c:ID]` / `[f:ID]` markers, so no output model."""

    question: str
    chunks: list[QAChunk] = Field(default_factory=list)
    card_facts: list[QACardFact] = Field(default_factory=list)


# --- Earth applications --------------------------------------------------------------------


class EarthFinding(AgentModel):
    id: int
    acronym: str
    statement: str
    category: FindingCategory


class KnownApplication(AgentModel):
    title: str
    sector: EarthSector


class EarthAppsInput(AgentModel):
    findings: list[EarthFinding]
    known_applications: list[KnownApplication] = Field(default_factory=list)


class EarthAppCandidate(AgentModel):
    title: str
    sector: EarthSector
    description: str
    finding_ids: list[int] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class EarthAppsOutput(AgentModel):
    applications: list[EarthAppCandidate] = Field(default_factory=list)
