"""`rubric.yaml` and `presets.yaml` against document 08 sections 1, 3, 4.1 and 4.4."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from flamescope_common.errors import ValidationError
from flamescope_common.rubric import Presets, Rubric

pytestmark = pytest.mark.unit

WEIGHT_TOLERANCE = 1e-9
RUBRIC_VERSION = "2026.11-1"
LENS_WEIGHTS = {"habitat": 0.4, "modeling": 0.3, "controls": 0.3}
CRITERIA: dict[str, list[tuple[str, str, float]]] = {
    "habitat": [
        ("fuel_realism", "Fuel realism", 0.25),
        ("atmosphere_match", "Atmosphere match", 0.25),
        ("flow_regime", "Flow regime", 0.15),
        ("phenomenon", "Phenomenon relevance", 0.20),
        ("gravity_bounding", "Gravity bounding value", 0.15),
    ],
    "modeling": [
        ("quantitative_outputs", "Quantitative outputs", 0.25),
        ("parameter_sweep", "Parameter sweep breadth", 0.25),
        ("geometry_definition", "Geometry and boundary definition", 0.15),
        ("data_accessibility", "Data accessibility", 0.20),
        ("model_validation", "Model and correlation support", 0.15),
    ],
    "controls": [
        ("detection", "Detection", 0.25),
        ("suppression", "Suppression and extinction", 0.25),
        ("material_screening", "Material screening", 0.20),
        ("post_fire", "Post-fire and hidden hazards", 0.15),
        ("hardware_heritage", "Hardware and sensor heritage", 0.15),
    ],
}
RANKING_LENS_WEIGHTS = {
    "balanced": (0.4, 0.3, 0.3),
    "lunar_habitat": (0.6, 0.2, 0.2),
    "spacecraft_cabin": (0.5, 0.2, 0.3),
    "modeler": (0.2, 0.6, 0.2),
    "equipment_designer": (0.2, 0.2, 0.6),
}
CRITERION_EMPHASIS: dict[str, dict[str, dict[str, float]]] = {
    "balanced": {},
    "modeler": {},
    "lunar_habitat": {
        "habitat": {
            "atmosphere_match": 0.35,
            "fuel_realism": 0.25,
            "gravity_bounding": 0.20,
            "phenomenon": 0.15,
            "flow_regime": 0.05,
        }
    },
    "spacecraft_cabin": {
        "habitat": {
            "flow_regime": 0.25,
            "fuel_realism": 0.25,
            "phenomenon": 0.25,
            "atmosphere_match": 0.15,
            "gravity_bounding": 0.10,
        }
    },
    "equipment_designer": {
        "controls": {
            "detection": 0.30,
            "suppression": 0.30,
            "material_screening": 0.16,
            "post_fire": 0.12,
            "hardware_heritage": 0.12,
        }
    },
}
SCENARIO_PRESETS = {
    "lunar_habitat": (0.34, 56.5, 0.166, 10, True),
    "lunar_habitat_threshold": (0.30, 70.3, 0.166, 10, False),
    "iss_cabin": (0.21, 101.3, 0, 10, False),
    "spacesuit": (1.00, 29.6, 0, 0, False),
    "mars_habitat": (0.34, 56.5, 0.38, 10, True),
}


@pytest.fixture(scope="module")
def rubric() -> Rubric:
    return Rubric.load(Path(__file__).resolve().parents[3] / "src" / "data" / "rubric.yaml")


@pytest.fixture(scope="module")
def presets() -> Presets:
    return Presets.load(Path(__file__).resolve().parents[3] / "src" / "data" / "presets.yaml")


def test_rubric_loads_from_data_dir() -> None:
    """FR-03: `Rubric.load()` reads `DATA_DIR/rubric.yaml`."""
    assert Rubric.load().rubric_version == RUBRIC_VERSION


def test_rubric_version_and_lens_weights(rubric: Rubric) -> None:
    """FR-03: version string and default lens weights W (document 08 sections 1 and 2)."""
    assert rubric.rubric_version == RUBRIC_VERSION
    assert rubric.lens_weights == LENS_WEIGHTS
    assert sum(rubric.lens_weights.values()) == pytest.approx(1.0, abs=WEIGHT_TOLERANCE)


@pytest.mark.parametrize("lens", list(CRITERIA))
def test_lens_has_the_five_documented_criteria(rubric: Rubric, lens: str) -> None:
    """FR-03: IDs, labels and default weights per lens, in the order of document 08."""
    actual = [(c.id, c.label, c.weight) for c in rubric.criteria(lens)]  # type: ignore[arg-type]

    assert actual == CRITERIA[lens]


@pytest.mark.parametrize("lens", list(CRITERIA))
def test_criterion_weights_sum_to_one_per_lens(rubric: Rubric, lens: str) -> None:
    """FR-03: weights within a lens sum to 1."""
    weights = rubric.default_criterion_weights(lens)  # type: ignore[arg-type]

    assert sum(weights.values()) == pytest.approx(1.0, abs=WEIGHT_TOLERANCE)


@pytest.mark.parametrize("lens", list(CRITERIA))
def test_every_criterion_has_the_three_anchors(rubric: Rubric, lens: str) -> None:
    """FR-03: anchors 0, 3 and 5 for every criterion (document 08 section 1)."""
    anchor_keys = {frozenset(c.anchors) for c in rubric.criteria(lens)}  # type: ignore[arg-type]

    assert anchor_keys == {frozenset({0, 3, 5})}


def test_ranking_presets_are_the_documented_five(presets: Presets) -> None:
    """FR-04: preset names and lens weights habitat / modeling / controls."""
    actual = {
        name: tuple(preset.lens_weights[lens] for lens in LENS_WEIGHTS)
        for name, preset in presets.ranking.items()
    }

    assert actual == RANKING_LENS_WEIGHTS


@pytest.mark.parametrize("name", list(CRITERION_EMPHASIS))
def test_ranking_preset_criterion_emphasis(presets: Presets, name: str) -> None:
    """FR-04: criterion emphasis of each preset (document 08 section 3)."""
    assert presets.ranking[name].criterion_weights == CRITERION_EMPHASIS[name]


@pytest.mark.parametrize("name", list(RANKING_LENS_WEIGHTS))
def test_preset_weights_sum_to_one(presets: Presets, name: str) -> None:
    """FR-04: lens weights and each lens's criterion weights sum to 1."""
    preset = presets.ranking[name]
    sums = [sum(preset.lens_weights.values())]
    sums += [sum(weights.values()) for weights in preset.criterion_weights.values()]

    assert sums == pytest.approx([1.0] * len(sums), abs=WEIGHT_TOLERANCE)


def test_presets_reference_only_existing_lenses_and_criteria(
    rubric: Rubric, presets: Presets
) -> None:
    """FR-04: every preset lens and criterion exists in the rubric."""
    presets.validate_against(rubric)
    referenced = {
        (lens, criterion)
        for preset in presets.ranking.values()
        for lens, weights in preset.criterion_weights.items()
        for criterion in weights
    }
    known = {(lens, cid) for lens, rows in CRITERIA.items() for cid, _label, _weight in rows}

    assert referenced <= known


def test_scenario_presets_equal_document_08_section_4_1(presets: Presets) -> None:
    """FR-07: o2, pressure, gravity, flow and `assumed_default` of each scenario preset."""
    actual = {
        name: (p.o2_fraction, p.pressure_kpa, p.gravity_g, p.flow_speed_cm_s, p.assumed_default)
        for name, p in presets.scenario.items()
    }

    assert actual == SCENARIO_PRESETS


def test_gravity_bounding_statement_uses_python_g_format(presets: Presets) -> None:
    """FR-16: the template's `{gravity_g}` is formatted with `:g` (document 08 section 4.4)."""
    statement = presets.gravity_bounding_statement(0.166)

    assert "0.166 g" in statement
    assert "{gravity_g}" not in statement
    assert "LUCI" in statement
    assert "FM2" in statement


def write_yaml(path: Path, content: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return path


def rubric_document(rubric: Rubric) -> dict[str, object]:
    return rubric.model_dump(mode="json")


def test_rubric_rejects_unknown_keys(rubric: Rubric, tmp_path: Path) -> None:
    """FR-03: unknown keys in `rubric.yaml` are rejected (document 08 section 1)."""
    document = rubric_document(rubric) | {"comment_weights": {"habitat": 1}}

    with pytest.raises(PydanticValidationError):
        Rubric.load(write_yaml(tmp_path / "rubric.yaml", document))


def test_rubric_rejects_lens_weights_not_summing_to_one(rubric: Rubric, tmp_path: Path) -> None:
    """FR-03: lens weights must sum to 1."""
    document = rubric_document(rubric) | {
        "lens_weights": {"habitat": 0.5, "modeling": 0.3, "controls": 0.3}
    }

    with pytest.raises(PydanticValidationError):
        Rubric.load(write_yaml(tmp_path / "rubric.yaml", document))


def test_rubric_rejects_a_missing_lens(rubric: Rubric, tmp_path: Path) -> None:
    """FR-03: exactly the lenses habitat, modeling, controls."""
    document = rubric_document(rubric)
    lenses = dict(document["lenses"])  # type: ignore[call-overload]
    del lenses["controls"]
    document["lenses"] = lenses

    with pytest.raises(PydanticValidationError):
        Rubric.load(write_yaml(tmp_path / "rubric.yaml", document))


def test_presets_reject_unknown_criterion(
    rubric: Rubric, presets: Presets, tmp_path: Path
) -> None:
    """FR-04: criterion IDs in presets must exist in the rubric."""
    document = presets.model_dump(mode="json")
    document["ranking"]["typo"] = {
        "lens_weights": LENS_WEIGHTS,
        "criterion_weights": {"habitat": {"fuel_reality": 1.0}},
    }
    loaded = Presets.load(write_yaml(tmp_path / "presets.yaml", document))

    with pytest.raises(ValidationError):
        loaded.validate_against(rubric)


def test_presets_reject_unknown_keys(presets: Presets, tmp_path: Path) -> None:
    """FR-04: unknown keys in `presets.yaml` are rejected (document 08 section 3)."""
    document = presets.model_dump(mode="json") | {"extras": {}}

    with pytest.raises(PydanticValidationError):
        Presets.load(write_yaml(tmp_path / "presets.yaml", document))


def test_missing_rubric_file_is_a_validation_error(tmp_path: Path) -> None:
    """FR-03: a missing configuration file is reported, not ignored."""
    with pytest.raises(ValidationError):
        Rubric.load(tmp_path / "absent.yaml")
