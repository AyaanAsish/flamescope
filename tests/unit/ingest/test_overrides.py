"""FR-01: curator overrides deep-merged over a card (document 06 section 3.4).

Mappings merge key by key; lists and scalars replace; overrides always win; every overridden
field is reported as a dotted path.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from flamescope_common.errors import ValidationError
from flamescope_ingest.overrides import apply_override, deep_merge, load_override

pytestmark = pytest.mark.unit

CardFactory = Callable[..., dict[str, Any]]


def _write_override(data_dir: Path, acronym: str, text: str) -> None:
    directory = data_dir / "overrides"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{acronym}.yaml").write_text(text, encoding="utf-8")


def test_mappings_merge_key_by_key() -> None:
    base = {"conditions": {"flow_direction": ["opposed"], "gravity_g": [0]}, "title": "A"}
    merged = deep_merge(base, {"conditions": {"gravity_g": [1]}})
    assert merged.data == {
        "conditions": {"flow_direction": ["opposed"], "gravity_g": [1]},
        "title": "A",
    }
    assert merged.paths == {"conditions.gravity_g"}


def test_lists_replace_rather_than_append() -> None:
    merged = deep_merge({"fire_safety_tags": ["soot", "ignition"]}, {"fire_safety_tags": ["soot"]})
    assert merged.data["fire_safety_tags"] == ["soot"]


def test_scalars_replace_and_null_wins() -> None:
    merged = deep_merge({"platform": "ISS", "title": "A"}, {"platform": None})
    assert merged.data == {"platform": None, "title": "A"}
    assert merged.paths == {"platform"}


def test_new_keys_are_added() -> None:
    merged = deep_merge({"title": "A"}, {"scores": {"habitat": {"fuel_realism": {"value": None}}}})
    assert merged.data["scores"] == {"habitat": {"fuel_realism": {"value": None}}}
    assert merged.paths == {"scores"}


def test_mapping_replaces_non_mapping_value() -> None:
    merged = deep_merge({"approach": None}, {"approach": {"text": "x"}})
    assert merged.data["approach"] == {"text": "x"}


def test_base_is_not_mutated() -> None:
    base = {"conditions": {"gravity_g": [0]}}
    deep_merge(base, {"conditions": {"gravity_g": [1]}})
    assert base == {"conditions": {"gravity_g": [0]}}


def test_covers_matches_ancestors_and_descendants() -> None:
    """Overridden criteria are recognised for `relevance_score.origin = override`."""
    merged = deep_merge({}, {"scores": {"habitat": {"fuel_realism": {"value": 3}}}})
    assert merged.paths == {"scores"}
    assert merged.covers("scores.habitat.fuel_realism")
    nested = deep_merge({"scores": {"habitat": {}}}, {"scores": {"habitat": {"fuel_realism": 1}}})
    assert nested.covers("scores")
    assert nested.covers("scores.habitat.fuel_realism")
    assert not nested.covers("scores.modeling")


def test_missing_override_file_is_empty(tmp_path: Path) -> None:
    assert load_override(tmp_path, "TEST-1") == {}


def test_empty_override_file_is_empty(tmp_path: Path) -> None:
    _write_override(tmp_path, "TEST-1", "")
    assert load_override(tmp_path, "TEST-1") == {}


def test_non_mapping_override_is_rejected(tmp_path: Path) -> None:
    """The override file is a YAML mapping shaped like the card."""
    _write_override(tmp_path, "TEST-1", "- a\n- b\n")
    with pytest.raises(ValidationError):
        load_override(tmp_path, "TEST-1")


def test_apply_override_reads_overrides_dir_and_wins(
    tmp_path: Path, make_card: CardFactory
) -> None:
    """`src/data/overrides/<acronym>.yaml` is merged on top; overrides always win."""
    _write_override(
        tmp_path,
        "TEST-1",
        "title: Curated title\nsummary: Curated summary.\nruns: []\n"
        "conditions:\n  gravity_g: [0]\n",
    )
    card = make_card(conditions={"flow_direction": ["opposed"], "gravity_g": [1]})
    result = apply_override(card, tmp_path, "TEST-1")
    assert result.data["title"] == "Curated title"
    assert result.data["summary"] == "Curated summary."
    assert result.data["conditions"] == {"flow_direction": ["opposed"], "gravity_g": [0]}
    assert result.paths == {"title", "summary", "runs", "conditions.gravity_g"}


def test_apply_override_without_file_returns_card(tmp_path: Path, make_card: CardFactory) -> None:
    card = make_card()
    result = apply_override(card, tmp_path, "TEST-1")
    assert result.data == card
    assert result.paths == set()
