"""Shell: dark theme, sidebar, top bar, footer, global search, every route clean.

Requirements NFR-03 (dark professional UI, usable at 1024 px), NFR-02 (mock mode badge),
FR-14 (overview reachable), NFR-09 (score disclaimer in the footer); document 10 sections 2, 4
and 5; call flow CF-11 (`/meta/stats`) and CF-12 (`/meta/status`).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.e2e

DOC_10 = "10-ui-architecture.md"
CHECKED_TOKENS = ("--bg", "--surface-1", "--accent")
NAV_ORDER = re.compile(r"navigation in this order - (.+?)\.\s*Active")
DETAIL_ROUTE = "/investigations/[id]"
DATA_CREDIT = "Data: NASA Physical Sciences Informatics (PSI)"


def _documented_routes(doc_table: Callable[[str, str], list[dict[str, str]]]) -> list[str]:
    return [row["Route"].strip("`") for row in doc_table(DOC_10, "## 5. Routes")]


def _nav_routes(doc_table: Callable[[str, str], list[dict[str, str]]]) -> list[str]:
    return [route for route in _documented_routes(doc_table) if route != DETAIL_ROUTE]


def _hex_to_rgb(value: str) -> str:
    red, green, blue = (int(value[index : index + 2], 16) for index in (1, 3, 5))
    return f"rgb({red}, {green}, {blue})"


def _sidebar_links(page: Page) -> Locator:
    return page.get_by_role("navigation", name="Main").get_by_role("link")


def test_dark_theme_tokens(
    goto: Callable[..., Page],
    css_var: Callable[[Page, str], str],
    doc_table: Callable[[str, str], list[dict[str, str]]],
) -> None:
    """NFR-03: `html.dark`; `--bg`, `--surface-1`, `--accent` as in doc 10 s2.1; body on `--bg`."""
    page = goto("/")
    tokens = {
        row["Token"].strip("`"): row["Value"].strip("`")
        for row in doc_table(DOC_10, "### 2.1 Tokens")
    }
    expect(page.locator("html")).to_have_class(re.compile(r"\bdark\b"))
    shown = {name: css_var(page, name) for name in CHECKED_TOKENS}
    assert shown == {name: tokens[name].lower() for name in CHECKED_TOKENS}
    body_background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert body_background == _hex_to_rgb(tokens["--bg"])


def test_sidebar_lists_ten_views_in_order(
    goto: Callable[..., Page],
    doc_section: Callable[[str, str], str],
    doc_table: Callable[[str, str], list[dict[str, str]]],
) -> None:
    """NFR-03: the sidebar lists the ten views of doc 10 s4 in order, linking the s5 routes."""
    page = goto("/")
    match = NAV_ORDER.search(" ".join(doc_section(DOC_10, "## 4. Layout").split()))
    assert match is not None
    labels = match.group(1).split(", ")
    links = _sidebar_links(page)
    expect(links).to_have_text(labels)
    hrefs = [links.nth(index).get_attribute("href") for index in range(links.count())]
    assert hrefs == _nav_routes(doc_table)


def test_sidebar_navigates_and_marks_active(
    goto: Callable[..., Page], doc_table: Callable[[str, str], list[dict[str, str]]]
) -> None:
    """NFR-03: each sidebar item navigates to its route and is the one marked active."""
    page = goto("/")
    links = _sidebar_links(page)
    for index, route in enumerate(_nav_routes(doc_table)):
        links.nth(index).click()
        expect(page).to_have_url(re.compile(rf"^[^?]*{re.escape(route)}(\?.*)?$"))
        expect(links.nth(index)).to_have_attribute("aria-current", "page")
        expect(page.locator("nav[aria-label=Main] [aria-current=page]")).to_have_count(1)


def test_top_bar_badges(goto: Callable[..., Page], api: httpx.Client) -> None:
    """NFR-02: the LLM badge shows `mock`; the dataset badge shows mode and `/meta/stats` count."""
    stats = api.get("/meta/stats").json()
    llm = next(c for c in api.get("/meta/status").json()["components"] if c["id"] == "C-LLM")
    assert llm["status"] == "mock"
    banner = goto("/").get_by_role("banner")
    expect(banner.locator("[data-status=mock]")).to_have_text("mock")
    expected = f"{stats['ingest_mode']} · {stats['investigations']} investigations"
    expect(banner.get_by_text(expected, exact=True)).to_be_visible()


def test_footer_disclaimer_and_rubric_version(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """NFR-09: the footer shows the score disclaimer, rubric version and the PSI data credit."""
    disclaimer = api.post("/rank", json={"lens": "overall", "limit": 1}).json()["disclaimer"]
    rubric_version = api.get("/meta/stats").json()["rubric_version"]
    footer = goto("/").locator("footer")
    expect(footer).to_contain_text(disclaimer)
    expect(footer).to_contain_text(f"Rubric {rubric_version}")
    expect(footer).to_contain_text(DATA_CREDIT)


def test_global_search_navigates_to_explorer(goto: Callable[..., Page], sample: Any) -> None:
    """FR-02: `/` focuses the global search; submitting opens Explorer with `q`."""
    page = goto("/")
    page.keyboard.press("/")
    search = page.get_by_role("banner").get_by_role("textbox", name="Search investigations")
    expect(search).to_be_focused()
    search.fill(sample.any)
    search.press("Enter")
    expect(page).to_have_url(re.compile(rf"/explorer\?q={re.escape(sample.any)}$"))
    expect(page.get_by_test_id("explorer-q")).to_have_value(sample.any)


def _route_paths(doc_table: Callable[[str, str], list[dict[str, str]]], acronym: str) -> list[str]:
    detail = f"/investigations/{acronym}"
    return [detail if route == DETAIL_ROUTE else route for route in _documented_routes(doc_table)]


@pytest.mark.parametrize("route_index", range(11))
def test_route_has_no_console_errors(
    route_index: int,
    goto: Callable[..., Page],
    doc_table: Callable[[str, str], list[dict[str, str]]],
    sample: Any,
) -> None:
    """NFR-03: each of the eleven doc 10 s5 routes loads with no console error or failed call."""
    routes = _route_paths(doc_table, sample.any)
    assert len(routes) == 11
    page = goto(routes[route_index])
    expect(page.locator("main h1").first).to_be_visible()


@pytest.mark.parametrize("route_index", range(11))
def test_route_has_no_horizontal_overflow(
    route_index: int,
    page: Page,
    small_page: Page,
    goto: Callable[..., Page],
    request: pytest.FixtureRequest,
) -> None:
    """NFR-03: no horizontal scrollbar at 1440 px and at 1024 px on any route."""
    doc_table = request.getfixturevalue("doc_table")
    route = _route_paths(doc_table, request.getfixturevalue("sample").any)[route_index]
    overflow_check = request.getfixturevalue("expect_no_layout_overflow")
    for target in (page, small_page):
        overflow_check(goto(route, target))
