"""Data Extract: dictionary, query builder, preview, column picker, CSV and JSON exports.

Requirement FR-08 (extract, with FR-15 provenance columns); documents 05 section 8 and 10
section 5 (`/extract`), call flow CF-08 (`/extract/dictionary`, `/extract/preview`,
`/extract/export`).
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.e2e

PROVENANCE_COLUMNS = {"source_uri", "source_locator"}
CSV_HEADER_KEYS = ("exported_at", "filters", "rubric_version")
TOGGLED_COLUMN = "investigation"


def _preview(api: httpx.Client, filters: dict[str, Any], columns: list[str] | None = None) -> Any:
    body: dict[str, Any] = {"filters": filters, **({"columns": columns} if columns else {})}
    return api.post("/extract/preview", json=body).json()


def _expect_preview(page: Page, table: dict[str, Any]) -> None:
    preview = page.get_by_test_id("extract-preview")
    if not table["rows"]:
        expect(preview.locator("[data-state=empty]")).to_be_visible()
        return
    expect(preview.locator("thead th")).to_have_count(len(table["columns"]))
    expect(preview.locator("tbody tr")).to_have_count(len(table["rows"]))
    expect(preview).to_contain_text(f"Showing {len(table['rows'])} of {table['total']} runs")


def _column_checkbox(page: Page, label: str) -> Locator:
    return page.locator("main").get_by_role("checkbox", name=label, exact=True)


def test_dictionary_drawer_lists_columns_with_units(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-08: the data dictionary drawer lists every column with its unit (or none)."""
    columns = api.get("/extract/dictionary").json()["columns"]
    page = goto("/extract")
    page.get_by_role("button", name="Data dictionary").click()
    rows = page.get_by_role("dialog", name="Data dictionary").locator("tbody tr")
    expect(rows).to_have_count(len(columns))
    for index, column in enumerate(columns):
        cells = rows.nth(index).locator("td")
        expect(cells.nth(0)).to_contain_text(column["name"])
        expect(cells.nth(1)).to_have_text(column["unit"] or "none")
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_query_filter_preview_equals_api(
    goto: Callable[..., Page], api: httpx.Client, sample: Any
) -> None:
    """FR-08: an investigation filter narrows the preview to the API preview of that filter."""
    page = goto("/extract")
    _expect_preview(page, _preview(api, {}))
    query = page.get_by_test_id("extract-query")
    checkbox = query.get_by_role("checkbox", name=sample.any, exact=True)
    checkbox.click()
    expect(checkbox).to_be_checked()
    expect(page).to_have_url(re.compile(rf"inv={re.escape(sample.any)}"))
    _expect_preview(page, _preview(api, {"investigations": [sample.any]}))


def test_toggle_column_off_and_on(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-08: choosing a column narrows the preview to it; clearing it restores the defaults."""
    label = next(
        c for c in api.get("/extract/dictionary").json()["columns"] if c["name"] == TOGGLED_COLUMN
    )["label"]
    page = goto("/extract")
    checkbox = _column_checkbox(page, label)
    checkbox.click()
    expect(checkbox).to_be_checked()
    expect(page).to_have_url(re.compile(rf"cols={TOGGLED_COLUMN}"))
    _expect_preview(page, _preview(api, {}, [TOGGLED_COLUMN]))
    checkbox.click()
    expect(checkbox).not_to_be_checked()
    expect(page).not_to_have_url(re.compile("cols="))
    _expect_preview(page, _preview(api, {}))


def _download(page: Page, test_id: str) -> tuple[str, str]:
    with page.expect_download() as download:
        page.get_by_test_id(test_id).click()
    return download.value.suggested_filename, download.value.path().read_text(encoding="utf-8")


def test_csv_export_has_header_block_provenance_and_rows(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-08, FR-15: the CSV carries the commented header block, provenance columns, all rows."""
    total = _preview(api, {})["total"]
    filename, text = _download(goto("/extract"), "export-csv")
    assert filename.endswith(".csv")
    comments = [line for line in text.splitlines() if line.startswith("#")]
    assert [line.split(":")[0].lstrip("# ") for line in comments] == list(CSV_HEADER_KEYS)
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    reader = csv.DictReader(io.StringIO(body))
    rows = list(reader)
    assert set(reader.fieldnames or []) >= PROVENANCE_COLUMNS
    assert len(rows) == total


def test_json_export_has_meta_provenance_and_rows(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-08, FR-15: the JSON export carries meta, provenance columns and every matching run."""
    total = _preview(api, {})["total"]
    rubric_version = api.get("/meta/stats").json()["rubric_version"]
    filename, text = _download(goto("/extract"), "export-json")
    assert filename.endswith(".json")
    exported = json.loads(text)
    assert exported["meta"]["rubric_version"] == rubric_version
    assert {column["name"] for column in exported["columns"]} >= PROVENANCE_COLUMNS
    assert len(exported["rows"]) == total
