"""Health and meta endpoints (document 12 s2; document 05 s3; document 08 s1, s3 and s4.1).

Requirements: FR-03 (`/meta/rubric`), FR-04 (`/meta/presets`), FR-13 (`/meta/status` for the
Architecture page), FR-14 (`/meta/stats` for the Overview), NFR-02 (LLM status `mock`).
Call flows: CF-01 (readiness), CF-11 (Overview stats), CF-12 (live component status).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(10)]
OPEN_OR_MIN = (
    "CASE WHEN bool_or({low} IS NULL AND {high} IS NOT NULL) THEN NULL ELSE min({low}) END"
)
OPEN_OR_MAX = (
    "CASE WHEN bool_or({high} IS NULL AND {low} IS NOT NULL) THEN NULL ELSE max({high}) END"
)

Rows = Callable[..., list[dict[str, Any]]]
DOC_08 = "08-scoring-and-scenario.md"
LENSES = ("habitat", "modeling", "controls")
CRITERIA_PER_LENS = 5
COMPONENT_IDS = ["C-API", "C-DB", "C-LLM", "C-ING"]
NUMBER = re.compile(r"\d+(?:\.\d+)?")
STAT_TABLES = {
    "investigations": "investigation",
    "test_runs": "test_run",
    "publications": "publication",
    "findings": "finding",
    "chunks": "chunk",
    "hardware": "hardware",
}
# Document 08 section 4.1: assumed_default is true only for these presets.
ASSUMED_DEFAULT_PRESETS = {"lunar_habitat", "mars_habitat"}


def _numbers(cell: str) -> list[float]:
    return [float(value) for value in NUMBER.findall(cell)]


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def test_cf01_health(stack: str, api: httpx.Client) -> None:
    """CF-01: `GET /health` is `{"status":"ok"}`."""
    response = api.get("/health")
    assert (response.status_code, response.json()) == (httpx.codes.OK, {"status": "ok"})


def test_cf01_ready_fields(
    stack: str, api: httpx.Client, seed_acronyms: list[str], scalar: Callable[..., Any]
) -> None:
    """CF-01: `/ready` reports the database, the applied migration and the investigation count."""
    response = api.get("/ready")
    assert response.status_code == httpx.codes.OK
    assert response.json() == {
        "status": "ready",
        "db": True,
        "migrations": scalar("SELECT version_num FROM alembic_version"),
        "investigations": len(seed_acronyms),
    }


def test_fr14_stats_counts_equal_database(stack: str, api: httpx.Client, sql: Rows) -> None:
    """FR-14, CF-11: `/meta/stats` counts equal the database row counts."""
    stats = api.get("/meta/stats").json()
    expected = {
        key: sql(f'SELECT count(*) AS n FROM "{table}"')[0]["n"]  # noqa: S608 - fixed names
        for key, table in STAT_TABLES.items()
    }
    assert {key: stats[key] for key in STAT_TABLES} == expected


def test_fr14_stats_phases_ranges_and_ingest(
    stack: str, api: httpx.Client, sql: Rows, rubric_file: dict[str, Any]
) -> None:
    """FR-14: fuel-phase counts, oxygen and pressure ranges, rubric version, ingest mode."""
    stats = api.get("/meta/stats").json()
    phases = {
        row["phase"]: row["n"]
        for row in sql(
            "SELECT phase, count(*) AS n FROM investigation, unnest(fuel_phases) AS phase "
            "GROUP BY phase"
        )
    }
    bounds = sql(
        # Doc 05 s3: the union of the ranges; one open (null) end keeps that side open.
        "SELECT CASE WHEN bool_or(o2_min IS NULL AND o2_max IS NOT NULL) THEN NULL "
        "ELSE min(o2_min) END AS o2_low, "
        "CASE WHEN bool_or(o2_max IS NULL AND o2_min IS NOT NULL) THEN NULL "
        "ELSE max(o2_max) END AS o2_high, "
        "CASE WHEN bool_or(pressure_min_kpa IS NULL AND pressure_max_kpa IS NOT NULL) THEN NULL "
        "ELSE min(pressure_min_kpa) END AS p_low, "
        "CASE WHEN bool_or(pressure_max_kpa IS NULL AND pressure_min_kpa IS NOT NULL) THEN NULL "
        "ELSE max(pressure_max_kpa) END AS p_high FROM investigation"
    )[0]
    assert stats["fuel_phase_counts"] == {
        phase: phases.get(phase, 0) for phase in ("gas", "liquid", "solid")
    }
    assert stats["o2_range"] == [
        _optional_float(bounds["o2_low"]),
        _optional_float(bounds["o2_high"]),
    ]
    assert stats["pressure_range_kpa"] == [
        _optional_float(bounds["p_low"]),
        _optional_float(bounds["p_high"]),
    ]
    assert stats["rubric_version"] == rubric_file["rubric_version"]
    assert stats["ingest_mode"] == "seed"
    assert datetime.fromisoformat(stats["last_ingest"])


def test_fr13_status_components(stack: str, api: httpx.Client) -> None:
    """FR-13, CF-12, NFR-02: components C-API, C-DB, C-LLM (`mock`), C-ING."""
    components = {item["id"]: item for item in api.get("/meta/status").json()["components"]}
    assert list(components) == COMPONENT_IDS
    assert (components["C-API"]["status"], components["C-DB"]["status"]) == ("up", "up")
    assert (components["C-LLM"]["status"], components["C-LLM"]["provider"]) == ("mock", "mock")
    assert components["C-ING"]["status"] == "idle"
    assert components["C-ING"]["last_run"]["mode"] == "seed"


def test_fr03_rubric_has_three_lenses_of_five_criteria(
    stack: str,
    api: httpx.Client,
    rubric_criteria: dict[str, dict[str, float]],
    rubric_file: dict[str, Any],
) -> None:
    """FR-03, doc 08 s1: three lenses, fifteen criteria, documented weights and version."""
    rubric = api.get("/meta/rubric").json()
    served = {
        lens: {item["id"]: item["weight"] for item in rubric["lenses"][lens]["criteria"]}
        for lens in rubric["lenses"]
    }
    assert served == rubric_criteria
    assert sum(len(criteria) for criteria in served.values()) == len(LENSES) * CRITERIA_PER_LENS
    assert rubric["lens_weights"] == {"habitat": 0.4, "modeling": 0.3, "controls": 0.3}
    assert rubric["rubric_version"] == rubric_file["rubric_version"]


def test_fr03_rubric_criteria_have_labels_and_anchors(stack: str, api: httpx.Client) -> None:
    """FR-03, doc 08 s1 layout: every criterion has a label and anchors 0, 3 and 5."""
    rubric = api.get("/meta/rubric").json()
    incomplete = [
        criterion["id"]
        for lens in rubric["lenses"].values()
        for criterion in lens["criteria"]
        if not criterion["label"] or not {"0", "3", "5"} <= set(criterion["anchors"])
    ]
    assert incomplete == []


def test_fr04_ranking_presets_equal_document(
    stack: str, api: httpx.Client, ranking_presets: dict[str, dict[str, Any]]
) -> None:
    """FR-04, doc 08 s3: every ranking preset with its lens and criterion weights."""
    assert api.get("/meta/presets").json()["ranking"] == ranking_presets


def test_fr07_scenario_presets_equal_document(
    stack: str, api: httpx.Client, doc_table: Callable[..., list[dict[str, str]]]
) -> None:
    """FR-07, doc 08 s4.1: every scenario preset; `assumed_default` only where documented."""
    served = api.get("/meta/presets").json()["scenario"]
    documented = {
        row["Preset"].strip("`"): (
            _numbers(row["O2 fraction"])[0],
            _numbers(row["Pressure"])[0],
            _numbers(row["Gravity"])[0],
            _numbers(row["Flow"])[0],
            row["Preset"].strip("`") in ASSUMED_DEFAULT_PRESETS,
        )
        for row in doc_table(DOC_08, "### 4.1 Scenario presets")
    }
    actual = {
        name: (
            preset["o2_fraction"],
            preset["pressure_kpa"],
            preset["gravity_g"],
            preset["flow_speed_cm_s"],
            preset["assumed_default"],
        )
        for name, preset in served.items()
    }
    assert actual == documented


def test_fr16_presets_carry_gravity_bounding_template(stack: str, api: httpx.Client) -> None:
    """FR-16, doc 08 s4.4: the shared statement template with its `{gravity_g}` placeholder."""
    template = api.get("/meta/presets").json()["texts"]["gravity_bounding"]
    assert "{gravity_g}" in template
    assert "LUCI" in template
    assert "FM2" in template
