"""`InvestigationCard` schema and vocabularies (document 04 sections 2, 4 and 5; FR-01)."""

from __future__ import annotations

from typing import Any, get_args

import pytest
from pydantic import ValidationError as PydanticValidationError

from flamescope_common.schemas.card import (
    CARD_SCHEMA_VERSION,
    CoverageState,
    FindingCategory,
    FireSafetyTag,
    GravityLevel,
    InvestigationCard,
    Platform,
    SeedInvestigation,
    acronym_sort_key,
)

pytestmark = pytest.mark.unit

SOURCE = {"kind": "document", "uri": "s3://nasa-psi/test-folder/overview.pdf"}
DOCUMENTED_TAGS = {
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
}
DOCUMENTED_CATEGORIES = {
    "detection",
    "suppression",
    "material_screening",
    "post_fire",
    "atmosphere_design",
    "fundamental",
}
DOCUMENTED_PLATFORMS = {
    "ISS",
    "drop_tower",
    "parabolic",
    "sounding_rocket",
    "suborbital",
    "ground",
}
DOCUMENTED_GRAVITY_LEVELS = {"microgravity", "normal", "partial", "mixed"}


def full_card() -> dict[str, Any]:
    """Every section of the document 04 section 4 shape, with test-only values."""
    return {
        "schema_version": 1,
        "acronym": "TEST-1",
        "title": "Test Investigation",
        "project": None,
        "platform": "ISS",
        "gravity_level": "microgravity",
        "hardware": [{"name": "Test rack", "role": "host"}],
        "objectives": [{"text": "Observe a test flame.", "source": SOURCE}],
        "approach": {"text": "Burn test samples.", "source": SOURCE},
        "fuels": [
            {
                "name": "test fuel",
                "phase": "solid",
                "material_class": None,
                "geometry": {"shape": "sheet", "dimensions_mm": {"thickness": None}},
                "source": SOURCE,
            }
        ],
        "conditions": {
            "o2_fraction": {"min": None, "max": None, "source": None},
            "pressure_kpa": None,
            "flow_speed_cm_s": None,
            "flow_direction": ["quiescent"],
            "gravity_g": [0],
        },
        "variables": {"varied": ["o2_fraction"], "fixed": []},
        "measurements": [{"instrument": "camera", "quantity": "flame shape", "source": SOURCE}],
        "findings": [
            {
                "statement": "A test finding.",
                "category": "fundamental",
                "source": SOURCE,
                "confidence": 0.5,
            }
        ],
        "publications": [{"doi": None, "title": "A test paper", "year": None}],
        "fire_safety_tags": ["flame_spread"],
        "data": {"s3_prefix": None, "volume_bytes": None, "file_types": []},
        "field_confidence": {"fuels": 0.5},
        "open_questions": ["pressure not stated"],
    }


def test_full_card_shape_validates() -> None:
    """FR-01: the card shape of document 04 section 4 validates."""
    card = InvestigationCard.model_validate(full_card())

    assert card.acronym == "TEST-1"
    assert card.fuels[0].geometry is not None
    assert card.schema_version == CARD_SCHEMA_VERSION


def test_minimal_card_leaves_unknowns_null() -> None:
    """FR-01: unknown values are null, never guessed (document 04 section 4)."""
    card = InvestigationCard(acronym="TEST-2", title="Minimal")

    nullable = (card.project, card.platform, card.gravity_level, card.approach, card.conditions)
    assert nullable == (None, None, None, None, None)
    assert (card.data.s3_prefix, card.data.volume_bytes) == (None, None)


def test_publication_optional_fields_default_to_empty() -> None:
    """FR-01: publication authors, venue, url and key_findings are optional."""
    publication = InvestigationCard.model_validate(full_card()).publications[0]

    assert (publication.authors, publication.venue, publication.url) == ([], None, None)
    assert publication.key_findings == []


def test_unknown_tag_is_rejected() -> None:
    """FR-01: fire_safety_tags use the controlled vocabulary (document 04 section 5)."""
    card = full_card() | {"fire_safety_tags": ["flame_spread", "dragons"]}

    with pytest.raises(PydanticValidationError):
        InvestigationCard.model_validate(card)


def test_tag_vocabulary_equals_document_04_section_5() -> None:
    """FR-01: exactly the twenty documented tags."""
    assert set(get_args(FireSafetyTag)) == DOCUMENTED_TAGS


def test_enumerations_equal_document_04() -> None:
    """FR-01: finding categories, platforms, gravity levels and coverage states."""
    assert set(get_args(FindingCategory)) == DOCUMENTED_CATEGORIES
    assert set(get_args(Platform)) == DOCUMENTED_PLATFORMS
    assert set(get_args(GravityLevel)) == DOCUMENTED_GRAVITY_LEVELS
    assert set(get_args(CoverageState)) == {"covered", "extrapolated", "no_data"}


@pytest.mark.parametrize(
    ("field", "value"),
    [("platform", "space_shuttle"), ("gravity_level", "hyper")],
)
def test_values_outside_vocabulary_are_rejected(field: str, value: str) -> None:
    """FR-01: platform and gravity level are enumerations."""
    with pytest.raises(PydanticValidationError):
        InvestigationCard.model_validate(full_card() | {field: value})


def test_finding_without_source_is_rejected() -> None:
    """FR-15: every leaf that states a fact carries a source."""
    card = full_card()
    del card["findings"][0]["source"]

    with pytest.raises(PydanticValidationError):
        InvestigationCard.model_validate(card)


def test_numeric_range_without_source_is_rejected() -> None:
    """FR-15: a stated range is a fact and needs a source."""
    card = full_card()
    card["conditions"]["o2_fraction"] = {"min": 0.2, "max": 0.3, "source": None}

    with pytest.raises(PydanticValidationError):
        InvestigationCard.model_validate(card)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_finding_confidence_is_between_zero_and_one(confidence: float) -> None:
    """FR-01: confidence 0 to 1 (document 04 table `finding`)."""
    card = full_card()
    card["findings"][0]["confidence"] = confidence

    with pytest.raises(PydanticValidationError):
        InvestigationCard.model_validate(card)


def test_unknown_keys_are_ignored() -> None:
    """FR-01: unknown keys are ignored (document 03 section 2 `schemas/card.py`)."""
    card = InvestigationCard.model_validate(full_card() | {"curator_note": "ignored"})

    assert "curator_note" not in card.model_dump()


def test_seed_investigation_is_an_investigation_card() -> None:
    """FR-01: `SeedInvestigation(InvestigationCard)` adds seed-only keys (document 06 s5)."""
    seed = SeedInvestigation.model_validate(full_card() | {"psi_url": "https://psi.nasa.gov/test"})

    assert isinstance(seed, InvestigationCard)
    assert (seed.runs, seed.scores, seed.documents, seed.reviewed) == ([], {}, [], False)


def test_acronym_order_is_case_insensitive_with_exact_tie_break() -> None:
    """Doc 05 s4: `(lower(acronym), acronym)`, compared by code point (no locale)."""
    acronyms = ["SLICE", "s-Flame", "FLEX-2", "Flame-Design", "FLEX", "flex", "BASS-II", "BASS"]
    assert sorted(acronyms, key=acronym_sort_key) == [
        "BASS", "BASS-II", "Flame-Design", "FLEX", "flex", "FLEX-2", "s-Flame", "SLICE",
    ]  # fmt: skip
