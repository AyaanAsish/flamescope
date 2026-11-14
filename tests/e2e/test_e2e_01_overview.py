"""Overview page: stat tiles, parameter-space scatter, top five, gaps.

Requirements FR-14 (overview) and FR-16 (partial-gravity gap); document 10 section 5 (`/`),
call flow CF-11 (`/meta/stats`, `POST /rank` overall limit 5, `/insights/gaps`,
`POST /extract/preview` with the four scatter columns).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

STAT_TILES = {
    "Investigations": "investigations",
    "Test runs": "test_runs",
    "Publications": "publications",
    "Findings": "findings",
    "Indexed chunks": "chunks",
    "Hardware": "hardware",
}
SCATTER_COLUMNS = ["o2_fraction", "pressure_kpa", "fuel_phase", "investigation"]
SCATTER_LIMIT = 1000
FUEL_PHASES = {"gas", "liquid", "solid"}
PHASE_LEGEND = ["Gas", "Liquid", "Solid"]
TOP_LIMIT = 5
PARTIAL_GRAVITY = re.compile(r"partial[- ]gravity", re.IGNORECASE)


def _plottable_runs(api: httpx.Client) -> int:
    body = {"filters": {}, "columns": SCATTER_COLUMNS, "limit": SCATTER_LIMIT}
    rows = api.post("/extract/preview", json=body).json()["rows"]
    return sum(
        isinstance(o2, float | int) and isinstance(pressure, float | int) and phase in FUEL_PHASES
        for o2, pressure, phase, _ in rows
    )


def test_stat_tiles_equal_meta_stats(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-14: every stat tile shows the `/meta/stats` count (CF-11)."""
    stats = api.get("/meta/stats").json()
    panel = goto("/").get_by_test_id("overview-stats")
    for label, field in STAT_TILES.items():
        tile = panel.locator("div", has=panel.page.get_by_text(label, exact=True)).last
        expect(tile).to_contain_text(f"{stats[field]:,}")


def test_scatter_renders_runs_legend_and_envelope(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-14: one mark per plottable run, a fuel-phase legend and the lunar-habitat envelope.

    Without runs carrying oxygen and pressure the panel shows its documented empty state
    (doc 10 section 2.3 rule 3).
    """
    runs = _plottable_runs(api)
    scatter = goto("/").get_by_test_id("overview-scatter")
    if runs == 0:
        expect(scatter.locator("[data-state=empty]")).to_be_visible()
        return
    expect(scatter.locator(".recharts-scatter-symbol")).to_have_count(runs)
    expect(scatter.locator(".recharts-legend-item")).to_have_text(PHASE_LEGEND)
    expect(scatter.locator(".recharts-reference-area")).to_have_count(1)
    expect(scatter).to_contain_text("Lunar habitat envelope")


def test_top_five_equals_rank_and_links_to_detail(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-14: the top-five list equals `POST /rank` overall limit 5; each row opens its detail."""
    ranked = api.post("/rank", json={"lens": "overall", "limit": TOP_LIMIT}).json()["items"]
    expected = [item["acronym"] for item in ranked]
    page = goto("/")
    links = page.get_by_test_id("overview-top").locator("tbody tr").get_by_role("link")
    expect(links).to_have_text(expected)
    links.first.click()
    expect(page).to_have_url(re.compile(rf"/investigations/{re.escape(expected[0])}$"))
    expect(page.get_by_test_id("detail-header")).to_contain_text(expected[0])


def test_gaps_card_mentions_partial_gravity(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-16: the gaps card shows the API gaps, including the partial-gravity gap."""
    gaps: list[dict[str, Any]] = api.get("/insights/gaps").json()["gaps"]
    assert any(gap["id"] == "partial_gravity" for gap in gaps)
    card = goto("/").get_by_test_id("overview-gaps")
    expect(card).to_contain_text(PARTIAL_GRAVITY)
    for gap in gaps[:4]:
        expect(card).to_contain_text(gap["title"])
