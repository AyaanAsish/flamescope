"""Curator overrides: `src/data/overrides/<acronym>.yaml` deep-merged over a card (document 06)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from flamescope_common.errors import ValidationError

OVERRIDES_DIR = "overrides"
PATH_SEPARATOR = "."


@dataclass
class OverrideResult:
    """The merged mapping and the dotted paths the override file touched."""

    data: dict[str, Any]
    paths: set[str] = field(default_factory=set)

    def covers(self, path: str) -> bool:
        """True when the override touched `path` or any ancestor or descendant of it."""
        return any(
            touched == path
            or touched.startswith(path + PATH_SEPARATOR)
            or path.startswith(touched + PATH_SEPARATOR)
            for touched in self.paths
        )


def override_path(data_dir: Path, acronym: str) -> Path:
    return data_dir / OVERRIDES_DIR / f"{acronym}.yaml"


def load_override(data_dir: Path, acronym: str) -> dict[str, Any]:
    """The override mapping for an acronym; empty when the investigation has no file."""
    path = override_path(data_dir, acronym)
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValidationError(f"Override file must hold a mapping: {path}", {"path": str(path)})
    return loaded


def deep_merge(
    base: Mapping[str, Any], patch: Mapping[str, Any], prefix: str = ""
) -> OverrideResult:
    """Mappings merge recursively; lists and scalars in `patch` replace the base value."""
    merged = dict(base)
    touched: set[str] = set()
    for key, value in patch.items():
        path = f"{prefix}{key}"
        current = merged.get(key)
        if isinstance(value, Mapping) and isinstance(current, Mapping):
            nested = deep_merge(current, value, prefix=f"{path}{PATH_SEPARATOR}")
            merged[key] = nested.data
            touched |= nested.paths
        else:
            merged[key] = value
            touched.add(path)
    return OverrideResult(data=merged, paths=touched)


def apply_override(card: Mapping[str, Any], data_dir: Path, acronym: str) -> OverrideResult:
    """Merge the acronym's override file over `card`; overrides always win."""
    return deep_merge(card, load_override(data_dir, acronym))
