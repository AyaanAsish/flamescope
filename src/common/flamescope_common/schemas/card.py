"""`InvestigationCard`, its nested models and the seed file schema (documents 04 and 06)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from flamescope_common.rubric import Lens
from flamescope_common.sources import SourceRef

Platform = Literal["ISS", "drop_tower", "parabolic", "sounding_rocket", "suborbital", "ground"]
GravityLevel = Literal["microgravity", "normal", "partial", "mixed"]
InvestigationStatus = Literal["completed", "ongoing", "planned"]
FuelPhase = Literal["gas", "liquid", "solid"]
HardwareKind = Literal["facility", "apparatus", "insert", "instrument"]
HardwareRole = Literal["host", "apparatus", "instrument"]
FlowDirection = Literal["opposed", "concurrent", "quiescent", "coflow"]
FindingCategory = Literal[
    "detection",
    "suppression",
    "material_screening",
    "post_fire",
    "atmosphere_design",
    "fundamental",
]
FireSafetyTag = Literal[
    "ignition",
    "flame_spread",
    "flammability_limit",
    "extinction",
    "suppression",
    "smoke_detection",
    "aerosol",
    "soot",
    "cool_flame",
    "droplet",
    "solid_fuel",
    "gaseous_fuel",
    "liquid_fuel",
    "high_oxygen",
    "low_pressure",
    "flow_effects",
    "electric_field",
    "partial_gravity_analogue",
    "material_screening",
    "post_fire",
]
CoverageState = Literal["covered", "extrapolated", "no_data"]
CARD_SCHEMA_VERSION = 1


def acronym_sort_key(acronym: str) -> tuple[str, str]:
    """The acronym order of document 05 section 4: case-insensitive, exact acronym breaks ties.

    Comparison is by code point on both parts, so the order never depends on a locale; SQL
    queries use `ORDER BY lower(acronym) COLLATE "C", acronym COLLATE "C"`.
    """
    return (acronym.lower(), acronym)


class CardModel(BaseModel):
    """Base for card parts: unknown keys are ignored so LLM drafts and seeds stay tolerant."""

    model_config = ConfigDict(extra="ignore")


class ValueRange(CardModel):
    """A stated numeric range; a range with a bound must carry its source."""

    min: float | None = None
    max: float | None = None
    source: SourceRef | None = None

    @model_validator(mode="after")
    def _bounded_range_has_source(self) -> Self:
        if (self.min is not None or self.max is not None) and self.source is None:
            raise ValueError("a numeric range must carry a source")
        return self


class HardwareRef(CardModel):
    name: str
    role: HardwareRole


class Objective(CardModel):
    text: str
    source: SourceRef


class Approach(CardModel):
    text: str
    source: SourceRef


class FuelGeometry(CardModel):
    shape: str | None = None
    dimensions_mm: dict[str, float | None] = Field(default_factory=dict)


class CardFuel(CardModel):
    name: str
    phase: FuelPhase
    material_class: str | None = None
    geometry: FuelGeometry | None = None
    source: SourceRef


class CardConditions(CardModel):
    o2_fraction: ValueRange | None = None
    pressure_kpa: ValueRange | None = None
    flow_speed_cm_s: ValueRange | None = None
    flow_direction: list[FlowDirection] = Field(default_factory=list)
    gravity_g: list[float] = Field(default_factory=list)


class CardVariables(CardModel):
    varied: list[str] = Field(default_factory=list)
    fixed: list[str] = Field(default_factory=list)


class CardMeasurement(CardModel):
    instrument: str
    quantity: str
    source: SourceRef


class CardFinding(CardModel):
    statement: str
    category: FindingCategory
    source: SourceRef
    confidence: float = Field(ge=0.0, le=1.0)


class CardPublication(CardModel):
    """Publication metadata; authors, venue, url and key findings feed document 05 section 4."""

    doi: str | None = None
    title: str
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    url: str | None = None
    key_findings: list[str] = Field(default_factory=list)


class CardData(CardModel):
    s3_prefix: str | None = None
    volume_bytes: int | None = None
    file_types: list[str] = Field(default_factory=list)


class InvestigationCard(CardModel):
    """The curated investigation record stored in `investigation.card` (document 04 section 4)."""

    schema_version: int = CARD_SCHEMA_VERSION
    acronym: str
    title: str
    project: str | None = None
    platform: Platform | None = None
    gravity_level: GravityLevel | None = None
    hardware: list[HardwareRef] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    approach: Approach | None = None
    fuels: list[CardFuel] = Field(default_factory=list)
    conditions: CardConditions | None = None
    variables: CardVariables = Field(default_factory=CardVariables)
    measurements: list[CardMeasurement] = Field(default_factory=list)
    findings: list[CardFinding] = Field(default_factory=list)
    publications: list[CardPublication] = Field(default_factory=list)
    fire_safety_tags: list[FireSafetyTag] = Field(default_factory=list)
    data: CardData = Field(default_factory=CardData)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)


class RunCondition(CardModel):
    """Canonical-unit condition of one seed run (document 04 table `condition`)."""

    o2_fraction: float | None = None
    diluent: str | None = None
    pressure_kpa: float | None = None
    flow_speed_cm_s: float | None = None
    flow_direction: FlowDirection | None = None
    gravity_g: float | None = None
    e_field_kv: float | None = None
    temperature_k: float | None = None


class RunOutcome(CardModel):
    """Outcome keys of document 04 table `test_run`; any key may be null."""

    ignited: bool | None = None
    flame_spread_rate_mm_s: float | None = None
    burn_rate: float | None = None
    extinction: bool | None = None
    smoke_point: float | None = None
    cool_flame: bool | None = None
    notes: str | None = None


class SeedRun(CardModel):
    """An explicit run in a seed file (document 06 section 5)."""

    label: str
    fuel: str | None = None
    geometry: FuelGeometry | None = None
    condition: RunCondition = Field(default_factory=RunCondition)
    outcome: RunOutcome = Field(default_factory=RunOutcome)
    varied_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    fixed_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    is_aggregate: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    source: SourceRef


class SeedScore(CardModel):
    """A seed-provided criterion rating; `value` null means no evidence."""

    value: float | None = Field(default=None, ge=0.0, le=5.0)
    rationale: str = ""
    evidence: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rated_value_needs_evidence(self) -> Self:
        if self.value is not None and not self.evidence:
            raise ValueError("a non-null score requires at least one evidence source")
        return self


class SeedDocument(CardModel):
    """Text for the RAG index."""

    title: str
    uri: str
    text: str
    section: str | None = None


class SeedInvestigation(InvestigationCard):
    """A seed file: the card plus the table-level fields of document 06 section 5."""

    psi_url: str
    summary: str | None = None
    status: InvestigationStatus | None = None
    runs: list[SeedRun] = Field(default_factory=list)
    scores: dict[Lens, dict[str, SeedScore]] = Field(default_factory=dict)
    documents: list[SeedDocument] = Field(default_factory=list)
    reviewed: bool = False
