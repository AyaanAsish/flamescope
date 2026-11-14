"""Safety Tech and Earth Apps.

Requirements FR-09 (safety tech), FR-10 (Earth applications), FR-16 (gaps) and FR-15
(provenance); document 10 section 5 (`/safety-tech`, `/earth`), call flow CF-10
(`/insights/safety-tech`, `/insights/gaps`, `/earth-applications`).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.e2e


def _detail_href(acronym: str) -> str:
    return f"/investigations/{quote(acronym, safe='')}"


def _expect_links(scope: Locator, acronyms: list[str]) -> None:
    for acronym in acronyms:
        expect(scope.locator(f"a[href='{_detail_href(acronym)}']").first).to_be_visible()


def _expect_finding(group: Locator, index: int, finding: dict[str, Any]) -> None:
    item = group.locator("ul > li").nth(index)
    expect(item).to_contain_text(finding["statement"])
    _expect_links(item, [finding["investigation"]])
    expect(item.locator(f"a[href='{finding['source']['uri']}']")).to_have_attribute(
        "target", "_blank"
    )


def test_safety_groups_equal_api(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-09: one card per API category in order, with its findings and linked investigations."""
    groups = api.get("/insights/safety-tech").json()["groups"]
    cards = goto("/safety-tech").get_by_test_id("safety-group")
    expect(cards).to_have_count(len(groups))
    for index, group in enumerate(groups):
        card = cards.nth(index)
        expect(card).to_have_attribute("data-category", group["category"])
        expect(card).to_contain_text(group["label"])
        expect(card).to_contain_text(
            f"{len(group['findings'])} findings from {len(group['investigations'])} investigations"
        )
        _expect_links(card, group["investigations"])
        for finding_index, finding in enumerate(group["findings"]):
            _expect_finding(card, finding_index, finding)


def test_safety_gaps_section_present(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-16: the gaps section lists every API gap, the partial-gravity gap first."""
    gaps = api.get("/insights/gaps").json()["gaps"]
    assert gaps[0]["id"] == "partial_gravity"
    main = goto("/safety-tech").locator("main")
    expect(main.get_by_text("Gaps and future data", exact=True)).to_be_visible()
    for gap in gaps:
        expect(main.get_by_text(gap["detail"], exact=True)).to_be_visible()


def _expect_earth_cards(page: Page, items: list[dict[str, Any]]) -> None:
    cards = page.get_by_test_id("earth-card")
    expect(cards).to_have_count(len(items))
    for index, item in enumerate(items):
        expect(cards.nth(index).get_by_role("heading")).to_have_text(item["title"])
        _expect_links(cards.nth(index), item["investigations"])


def test_earth_cards_equal_api(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-10: the Earth page shows the API applications with links to their investigations."""
    _expect_earth_cards(goto("/earth"), api.get("/earth-applications").json()["items"])


def test_earth_sector_filter(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-10: a sector button shows the API list for that sector and is mirrored in the URL."""
    sector = api.get("/earth-applications").json()["items"][0]["sector"]
    expected = api.get("/earth-applications", params={"sector": sector}).json()["items"]
    page = goto("/earth")
    group = page.get_by_role("group", name="Sector")
    group.get_by_role("button", name=sector.replace("_", " "), exact=False).first.click()
    expect(page).to_have_url(re.compile(rf"sector={sector}"))
    _expect_earth_cards(page, expected)
    group.get_by_role("button", name="All sectors").click()
    expect(page).not_to_have_url(re.compile("sector="))
    _expect_earth_cards(page, api.get("/earth-applications").json()["items"])
