"""Request and response models of the REST and SSE API (document 05)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from flamescope_common.rubric import Lens, Presets, Rubric
from flamescope_common.schemas.card import (
    CardData,
    CoverageState,
    FindingCategory,
    FireSafetyTag,
    FuelGeometry,
    FuelPhase,
    GravityLevel,
    InvestigationCard,
    RunCondition,
    RunOutcome,
)
from flamescope_common.sources import SourceRef

SCORE_DISCLAIMER = "Scores are relative decision aids, not safety certifications."
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100
DEFAULT_ASK_TOP_K = 8
MAX_ASK_TOP_K = 20
DEFAULT_SCENARIO_LIMIT = 10
DEFAULT_EXTRACT_LIMIT = 50
MAX_EXTRACT_LIMIT = 1000

RankLens = Literal["habitat", "modeling", "controls", "overall"]
SortKey = Literal["acronym", "overall", "habitat", "modeling", "controls"]
NarrativeStatus = Literal["ok", "unavailable", "skipped"]
EarthSector = Literal[
    "firefighting", "detection", "building_safety", "industrial", "wildfire", "transport"
]
ExportFormat = Literal["csv", "json"]
RangePair = tuple[float, float]
# A null end is open on that side (doc 04 s2; doc 08 s4.2), never a guessed bound.
OpenRangePair = tuple[float | None, float | None]


class ApiModel(BaseModel):
    """Base for API models; responses ignore nothing and requests reject unknown keys."""

    model_config = ConfigDict(extra="forbid")


class Page[ItemT](ApiModel):
    """Paginated list envelope (document 05 section 1)."""

    items: list[ItemT]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=MAX_PAGE_SIZE)
    total: int = Field(ge=0)


class PageRequest(ApiModel):
    """Pagination and sort of list endpoints (document 05 section 1); also a query model."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    sort: SortKey = "acronym"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


# --- errors, health and meta (sections 2 and 3) --------------------------------------------


class ErrorBody(ApiModel):
    code: str
    message: str
    details: JsonValue = None
    request_id: str | None = None


class ErrorEnvelope(ApiModel):
    error: ErrorBody


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(ApiModel):
    status: Literal["ready"] = "ready"
    db: bool
    migrations: str | None
    investigations: int


class StatsResponse(ApiModel):
    investigations: int
    test_runs: int
    publications: int
    findings: int
    chunks: int
    hardware: int
    fuel_phase_counts: dict[str, int]
    o2_range: OpenRangePair
    pressure_range_kpa: OpenRangePair
    rubric_version: str
    last_ingest: datetime | None = None
    ingest_mode: Literal["seed", "harvest"] | None = None


class ComponentStatus(ApiModel):
    id: str
    status: str
    detail: str | None = None
    provider: str | None = None
    model: str | None = None
    last_run: dict[str, JsonValue] | None = None


class StatusResponse(ApiModel):
    components: list[ComponentStatus]


RubricResponse = Rubric
PresetsResponse = Presets


# --- catalog (section 4) -------------------------------------------------------------------


class InvestigationFilters(ApiModel):
    """Filters of `GET /investigations`; also used by `POST /rank`."""

    q: str | None = None
    fuel_phase: list[FuelPhase] = Field(default_factory=list)
    material: str | None = None
    hardware: list[str] = Field(default_factory=list)
    project: str | None = None
    tag: list[FireSafetyTag] = Field(default_factory=list)
    o2_min: float | None = Field(default=None, ge=0.0, le=1.0)
    o2_max: float | None = Field(default=None, ge=0.0, le=1.0)
    pressure_min_kpa: float | None = Field(default=None, ge=0.0)
    pressure_max_kpa: float | None = Field(default=None, ge=0.0)
    gravity_level: GravityLevel | None = None


class ScoreSet(ApiModel):
    habitat: float | None = None
    modeling: float | None = None
    controls: float | None = None
    overall: float | None = None


class InvestigationSummary(ApiModel):
    id: int
    acronym: str
    title: str
    project: str | None = None
    platform: str | None = None
    gravity_level: str | None = None
    fuel_phases: list[str] = Field(default_factory=list)
    hardware: list[str] = Field(default_factory=list)
    summary: str | None = None
    fire_safety_tags: list[str] = Field(default_factory=list)
    o2_range: OpenRangePair | None = None
    pressure_range_kpa: OpenRangePair | None = None
    flow_range_cm_s: OpenRangePair | None = None
    scores: ScoreSet = Field(default_factory=ScoreSet)
    reviewed: bool = False
    psi_url: str | None = None


class BreakdownItem(ApiModel):
    criterion: str
    label: str
    value: float | None
    weight: float
    contribution: float
    rationale: str = ""
    evidence: list[SourceRef] = Field(default_factory=list)
    origin: Literal["llm", "seed", "override"]


class LensScore(ApiModel):
    """Result of `ranking.aggregate`: lens score 0-100 (null without evidence) and confidence."""

    score: float | None
    confidence: float
    breakdown: list[BreakdownItem] = Field(default_factory=list)


class PublicationOut(ApiModel):
    doi: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    key_findings: JsonValue = None


class MeasurementOut(ApiModel):
    instrument: str
    quantity: str
    units: str | None = None
    file_pattern: str | None = None
    notes: str = ""
    source: SourceRef | None = None


class FindingOut(ApiModel):
    id: int
    statement: str
    category: FindingCategory
    source: SourceRef
    confidence: float


class InvestigationDetail(InvestigationSummary):
    card: InvestigationCard
    publications: list[PublicationOut] = Field(default_factory=list)
    measurements: list[MeasurementOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)
    score_breakdown: dict[Lens, LensScore] = Field(default_factory=dict)
    run_count: int = 0
    data: CardData = Field(default_factory=CardData)


class FuelRef(ApiModel):
    name: str
    phase: FuelPhase


class RunItem(ApiModel):
    id: int
    label: str
    fuel: FuelRef | None = None
    geometry: FuelGeometry | dict[str, JsonValue] = Field(default_factory=dict)
    condition: RunCondition = Field(default_factory=RunCondition)
    outcome: RunOutcome = Field(default_factory=RunOutcome)
    is_aggregate: bool = False
    source: SourceRef | None = None
    confidence: float = 0.0


class VariedParameter(ApiModel):
    name: str
    values: list[JsonValue] = Field(default_factory=list)
    unit: str | None = None


class FixedParameter(ApiModel):
    name: str
    value: JsonValue = None
    unit: str | None = None


class VariablesResponse(ApiModel):
    varied: list[VariedParameter] = Field(default_factory=list)
    fixed: list[FixedParameter] = Field(default_factory=list)
    run_count: int = 0


class FacetValue(ApiModel):
    value: str
    count: int


class FacetsResponse(ApiModel):
    fuel_phase: list[FacetValue] = Field(default_factory=list)
    hardware: list[FacetValue] = Field(default_factory=list)
    project: list[FacetValue] = Field(default_factory=list)
    tag: list[FacetValue] = Field(default_factory=list)
    platform: list[FacetValue] = Field(default_factory=list)
    gravity_level: list[FacetValue] = Field(default_factory=list)


class LineageNode(ApiModel):
    id: str
    type: Literal["hardware", "investigation", "project"]
    label: str
    kind: str | None = None


class LineageEdge(ApiModel):
    source: str
    target: str
    role: str


class LineageGraph(ApiModel):
    nodes: list[LineageNode] = Field(default_factory=list)
    edges: list[LineageEdge] = Field(default_factory=list)


class ProjectOut(ApiModel):
    name: str
    description: str | None = None
    investigations: list[str] = Field(default_factory=list)


# --- ranking (section 5) -------------------------------------------------------------------


class RankRequest(ApiModel):
    lens: RankLens
    preset: str | None = None
    criterion_weights: dict[Lens, dict[str, float]] | None = None
    lens_weights: dict[Lens, float] | None = None
    filters: InvestigationFilters | None = None
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class WeightsUsed(ApiModel):
    lens_weights: dict[Lens, float]
    criterion_weights: dict[Lens, dict[str, float]]


class RankItem(ApiModel):
    rank: int
    acronym: str
    title: str
    score: float | None
    confidence: float | None
    lens_scores: dict[Lens, float | None]
    breakdown: list[BreakdownItem] = Field(default_factory=list)


class RankResponse(ApiModel):
    lens: RankLens
    rubric_version: str
    weights_used: WeightsUsed
    items: list[RankItem]
    disclaimer: str = SCORE_DISCLAIMER


# --- compare (section 6) -------------------------------------------------------------------


class CompareRequest(ApiModel):
    """The 2 to 4 ID bound is enforced by the service (HTTP 400), not the schema."""

    investigations: list[str]
    narrative: bool = True


class MatrixRow(ApiModel):
    attribute: str
    label: str
    group: str
    values: dict[str, JsonValue]
    same: bool


DiffMatrix = list[MatrixRow]


class SharedFacts(ApiModel):
    hardware: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)


class NarrativeSentence(ApiModel):
    text: str
    citations: list[SourceRef] = Field(default_factory=list)


class Narrative(ApiModel):
    """Compare narrative and scenario explanation share this shape."""

    text: str = ""
    sentences: list[NarrativeSentence] = Field(default_factory=list)
    status: NarrativeStatus


class CompareResponse(ApiModel):
    investigations: list[InvestigationSummary]
    matrix: DiffMatrix
    shared: SharedFacts
    narrative: Narrative


# --- scenario (section 7) ------------------------------------------------------------------


class ScenarioWeights(ApiModel):
    """Distance weights; defaults from document 08 section 4.2."""

    o2: float = Field(default=0.35, ge=0.0)
    pressure: float = Field(default=0.25, ge=0.0)
    flow: float = Field(default=0.15, ge=0.0)
    fuel: float = Field(default=0.25, ge=0.0)


class ScenarioRequest(ApiModel):
    preset: str | None = None
    o2_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    pressure_kpa: float | None = Field(default=None, ge=0.0)
    gravity_g: float | None = Field(default=None, ge=0.0)
    flow_speed_cm_s: float | None = Field(default=None, ge=0.0)
    fuel_phase: FuelPhase | None = None
    material: str | None = None
    weights: ScenarioWeights | None = None
    explain: bool = True
    limit: int = Field(default=DEFAULT_SCENARIO_LIMIT, ge=1, le=MAX_PAGE_SIZE)


class ResolvedScenario(ApiModel):
    """The scenario after preset and explicit values are merged."""

    preset: str | None = None
    o2_fraction: float | None = None
    pressure_kpa: float | None = None
    gravity_g: float | None = None
    flow_speed_cm_s: float | None = None
    fuel_phase: FuelPhase | None = None
    material: str | None = None
    weights: ScenarioWeights = Field(default_factory=ScenarioWeights)
    assumed_default: bool = False


class CoverageEntry(ApiModel):
    state: CoverageState
    catalog_range: RangePair | None = None
    catalog_values: list[float] | None = None


class ScenarioMatch(ApiModel):
    acronym: str
    similarity: float
    best_run: RunItem | None = None
    median_similarity: float
    per_dimension: dict[str, float] = Field(default_factory=dict)
    matching_runs: int = 0


class GravityBound(ApiModel):
    gravity_g: float
    investigations: list[str] = Field(default_factory=list)


class GravityAnalogue(ApiModel):
    acronym: str
    note: str


class GravityBounding(ApiModel):
    partial_gravity_data: bool
    lower_bound: GravityBound | None = None
    upper_bound: GravityBound | None = None
    analogue: GravityAnalogue | None = None
    statement: str | None = None


class ScenarioResponse(ApiModel):
    scenario: ResolvedScenario
    coverage: dict[str, CoverageEntry]
    matches: list[ScenarioMatch]
    gravity_bounding: GravityBounding
    explanation: Narrative
    scenario_id: str


# --- extract (section 8) -------------------------------------------------------------------


class ExtractFilters(ApiModel):
    investigations: list[str] = Field(default_factory=list)
    fuel_phase: list[FuelPhase] = Field(default_factory=list)
    o2_min: float | None = None
    o2_max: float | None = None
    pressure_min_kpa: float | None = None
    pressure_max_kpa: float | None = None
    has_outcome: list[str] = Field(default_factory=list)
    scenario_id: str | None = None


class ExtractRequest(ApiModel):
    filters: ExtractFilters = Field(default_factory=ExtractFilters)
    columns: list[str] | None = None
    limit: int = Field(default=DEFAULT_EXTRACT_LIMIT, ge=1, le=MAX_EXTRACT_LIMIT)


class ExportRequest(ExtractRequest):
    format: ExportFormat = "csv"


class ColumnInfo(ApiModel):
    name: str
    label: str
    unit: str | None = None
    description: str = ""


class Table(ApiModel):
    """Columns, rows and total of an extract preview."""

    columns: list[ColumnInfo]
    rows: list[list[JsonValue]]
    total: int


class DictionaryResponse(ApiModel):
    columns: list[ColumnInfo]


# --- insights and Earth applications (section 9) -------------------------------------------


class SafetyFinding(ApiModel):
    id: int
    statement: str
    investigation: str
    source: SourceRef
    confidence: float


class SafetyGroup(ApiModel):
    category: FindingCategory
    label: str
    findings: list[SafetyFinding] = Field(default_factory=list)
    investigations: list[str] = Field(default_factory=list)


class SafetyTechResponse(ApiModel):
    groups: list[SafetyGroup]


class GapItem(ApiModel):
    id: str
    title: str
    detail: str
    related: list[str] = Field(default_factory=list)
    future: list[str] = Field(default_factory=list)


class GapsResponse(ApiModel):
    gaps: list[GapItem]


class EarthApplicationOut(ApiModel):
    id: int
    title: str
    sector: EarthSector
    description: str
    maturity: str | None = None
    investigations: list[str] = Field(default_factory=list)
    findings: list[int] = Field(default_factory=list)
    references: list[SourceRef] = Field(default_factory=list)


class EarthApplicationsResponse(ApiModel):
    items: list[EarthApplicationOut]


# --- ask (section 10) ----------------------------------------------------------------------


class AskFilters(ApiModel):
    investigations: list[str] = Field(default_factory=list)


class AskRequest(ApiModel):
    question: str = Field(min_length=1)
    filters: AskFilters = Field(default_factory=AskFilters)
    top_k: int = Field(default=DEFAULT_ASK_TOP_K, ge=1, le=MAX_ASK_TOP_K)


class ChunkHit(ApiModel):
    """A retrieved chunk with its retrieval or fused score."""

    chunk_id: int
    acronym: str
    doc_title: str
    text: str
    score: float
    source: SourceRef | None = None


class RetrievedChunk(ApiModel):
    chunk_id: int
    acronym: str
    doc_title: str
    score: float


class AskMeta(ApiModel):
    request_id: str | None = None
    retrieved: list[RetrievedChunk] = Field(default_factory=list)


class AskToken(ApiModel):
    text: str


class VerifiedSentence(ApiModel):
    """A sentence after citation verification (document 07 section 4)."""

    text: str
    citations: list[SourceRef] = Field(default_factory=list)
    supported: bool


class AskCitations(ApiModel):
    sentences: list[VerifiedSentence]
    dropped: int = 0


class AskRelated(ApiModel):
    investigations: list[str] = Field(default_factory=list)


class AskDone(ApiModel):
    status: Literal["ok"] = "ok"


class AskError(ApiModel):
    code: str
    message: str
