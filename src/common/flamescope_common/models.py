"""SQLAlchemy 2.x ORM models for every table of document 04."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, get_args

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INT4RANGE, JSONB, TSVECTOR, Range
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from flamescope_common.config import get_settings
from flamescope_common.rubric import LENSES
from flamescope_common.schemas.api import EarthSector
from flamescope_common.schemas.card import (
    FindingCategory,
    FlowDirection,
    FuelPhase,
    GravityLevel,
    HardwareKind,
    HardwareRole,
    InvestigationStatus,
    Platform,
)

EMBED_DIM = get_settings().embed_dim
SCORE_ORIGINS = ("llm", "seed", "override")
INGEST_MODES = ("seed", "harvest")
INGEST_STATUSES = ("ok", "failed", "partial")
SCORE_MIN = 0
SCORE_MAX = 5
CONFIDENCE_CHECK = "confidence >= 0 and confidence <= 1"


def _in_values(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} in ({quoted})"


def _vocabulary(literal: Any) -> tuple[str, ...]:
    return tuple(get_args(literal))


def _investigation_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("investigation.id", ondelete="CASCADE"))


def _bigint_pk() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(), primary_key=True)


class Base(DeclarativeBase):
    """Declarative base; every table carries `created_at` and `updated_at`."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = _bigint_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class Hardware(Base):
    __tablename__ = "hardware"
    __table_args__ = (CheckConstraint(_in_values("kind", _vocabulary(HardwareKind))),)

    id: Mapped[int] = _bigint_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("hardware.id", ondelete="SET NULL"))


_OBJECTIVES_TEXT = "jsonb_path_query_array(objectives, '$[*].text')::text"
_INVESTIGATION_TSV = (
    "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '') "
    f"|| ' ' || coalesce({_OBJECTIVES_TEXT}, ''))"
)


class Investigation(Base):
    __tablename__ = "investigation"
    __table_args__ = (
        CheckConstraint(_in_values("platform", _vocabulary(Platform))),
        CheckConstraint(_in_values("gravity_level", _vocabulary(GravityLevel))),
        CheckConstraint(_in_values("status", _vocabulary(InvestigationStatus))),
        Index("ix_investigation_search_tsv", "search_tsv", postgresql_using="gin"),
        Index("ix_investigation_fire_safety_tags", "fire_safety_tags", postgresql_using="gin"),
        Index("ix_investigation_fuel_phases", "fuel_phases", postgresql_using="gin"),
        Index(
            "ix_investigation_acronym_trgm",
            "acronym",
            postgresql_using="gin",
            postgresql_ops={"acronym": "gin_trgm_ops"},
        ),
        Index(
            "ix_investigation_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_investigation_project_id", "project_id"),
    )

    id: Mapped[int] = _bigint_pk()
    acronym: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    discipline: Mapped[str] = mapped_column(Text, server_default="combustion")
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id", ondelete="SET NULL"))
    psi_url: Mapped[str | None] = mapped_column(Text)
    s3_prefix: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(Text)
    gravity_level: Mapped[str | None] = mapped_column(Text)
    years: Mapped[Range[int] | None] = mapped_column(INT4RANGE)
    status: Mapped[str | None] = mapped_column(Text)
    objectives: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    approach: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    fuel_phases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    fire_safety_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    o2_min: Mapped[Decimal | None] = mapped_column(Numeric)
    o2_max: Mapped[Decimal | None] = mapped_column(Numeric)
    pressure_min_kpa: Mapped[Decimal | None] = mapped_column(Numeric)
    pressure_max_kpa: Mapped[Decimal | None] = mapped_column(Numeric)
    flow_min_cm_s: Mapped[Decimal | None] = mapped_column(Numeric)
    flow_max_cm_s: Mapped[Decimal | None] = mapped_column(Numeric)
    data_volume_bytes: Mapped[int | None] = mapped_column(BigInteger)
    file_manifest_ref: Mapped[str | None] = mapped_column(Text)
    card: Mapped[dict[str, Any]] = mapped_column(JSONB)
    card_version: Mapped[int] = mapped_column(Integer, server_default="1")
    reviewed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    search_tsv: Mapped[str] = mapped_column(TSVECTOR, Computed(_INVESTIGATION_TSV, persisted=True))


class InvestigationHardware(Base):
    __tablename__ = "investigation_hardware"
    __table_args__ = (
        PrimaryKeyConstraint("investigation_id", "hardware_id"),
        CheckConstraint(_in_values("role", _vocabulary(HardwareRole))),
        Index("ix_investigation_hardware_hardware_id", "hardware_id"),
    )

    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )
    hardware_id: Mapped[int] = mapped_column(ForeignKey("hardware.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Text)


class Fuel(Base):
    __tablename__ = "fuel"
    __table_args__ = (
        UniqueConstraint("name", "phase"),
        CheckConstraint(_in_values("phase", _vocabulary(FuelPhase))),
    )

    id: Mapped[int] = _bigint_pk()
    name: Mapped[str] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(Text)
    material_class: Mapped[str | None] = mapped_column(Text)


class TestRun(Base):
    __tablename__ = "test_run"
    __test__ = False  # not a pytest test class
    __table_args__ = (
        CheckConstraint(CONFIDENCE_CHECK),
        Index("ix_test_run_investigation_id", "investigation_id"),
        Index("ix_test_run_fuel_id", "fuel_id"),
    )

    id: Mapped[int] = _bigint_pk()
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(Text)
    fuel_id: Mapped[int | None] = mapped_column(ForeignKey("fuel.id", ondelete="SET NULL"))
    geometry: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    varied_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    fixed_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    outcome: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    data_files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    is_aggregate: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Condition(Base):
    __tablename__ = "condition"
    __table_args__ = (CheckConstraint(_in_values("flow_direction", _vocabulary(FlowDirection))),)

    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("test_run.id", ondelete="CASCADE"), primary_key=True
    )
    o2_fraction: Mapped[Decimal | None] = mapped_column(Numeric)
    diluent: Mapped[str | None] = mapped_column(Text)
    pressure_kpa: Mapped[Decimal | None] = mapped_column(Numeric)
    flow_speed_cm_s: Mapped[Decimal | None] = mapped_column(Numeric)
    flow_direction: Mapped[str | None] = mapped_column(Text)
    gravity_g: Mapped[Decimal | None] = mapped_column(Numeric)
    e_field_kv: Mapped[Decimal | None] = mapped_column(Numeric)
    temperature_k: Mapped[Decimal | None] = mapped_column(Numeric)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Measurement(Base):
    __tablename__ = "measurement"
    __table_args__ = (Index("ix_measurement_investigation_id", "investigation_id"),)

    id: Mapped[int] = _bigint_pk()
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )
    instrument: Mapped[str] = mapped_column(Text)
    hardware_id: Mapped[int | None] = mapped_column(ForeignKey("hardware.id", ondelete="SET NULL"))
    quantity: Mapped[str] = mapped_column(Text)
    units: Mapped[str | None] = mapped_column(Text)
    file_pattern: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default="")
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Publication(Base):
    __tablename__ = "publication"
    __table_args__ = (
        Index(
            "uq_publication_investigation_doi_title",
            "investigation_id",
            text("coalesce(doi, title)"),
            unique=True,
        ),
    )

    id: Mapped[int] = _bigint_pk()
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )
    doi: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    year: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    key_findings: Mapped[list[Any]] = mapped_column(JSONB, server_default="[]")


class Finding(Base):
    __tablename__ = "finding"
    __table_args__ = (
        CheckConstraint(_in_values("category", _vocabulary(FindingCategory))),
        CheckConstraint(CONFIDENCE_CHECK),
        Index("ix_finding_investigation_id", "investigation_id"),
    )

    id: Mapped[int] = _bigint_pk()
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )
    statement: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence: Mapped[Decimal] = mapped_column(Numeric)


class EarthApplication(Base):
    __tablename__ = "earth_application"
    __table_args__ = (CheckConstraint(_in_values("sector", _vocabulary(EarthSector))),)

    id: Mapped[int] = _bigint_pk()
    title: Mapped[str] = mapped_column(Text)
    sector: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    maturity: Mapped[str | None] = mapped_column(Text)
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")


class FindingEarthApplication(Base):
    __tablename__ = "finding_earth_application"
    __table_args__ = (PrimaryKeyConstraint("finding_id", "earth_application_id"),)

    finding_id: Mapped[int] = mapped_column(ForeignKey("finding.id", ondelete="CASCADE"))
    earth_application_id: Mapped[int] = mapped_column(
        ForeignKey("earth_application.id", ondelete="CASCADE")
    )


class EarthApplicationInvestigation(Base):
    __tablename__ = "earth_application_investigation"
    __table_args__ = (PrimaryKeyConstraint("earth_application_id", "investigation_id"),)

    earth_application_id: Mapped[int] = mapped_column(
        ForeignKey("earth_application.id", ondelete="CASCADE")
    )
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )


class RelevanceScore(Base):
    __tablename__ = "relevance_score"
    __table_args__ = (
        UniqueConstraint("investigation_id", "lens", "criterion", "rubric_version"),
        CheckConstraint(_in_values("lens", LENSES)),
        CheckConstraint(_in_values("origin", SCORE_ORIGINS)),
        CheckConstraint(f"value is null or (value >= {SCORE_MIN} and value <= {SCORE_MAX})"),
    )

    id: Mapped[int] = _bigint_pk()
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )
    lens: Mapped[str] = mapped_column(Text)
    criterion: Mapped[str] = mapped_column(Text)
    value: Mapped[Decimal | None] = mapped_column(Numeric)
    rationale: Mapped[str] = mapped_column(Text, server_default="")
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    rubric_version: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)


_CHUNK_TSV = "to_tsvector('english', coalesce(doc_title, '') || ' ' || text)"


class Chunk(Base):
    __tablename__ = "chunk"
    __table_args__ = (
        Index("ix_chunk_investigation_id", "investigation_id"),
        Index("ix_chunk_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = _bigint_pk()
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE")
    )
    doc_ref: Mapped[str] = mapped_column(Text)
    doc_title: Mapped[str] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(doc_title, '') || ' ' || text)", persisted=True),
    )
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)


class IngestRun(Base):
    __tablename__ = "ingest_run"
    __table_args__ = (
        CheckConstraint(_in_values("mode", INGEST_MODES)),
        CheckConstraint(_in_values("status", INGEST_STATUSES)),
    )

    id: Mapped[int] = _bigint_pk()
    investigation_id: Mapped[int | None] = mapped_column(
        ForeignKey("investigation.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(Text)
    stages: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    status: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class LlmCacheEntry(Base):
    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
