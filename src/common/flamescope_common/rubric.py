"""Loaders and validators for `src/data/rubric.yaml` and `presets.yaml` (document 08)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flamescope_common.config import get_settings
from flamescope_common.errors import ValidationError

Lens = Literal["habitat", "modeling", "controls"]
LENSES: tuple[Lens, ...] = ("habitat", "modeling", "controls")
WEIGHT_SUM_TOLERANCE = 1e-6
RUBRIC_FILE = "rubric.yaml"
PRESETS_FILE = "presets.yaml"


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValidationError(f"Configuration file not found: {path}", {"path": str(path)})
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValidationError(f"Expected a mapping at the top of {path}", {"path": str(path)})
    return loaded


def _require_weights_sum_to_one(weights: Iterable[float], label: str) -> None:
    total = sum(weights)
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"{label} weights must sum to 1, got {total}")


class Criterion(BaseModel):
    """One rubric criterion rated 0 to 5 (document 08 section 1)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    weight: float = Field(ge=0.0, le=1.0)
    description: str = ""
    anchors: dict[int, str] = Field(default_factory=dict)


class LensDefinition(BaseModel):
    """A lens: a label and its weighted criteria."""

    model_config = ConfigDict(extra="forbid")

    label: str
    description: str = ""
    criteria: list[Criterion] = Field(min_length=1)

    @model_validator(mode="after")
    def _criteria_are_unique_and_normalized(self) -> Self:
        ids = [criterion.id for criterion in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate criterion ids in lens {self.label!r}")
        _require_weights_sum_to_one((c.weight for c in self.criteria), self.label)
        return self


class Rubric(BaseModel):
    """The scoring rubric: three lenses, default lens weights and the version string."""

    model_config = ConfigDict(extra="forbid")

    rubric_version: str
    lens_weights: dict[Lens, float]
    lenses: dict[Lens, LensDefinition]

    @model_validator(mode="after")
    def _covers_every_lens(self) -> Self:
        if set(self.lens_weights) != set(LENSES) or set(self.lenses) != set(LENSES):
            raise ValueError(f"rubric must define exactly the lenses {list(LENSES)}")
        _require_weights_sum_to_one(self.lens_weights.values(), "lens")
        return self

    @classmethod
    def load(cls, path: Path | None = None) -> Rubric:
        """Load and validate `rubric.yaml` (default: `DATA_DIR/rubric.yaml`)."""
        target = path or get_settings().data_dir / RUBRIC_FILE
        return cls.model_validate(_read_yaml_mapping(target))

    def criteria(self, lens: Lens) -> list[Criterion]:
        return self.lenses[lens].criteria

    def criterion_ids(self, lens: Lens) -> list[str]:
        return [criterion.id for criterion in self.criteria(lens)]

    def criterion(self, lens: Lens, criterion_id: str) -> Criterion:
        for criterion in self.criteria(lens):
            if criterion.id == criterion_id:
                return criterion
        raise ValidationError(f"Unknown criterion {criterion_id!r} in lens {lens!r}")

    def default_criterion_weights(self, lens: Lens) -> dict[str, float]:
        return {criterion.id: criterion.weight for criterion in self.criteria(lens)}


class RankingPreset(BaseModel):
    """Lens weights and optional per-lens criterion weights (document 08 section 3)."""

    model_config = ConfigDict(extra="forbid")

    lens_weights: dict[Lens, float]
    criterion_weights: dict[Lens, dict[str, float]] = Field(default_factory=dict)


class ScenarioPreset(BaseModel):
    """Preset scenario values; `assumed_default` marks design assumptions (document 08 4.1)."""

    model_config = ConfigDict(extra="forbid")

    o2_fraction: float
    pressure_kpa: float
    pressure_psi: float | None = None
    gravity_g: float
    flow_speed_cm_s: float
    assumed_default: bool = False
    note: str = ""


class PresetTexts(BaseModel):
    """Shared wording used by the UI, the API and the agents."""

    model_config = ConfigDict(extra="forbid")

    gravity_bounding: str


class Presets(BaseModel):
    """Ranking presets, scenario presets and shared texts."""

    model_config = ConfigDict(extra="forbid")

    rubric_version: str | None = None
    ranking: dict[str, RankingPreset]
    scenario: dict[str, ScenarioPreset]
    texts: PresetTexts

    @classmethod
    def load(cls, path: Path | None = None) -> Presets:
        """Load and validate `presets.yaml` (default: `DATA_DIR/presets.yaml`)."""
        target = path or get_settings().data_dir / PRESETS_FILE
        return cls.model_validate(_read_yaml_mapping(target))

    def validate_against(self, rubric: Rubric) -> None:
        """Raise when a preset names a criterion the rubric does not define."""
        for name, preset in self.ranking.items():
            for lens, weights in preset.criterion_weights.items():
                unknown = set(weights) - set(rubric.criterion_ids(lens))
                if unknown:
                    raise ValidationError(
                        f"Ranking preset {name!r} names unknown criteria {sorted(unknown)}",
                        {"preset": name, "lens": lens},
                    )

    def gravity_bounding_statement(self, gravity_g: float) -> str:
        """The fixed gravity-bounding statement for a scenario gravity (document 08 4.4)."""
        return self.texts.gravity_bounding.format(gravity_g=f"{gravity_g:g}")
