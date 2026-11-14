"""Ranking: lenses, presets, weight sliders, URL state and the evidence drawer.

Requirements FR-03 (ranking with evidence), FR-04 (tunable weights), FR-15 (provenance) and
NFR-09 (disclaimer); document 10 section 5 (`/ranking`), call flow CF-05 (`/meta/rubric`,
`/meta/presets`, `POST /rank`).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.e2e

RANK_LIMIT = 24
PRESET = "lunar_habitat"
LENS_LABELS = {
    "overall": "Overall",
    "habitat": "Habitat",
    "modeling": "Modeling",
    "controls": "Controls",
}
SLIDER_STEPS = 4
SCORE_CELL = 2


def _rank(api: httpx.Client, lens: str, **extra: Any) -> list[dict[str, Any]]:
    body = {"lens": lens, "limit": RANK_LIMIT, **extra}
    return list(api.post("/rank", json=body).json()["items"])


def _score_text(score: float | None) -> str:
    if score is None:
        return "n/a"
    return f"{round(score, 1):g}"


def _rows(page: Page) -> Locator:
    return page.get_by_test_id("rank-row")


def _expect_ranking(page: Page, items: list[dict[str, Any]]) -> None:
    expect(_rows(page)).to_have_count(len(items))
    for index, item in enumerate(items):
        row = _rows(page).nth(index)
        expect(row).to_have_attribute("data-acronym", item["acronym"])
        expect(row.locator("td").nth(SCORE_CELL)).to_contain_text(_score_text(item["score"]))


def _lens_weights_in_url(page: Page) -> dict[str, float]:
    raw = parse_qs(urlparse(page.url).query)["lw"][0]
    pairs = (pair.split(":") for pair in raw.split(","))
    return {lens: float(value) for lens, value in pairs}


@pytest.mark.parametrize("lens", ["habitat", "controls", "overall"])
def test_lens_tabs_switch_and_reorder(
    goto: Callable[..., Page], api: httpx.Client, lens: str
) -> None:
    """FR-03: each lens tab shows its `POST /rank` order and is mirrored in the URL."""
    page = goto("/ranking?lens=modeling")
    page.get_by_test_id("ranking-lens-tabs").get_by_role("tab", name=LENS_LABELS[lens]).click()
    expect(
        page.get_by_test_id("ranking-lens-tabs").get_by_role("tab", selected=True)
    ).to_have_text(LENS_LABELS[lens])
    if lens != "overall":
        expect(page).to_have_url(re.compile(rf"lens={lens}"))
    _expect_ranking(page, _rank(api, lens))


def test_rank_rows_equal_api_order(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-03: the default view shows the overall API ranking with its scores."""
    _expect_ranking(goto("/ranking"), _rank(api, "overall"))


def test_preset_updates_sliders_and_order(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-04: choosing `lunar_habitat` sets its lens weights on the sliders and its ranking."""
    preset = api.get("/meta/presets").json()["ranking"][PRESET]
    page = goto("/ranking")
    page.get_by_test_id("ranking-preset").select_option(PRESET)
    expect(page).to_have_url(re.compile(rf"preset={PRESET}"))
    weights = page.get_by_test_id("ranking-weights")
    for lens, weight in preset["lens_weights"].items():
        slider = weights.get_by_role("slider", name=f"{LENS_LABELS[lens]} weight")
        expect(slider).to_have_attribute("aria-valuenow", f"{weight:g}")
    _expect_ranking(page, _rank(api, "overall", preset=PRESET))


def test_slider_changes_scores_url_and_survives_reload(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-04: keying a weight slider re-ranks after the debounce, updates `lw`, and reloads."""
    page = goto("/ranking")
    slider = page.get_by_test_id("ranking-weights").get_by_role("slider", name="Habitat weight")
    before = float(slider.get_attribute("aria-valuenow") or "nan")
    slider.focus()
    for _ in range(SLIDER_STEPS):
        page.keyboard.press("ArrowRight")
    expect(page).to_have_url(re.compile(r"lw=habitat"))
    lens_weights = _lens_weights_in_url(page)
    assert lens_weights["habitat"] > before
    expected = _rank(api, "overall", lens_weights=lens_weights)
    _expect_ranking(page, expected)
    page.reload()
    expect(slider).to_have_attribute("aria-valuenow", f"{lens_weights['habitat']:g}")
    _expect_ranking(page, expected)


def _item_with_evidence(api: httpx.Client) -> dict[str, Any]:
    items = _rank(api, "habitat")
    return next(i for i in items if any(entry["evidence"] for entry in i["breakdown"]))


def test_evidence_drawer_shows_rationale_and_source(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-03, FR-15: the evidence drawer lists rationales and at least one source link."""
    item = _item_with_evidence(api)
    page = goto("/ranking?lens=habitat")
    row = page.locator(f"[data-testid=rank-row][data-acronym='{item['acronym']}']")
    row.get_by_role("button", name="Evidence").click()
    drawer = page.get_by_test_id("evidence-drawer")
    expect(drawer).to_contain_text(f"{item['acronym']} evidence")
    rationale = next(entry["rationale"] for entry in item["breakdown"] if entry["rationale"])
    expect(drawer.get_by_text(rationale).first).to_be_visible()
    expect(drawer.locator("a[target=_blank]").first).to_be_visible()
    page.keyboard.press("Escape")
    expect(drawer).to_have_count(0)


def test_disclaimer_visible(goto: Callable[..., Page], api: httpx.Client) -> None:
    """NFR-09: the ranking view shows the API score disclaimer."""
    disclaimer = api.post("/rank", json={"lens": "overall", "limit": 1}).json()["disclaimer"]
    expect(goto("/ranking").locator("main").get_by_text(disclaimer).first).to_be_visible()
