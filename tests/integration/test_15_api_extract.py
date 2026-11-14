"""Data Extract (document 12 section 2; document 05 section 8; document 08 section 4.2).

Requirements: FR-08 (run table with conditions, outcomes and provenance; CSV and JSON export;
data dictionary), FR-15 (provenance columns). Call flow: CF-08 (Data extract).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(15)]

Rows = Callable[..., list[dict[str, Any]]]
DOC_05 = "05-api-specification.md"
DEFAULT_COLUMNS_PREFIX = "Default columns:"
# Units of document 05 section 1 conventions for the default columns that carry one.
DOCUMENTED_UNITS = {
    "o2_fraction": "fraction",
    "pressure_kpa": "kPa",
    "flow_speed_cm_s": "cm/s",
    "gravity_g": "g",
    "characteristic_dimension_mm": "mm",
    "flame_spread_rate_mm_s": "mm/s",
}
COLUMN_FIELDS = {"name", "label", "unit", "description"}
HEADER_BLOCK_KEYS = ("exported_at", "filters", "rubric_version")
PROVENANCE_COLUMNS = ("source_uri",)
SELECTED_COLUMNS = ["investigation", "o2_fraction", "source_uri"]
MAX_LIMIT = 1000
RUNS_BY_PHASE = (
    "SELECT count(*) AS n FROM test_run t JOIN fuel f ON f.id = t.fuel_id WHERE f.phase = :phase"
)
RUNS_BY_INVESTIGATION = (
    "SELECT count(*) AS n FROM test_run t JOIN investigation i ON i.id = t.investigation_id "
    "WHERE i.acronym = :acronym"
)


def _post(api: httpx.Client, path: str, body: Mapping[str, Any]) -> httpx.Response:
    response = api.post(path, json=body)
    assert response.status_code == httpx.codes.OK, response.text
    return response


def _preview(api: httpx.Client, body: Mapping[str, Any]) -> dict[str, Any]:
    return dict(_post(api, "/extract/preview", body).json())


def _count(sql: Rows, statement: str, **params: Any) -> int:
    return int(sql(statement, **params)[0]["n"])


@pytest.fixture(scope="module")
def default_columns(
    doc_section: Callable[[str, str], str], code_names: Callable[[str], list[str]]
) -> list[str]:
    section = doc_section(DOC_05, "## 8. Extract")
    line = next(line for line in section.splitlines() if line.startswith(DEFAULT_COLUMNS_PREFIX))
    return code_names(line)[: line.count(",") + 1]


@pytest.fixture(scope="module")
def csv_export(stack: str) -> httpx.Response:
    with httpx.Client(base_url=stack, timeout=30.0) as client:
        return _post(client, "/extract/export", {"filters": {}, "format": "csv"})


def test_fr08_dictionary_lists_default_columns_with_units(
    stack: str, api: httpx.Client, default_columns: list[str]
) -> None:
    """FR-08, doc 05 s8: every default column is described, with documented units."""
    columns = {item["name"]: item for item in api.get("/extract/dictionary").json()["columns"]}
    assert set(default_columns) <= set(columns)
    assert {frozenset(item) for item in columns.values()} == {frozenset(COLUMN_FIELDS)}
    assert {name: columns[name]["unit"] for name in DOCUMENTED_UNITS} == DOCUMENTED_UNITS
    assert all(columns[name]["label"] and columns[name]["description"] for name in columns)


def test_fr08_preview_defaults_and_total(
    stack: str, api: httpx.Client, sql: Rows, default_columns: list[str]
) -> None:
    """FR-08: default columns in order; `total` counts every run in the database."""
    preview = _preview(api, {"filters": {}})
    assert [column["name"] for column in preview["columns"]] == default_columns
    assert preview["total"] == _count(sql, "SELECT count(*) AS n FROM test_run")
    assert all(len(row) == len(default_columns) for row in preview["rows"])


def test_fr08_preview_limit_bounds_rows_only(
    stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """FR-08, doc 05 s8: `limit` bounds the preview rows, not `total`; at most 1000."""
    full = _preview(api, {"filters": {}, "limit": MAX_LIMIT})
    limited = _preview(api, {"filters": {}, "limit": 1})
    assert (len(limited["rows"]), limited["total"]) == (min(1, full["total"]), full["total"])
    response = api.post("/extract/preview", json={"filters": {}, "limit": MAX_LIMIT + 1})
    assert_error_envelope(response, 422, "validation_error")


@pytest.mark.parametrize("phase", ["gas", "liquid", "solid"])
def test_fr08_preview_fuel_phase_filter(
    phase: str, stack: str, api: httpx.Client, sql: Rows
) -> None:
    """FR-08: `fuel_phase` keeps runs burning a fuel of that phase."""
    total = _preview(api, {"filters": {"fuel_phase": [phase]}})["total"]
    assert total == _count(sql, RUNS_BY_PHASE, phase=phase)


def test_fr08_preview_investigation_filter(
    stack: str, api: httpx.Client, sql: Rows, seed_acronyms: list[str]
) -> None:
    """FR-08: `investigations` keeps the runs of the listed investigations."""
    totals = {
        acronym: _preview(api, {"filters": {"investigations": [acronym]}})["total"]
        for acronym in seed_acronyms
    }
    expected = {
        acronym: _count(sql, RUNS_BY_INVESTIGATION, acronym=acronym) for acronym in seed_acronyms
    }
    assert totals == expected


def test_fr08_column_selection(
    stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """FR-08, doc 05 s8: chosen columns in order; an unknown column is HTTP 400."""
    preview = _preview(api, {"filters": {}, "columns": SELECTED_COLUMNS})
    assert [column["name"] for column in preview["columns"]] == SELECTED_COLUMNS
    assert all(len(row) == len(SELECTED_COLUMNS) for row in preview["rows"])
    unknown = api.post("/extract/preview", json={"filters": {}, "columns": ["no_such_column"]})
    assert_error_envelope(unknown, 400, "bad_request")


def _csv_parts(body: str) -> tuple[list[str], list[list[str]]]:
    lines = body.splitlines()
    comments = [line for line in lines if line.startswith("#")]
    table = list(
        csv.reader(io.StringIO("\n".join(line for line in lines if not line.startswith("#"))))
    )
    return comments, table


def test_fr08_csv_export_parses_with_header_block(
    csv_export: httpx.Response, api: httpx.Client, default_columns: list[str]
) -> None:
    """FR-08, doc 05 s8: CSV download with a commented header block and one row per run."""
    assert csv_export.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_export.headers["content-disposition"]
    comments, table = _csv_parts(csv_export.text)
    assert all(any(key in comment for comment in comments) for key in HEADER_BLOCK_KEYS)
    assert table[0] == default_columns
    assert len(table) - 1 == _preview(api, {"filters": {}})["total"]


def test_fr15_csv_provenance_columns_filled(csv_export: httpx.Response) -> None:
    """FR-15: every exported run carries its source URI."""
    _, table = _csv_parts(csv_export.text)
    header, rows = table[0], table[1:]
    empty = [row for row in rows for column in PROVENANCE_COLUMNS if not row[header.index(column)]]
    assert empty == []


def test_fr08_json_export(stack: str, api: httpx.Client, default_columns: list[str]) -> None:
    """FR-08: JSON download with the same columns and every matching run."""
    response = _post(api, "/extract/export", {"filters": {}, "format": "json"})
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    exported = json.loads(response.content)
    assert [column["name"] for column in exported["columns"]] == default_columns
    assert len(exported["rows"]) == _preview(api, {"filters": {}})["total"]


def test_fr08_scenario_id_filter_keeps_matching_runs(
    stack: str, api: httpx.Client, seed_acronyms: list[str]
) -> None:
    """FR-08, doc 05 s8: `scenario_id` keeps runs with similarity >= 0.6 (`matching_runs`)."""
    scenario = _post(
        api, "/scenario", {"preset": "lunar_habitat", "limit": len(seed_acronyms)}
    ).json()
    narrowed = _preview(api, {"filters": {"scenario_id": scenario["scenario_id"]}})["total"]
    assert narrowed == sum(match["matching_runs"] for match in scenario["matches"])
    assert narrowed <= _preview(api, {"filters": {}})["total"]


def test_fr08_invalid_scenario_id_is_bad_request(
    stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """FR-08, doc 05 s8: an id that is not a resolved-scenario encoding is HTTP 400."""
    response = api.post("/extract/preview", json={"filters": {"scenario_id": "not-a-scenario"}})
    assert_error_envelope(response, 400, "bad_request")
