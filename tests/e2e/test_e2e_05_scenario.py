"""Scenario Lab: preset form, coverage, gravity bounding, matches, explanation, export.

Requirements FR-07 (scenario), FR-16 (partial-gravity gap), FR-08 (export of matching runs)
and NFR-09 (disclaimer); documents 08 sections 4.1 and 4.4 and 10 section 5 (`/scenario`),
call flow CF-07 (`/meta/presets`, `POST /scenario`, `POST /extract/export`).
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.e2e

PRESET = "lunar_habitat"
STATE_LABELS = {"covered": "Covered", "extrapolated": "Extrapolated", "no_data": "No data"}
COVERAGE_LABELS = {
    "o2_fraction": "Oxygen",
    "pressure_kpa": "Pressure",
    "flow_speed_cm_s": "Flow speed",
    "gravity_g": "Gravity",
}
SKIPPED_EXPLANATION = "No written summary was generated for this selection."
NO_MATCHES = "No investigation has runs near this scenario."


def _scenario(api: httpx.Client, **values: Any) -> dict[str, Any]:
    return dict(api.post("/scenario", json={"preset": PRESET, **values}).json())


def _field(page: Page, label: str) -> Locator:
    return page.get_by_test_id("scenario-form").get_by_label(label, exact=True)


def _open_preset(goto: Callable[..., Page]) -> Page:
    page = goto("/scenario")
    page.get_by_test_id("scenario-preset").select_option(PRESET)
    expect(page).to_have_url(re.compile(rf"preset={PRESET}"))
    return page


def test_preset_fills_form_and_converts_units(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-07: `lunar_habitat` fills 34 %, 56.5 kPa (8.2 psi after the toggle) and 0.166 g."""
    preset = api.get("/meta/presets").json()["scenario"][PRESET]
    page = _open_preset(goto)
    expect(_field(page, "Oxygen (%)")).to_have_value(f"{preset['o2_fraction'] * 100:g}")
    expect(_field(page, "Pressure (kPa)")).to_have_value(f"{preset['pressure_kpa']:g}")
    expect(_field(page, "Gravity (g)")).to_have_value(f"{preset['gravity_g']:g}")
    expect(page.get_by_test_id("scenario-form")).to_contain_text("assumed default")
    page.get_by_role("group", name="Pressure unit").get_by_role("button", name="psi").click()
    expect(_field(page, "Pressure (psi)")).to_have_value(f"{preset['pressure_psi']:g}")
    expect(page).to_have_url(re.compile("unit=psi"))


def test_coverage_panel_states_and_gravity_no_data(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-07, FR-16: each coverage row shows its API state as a label; gravity has no data."""
    coverage = _scenario(api)["coverage"]
    assert coverage["gravity_g"]["state"] == "no_data"
    panel = _open_preset(goto).get_by_test_id("coverage-panel")
    rows = panel.locator("[data-state]")
    expect(rows).to_have_count(len(coverage))
    for index, (key, entry) in enumerate(coverage.items()):
        expect(rows.nth(index)).to_have_attribute("data-state", entry["state"])
        expect(rows.nth(index)).to_contain_text(COVERAGE_LABELS[key])
        expect(rows.nth(index)).to_contain_text(STATE_LABELS[entry["state"]])


def test_gravity_bounding_statement_and_analogue(
    goto: Callable[..., Page], api: httpx.Client, sample: Any
) -> None:
    """FR-16: the card shows the doc 08 s4.4 template for 0.166 g and names the analogue."""
    presets = api.get("/meta/presets").json()
    gravity = presets["scenario"][PRESET]["gravity_g"]
    statement = presets["texts"]["gravity_bounding"].replace("{gravity_g}", f"{gravity:g}")
    assert _scenario(api)["gravity_bounding"]["statement"] == statement
    card = _open_preset(goto).get_by_test_id("gravity-bounding")
    expect(card).to_contain_text(statement)
    expect(card).to_contain_text("No partial-gravity data")
    if sample.analogue:
        expect(card).to_contain_text(f"Analogue: {sample.analogue}")


def test_match_list_equals_api_order(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-07: the match list shows the API matches in order (or the documented empty text)."""
    matches = [match["acronym"] for match in _scenario(api)["matches"]]
    page = _open_preset(goto)
    cards = page.get_by_test_id("scenario-match")
    expect(page.get_by_test_id("coverage-panel")).to_be_visible()
    expect(cards).to_have_count(len(matches))
    for index, acronym in enumerate(matches):
        expect(cards.nth(index)).to_have_attribute("data-acronym", acronym)
    if not matches:
        expect(page.locator("main").get_by_text(NO_MATCHES)).to_be_visible()


def test_explain_shows_text_and_caveats(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-07: Explain shows the verified sentences and caveats, or the documented skipped text."""
    explanation = _scenario(api, explain=True)["explanation"]
    page = _open_preset(goto)
    page.get_by_role("button", name="Explain").click()
    expect(page.locator("main").get_by_text("Interpretation", exact=True)).to_be_visible()
    panel = page.locator("main")
    if explanation["status"] == "skipped":
        expect(panel).to_contain_text(SKIPPED_EXPLANATION)
        return
    for sentence in explanation["sentences"]:
        expect(panel).to_contain_text(sentence["text"])


def _csv_rows(text: str) -> list[dict[str, str]]:
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    return list(csv.DictReader(io.StringIO(body)))


def test_export_matching_runs_csv(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-08: the CSV of matching runs has as many rows as the API extract for `scenario_id`."""
    scenario_id = _scenario(api)["scenario_id"]
    filters = {"scenario_id": scenario_id}
    total = api.post("/extract/preview", json={"filters": filters}).json()["total"]
    page = _open_preset(goto)
    with page.expect_download() as download:
        page.get_by_role("button", name="Export matching runs (CSV)").click()
    path = download.value.path()
    assert download.value.suggested_filename.endswith(".csv")
    assert len(_csv_rows(path.read_text(encoding="utf-8"))) == total


def test_gravity_zero_removes_gap_statement(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-16: at 0 g the scenario has no bounds and no gap statement (doc 08 s4.4)."""
    with_gap = _scenario(api)["gravity_bounding"]["statement"]
    assert _scenario(api, gravity_g=0)["gravity_bounding"]["statement"] is None
    page = _open_preset(goto)
    card = page.get_by_test_id("gravity-bounding")
    expect(card).to_contain_text(with_gap)
    gravity = _field(page, "Gravity (g)")
    gravity.fill("0")
    gravity.press("Enter")
    expect(page).to_have_url(re.compile(r"[?&]g=0(&|$)"))
    expect(card).not_to_contain_text(with_gap)


def test_disclaimer_visible(goto: Callable[..., Page], api: httpx.Client) -> None:
    """NFR-09: the Scenario Lab shows the score disclaimer."""
    disclaimer = api.post("/rank", json={"lens": "overall", "limit": 1}).json()["disclaimer"]
    expect(goto("/scenario").locator("main").get_by_text(disclaimer).first).to_be_visible()
