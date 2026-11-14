"""Seed files under `src/data/seed/**` (document 06 section 5): loading and export."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from flamescope_common.errors import NotFoundError, ValidationError
from flamescope_common.models import (
    Condition,
    Fuel,
    Investigation,
    RelevanceScore,
    TestRun,
)
from flamescope_common.schemas.card import (
    FuelPhase,
    HardwareKind,
    SeedInvestigation,
    SeedRun,
    SeedScore,
)
from flamescope_common.sources import SourceRef

SEED_DIR = "seed"
INVESTIGATIONS_DIR = "investigations"
HARDWARE_FILE = "hardware.yaml"
FUEL_TAXONOMY_FILE = "fuel_taxonomy.yaml"
EARTH_APPLICATIONS_FILE = "earth_applications.yaml"
S3_MAP_FILE = "s3_map.yaml"
YAML_LINE_WIDTH = 100
CONDITION_COLUMNS = (
    "o2_fraction",
    "diluent",
    "pressure_kpa",
    "flow_speed_cm_s",
    "flow_direction",
    "gravity_g",
    "e_field_kv",
    "temperature_k",
)


class SeedModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ProjectSeed(SeedModel):
    name: str
    description: str | None = None


class HardwareSeed(SeedModel):
    name: str
    kind: HardwareKind
    description: str | None = None
    parent: str | None = None


class HardwareCatalog(SeedModel):
    """`hardware.yaml`: projects and hardware, with parent links by name."""

    projects: list[ProjectSeed] = Field(default_factory=list)
    hardware: list[HardwareSeed] = Field(default_factory=list)

    def hardware_names(self) -> set[str]:
        return {item.name for item in self.hardware}


class FuelEntry(SeedModel):
    name: str
    phase: FuelPhase
    material_class: str | None = None
    aliases: list[str] = Field(default_factory=list)


class FuelTaxonomy(SeedModel):
    """`fuel_taxonomy.yaml`: canonical fuel names with aliases."""

    fuels: list[FuelEntry] = Field(default_factory=list)

    def resolve(self, name: str) -> FuelEntry | None:
        wanted = name.strip().casefold()
        for entry in self.fuels:
            if wanted in {candidate.casefold() for candidate in (entry.name, *entry.aliases)}:
                return entry
        return None


class EarthApplicationSeed(SeedModel):
    title: str
    sector: str
    description: str = ""
    maturity: str | None = None
    investigations: list[str] = Field(default_factory=list)
    references: list[SourceRef] = Field(default_factory=list)


class EarthApplicationCatalog(SeedModel):
    applications: list[EarthApplicationSeed] = Field(default_factory=list)


class S3Mapping(SeedModel):
    prefix: str
    acronym: str


class S3Map(SeedModel):
    """`s3_map.yaml`: pinned folder-to-acronym mappings for the discover stage."""

    mappings: list[S3Mapping] = Field(default_factory=list)


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise NotFoundError(f"Seed file not found: {path}", {"path": str(path)})
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValidationError(f"Seed file must hold a mapping: {path}", {"path": str(path)})
    return loaded


def _seed_path(data_dir: Path, file_name: str) -> Path:
    return data_dir / SEED_DIR / file_name


def investigations_dir(data_dir: Path) -> Path:
    return data_dir / SEED_DIR / INVESTIGATIONS_DIR


def list_seed_acronyms(data_dir: Path) -> list[str]:
    """Acronyms of every seed investigation file, sorted."""
    return sorted(path.stem for path in investigations_dir(data_dir).glob("*.yaml"))


def has_seed(data_dir: Path, acronym: str) -> bool:
    return (investigations_dir(data_dir) / f"{acronym}.yaml").is_file()


def select_acronyms(available: Iterable[str], only: Iterable[str] | None) -> list[str]:
    """`--only` filter; an unknown acronym is an error rather than a silent skip."""
    known = list(available)
    if not only:
        return known
    by_folded = {acronym.casefold(): acronym for acronym in known}
    missing = [name for name in only if name.casefold() not in by_folded]
    if missing:
        raise NotFoundError(f"Unknown investigation(s): {', '.join(missing)}", {"known": known})
    return [by_folded[name.casefold()] for name in only]


def load_seed_mapping(data_dir: Path, acronym: str) -> dict[str, Any]:
    """The raw YAML mapping of one seed investigation."""
    return _read_mapping(investigations_dir(data_dir) / f"{acronym}.yaml")


def load_hardware_catalog(data_dir: Path) -> HardwareCatalog:
    return HardwareCatalog.model_validate(_read_mapping(_seed_path(data_dir, HARDWARE_FILE)))


def load_fuel_taxonomy(data_dir: Path) -> FuelTaxonomy:
    return FuelTaxonomy.model_validate(_read_mapping(_seed_path(data_dir, FUEL_TAXONOMY_FILE)))


def load_earth_applications(data_dir: Path) -> EarthApplicationCatalog:
    path = _seed_path(data_dir, EARTH_APPLICATIONS_FILE)
    return EarthApplicationCatalog.model_validate(_read_mapping(path))


def load_s3_map(data_dir: Path) -> S3Map:
    return S3Map.model_validate(_read_mapping(_seed_path(data_dir, S3_MAP_FILE)))


def _plain_number(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


def _seed_run(run: TestRun, condition: Condition | None, fuel_name: str | None) -> SeedRun:
    condition_values = {}
    if condition is not None:
        condition_values = {
            column: _plain_number(getattr(condition, column)) for column in CONDITION_COLUMNS
        }
    return SeedRun.model_validate(
        {
            "label": run.label,
            "fuel": fuel_name,
            "geometry": run.geometry or None,
            "condition": condition_values,
            "outcome": run.outcome,
            "varied_parameters": run.varied_parameters,
            "fixed_parameters": run.fixed_parameters,
            "is_aggregate": run.is_aggregate,
            "confidence": float(run.confidence),
            "source": run.source,
        }
    )


class SeedExporter:
    """Writes stored cards back to `seed/investigations/<acronym>.yaml` (`export-seed`)."""

    def __init__(self, session: Session, data_dir: Path) -> None:
        self._session = session
        self._data_dir = data_dir

    def export(self, only: Iterable[str] | None = None) -> list[Path]:
        """Export the named investigations, or every reviewed one when none are named."""
        named = list(only or [])
        rows = self._session.scalars(select(Investigation).order_by(Investigation.acronym)).all()
        chosen = set(select_acronyms([row.acronym for row in rows], named))
        return [
            self._write(row) for row in rows if row.acronym in chosen and (named or row.reviewed)
        ]

    def _write(self, row: Investigation) -> Path:
        target = investigations_dir(self._data_dir) / f"{row.acronym}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(
            self._seed_for(row).model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
            width=YAML_LINE_WIDTH,
        )
        target.write_text(text, encoding="utf-8")
        return target

    def _seed_for(self, row: Investigation) -> SeedInvestigation:
        return SeedInvestigation.model_validate(
            {
                **row.card,
                "psi_url": row.psi_url,
                "summary": row.summary,
                "status": row.status,
                "reviewed": row.reviewed,
                "runs": self._runs(row.id),
                "scores": self._scores(row.id),
            }
        )

    def _runs(self, investigation_id: int) -> list[dict[str, Any]]:
        statement = (
            select(TestRun, Condition, Fuel.name)
            .join(Condition, Condition.test_run_id == TestRun.id, isouter=True)
            .join(Fuel, Fuel.id == TestRun.fuel_id, isouter=True)
            .where(TestRun.investigation_id == investigation_id)
            .order_by(TestRun.id)
        )
        return [
            _seed_run(run, condition, fuel_name).model_dump(mode="json")
            for run, condition, fuel_name in self._session.execute(statement)
        ]

    def _scores(self, investigation_id: int) -> dict[str, dict[str, Any]]:
        rows = self._session.scalars(
            select(RelevanceScore)
            .where(RelevanceScore.investigation_id == investigation_id)
            .order_by(RelevanceScore.lens, RelevanceScore.criterion)
        )
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            score = SeedScore(
                value=None if row.value is None else float(row.value),
                rationale=row.rationale,
                evidence=[SourceRef.model_validate(item) for item in row.evidence],
            )
            grouped.setdefault(row.lens, {})[row.criterion] = score.model_dump(mode="json")
        return grouped
