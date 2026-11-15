"""Explorer and investigation detail.

Requirements FR-01 (cards), FR-02 (search and filter), FR-06 (run variables), FR-15
(provenance links); document 10 section 5 (`/explorer`, `/investigations/[id]`), call flow
CF-04 (`/investigations`, `/facets`, detail, `/runs`, `/variables`).
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

DOC_10 = "10-ui-architecture.md"
PAGE_SIZE = 24
# Doc 05 s1 maximum page size, the page the Test runs tab requests.
RUNS_PAGE_SIZE = 100
DETAIL_TABS = re.compile(r"tabs: (.+)$")
FALLBACK_PHASE = "solid"


def _acronyms(api: httpx.Client, **params: Any) -> list[str]:
    body = api.get("/investigations", params={"page_size": PAGE_SIZE, **params}).json()
    return [item["acronym"] for item in body["items"]]


def _cards(page: Page) -> Locator:
    return page.get_by_test_id("investigation-card")


def _expect_cards(page: Page, acronyms: list[str]) -> None:
    if not acronyms:
        expect(
            page.locator("section[aria-label=Investigations] [data-state=empty]")
        ).to_be_visible()
    expect(_cards(page)).to_have_count(len(acronyms))
    for index, acronym in enumerate(acronyms):
        expect(_cards(page).nth(index)).to_have_attribute("data-acronym", acronym)


def _documented_detail_tabs(doc_table: Callable[[str, str], list[dict[str, str]]]) -> list[str]:
    row = next(
        r for r in doc_table(DOC_10, "## 5. Routes") if r["Route"] == "`/investigations/[id]`"
    )
    match = DETAIL_TABS.search(row["Key components"])
    assert match is not None
    return match.group(1).split(", ")


def test_card_count_equals_api_total(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-01: the grid shows the first API page of `GET /investigations` in acronym order."""
    total = api.get("/investigations").json()["total"]
    page = goto("/explorer")
    expected = _acronyms(api, sort="acronym")
    assert len(expected) == min(total, PAGE_SIZE)
    _expect_cards(page, expected)


def test_fuel_phase_filter_updates_cards_url_and_clears(
    goto: Callable[..., Page], api: httpx.Client
) -> None:
    """FR-02: a fuel-phase filter narrows the cards to the API result and is mirrored in the URL.

    With no fuel phase in the facets the filter is applied through its URL parameter (doc 10
    section 5: filters are linkable) and the documented empty state is asserted.
    """
    facets = api.get("/facets").json()["fuel_phase"]
    phase = facets[0]["value"] if facets else FALLBACK_PHASE
    page = goto("/explorer")
    if facets:
        page.get_by_test_id("explorer-filters").get_by_role(
            "checkbox", name=re.compile(rf"^{re.escape(phase)}\b", re.I)
        ).click()
    else:
        page.goto(f"/explorer?fuel_phase={phase}")
    expect(page).to_have_url(re.compile(rf"fuel_phase={phase}"))
    _expect_cards(page, _acronyms(api, fuel_phase=phase))
    page.get_by_test_id("explorer-filters").get_by_role("button", name="Clear").click()
    expect(page).not_to_have_url(re.compile("fuel_phase"))
    _expect_cards(page, _acronyms(api, sort="acronym"))


def test_search_by_acronym_finds_card(
    goto: Callable[..., Page], api: httpx.Client, sample: Any
) -> None:
    """FR-02: searching an acronym shows the API search result, including that card."""
    page = goto("/explorer")
    search = page.get_by_test_id("explorer-q")
    search.fill(sample.any)
    search.press("Enter")
    expect(page).to_have_url(re.compile(rf"q={re.escape(sample.any)}"))
    expected = _acronyms(api, q=sample.any)
    assert sample.any in expected
    _expect_cards(page, expected)


def test_sort_changes_order(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-02: sorting by overall score shows the API `sort=overall` order."""
    page = goto("/explorer")
    page.get_by_test_id("explorer-sort").select_option("overall")
    expect(page).to_have_url(re.compile("sort=overall"))
    by_score = _acronyms(api, sort="overall")
    assert by_score != _acronyms(api, sort="acronym")
    _expect_cards(page, by_score)


def _open_detail(page: Page, acronym: str) -> Locator:
    page.goto("/explorer")
    card = page.locator(f"[data-testid=investigation-card][data-acronym='{acronym}']")
    card.get_by_role("link", name=acronym, exact=True).click()
    header = page.get_by_test_id("detail-header")
    expect(header.get_by_role("heading", level=1)).to_have_text(acronym)
    return header


def test_detail_header_psi_link_and_tabs(
    page: Page,
    api: httpx.Client,
    sample: Any,
    doc_table: Callable[[str, str], list[dict[str, str]]],
) -> None:
    """FR-01, FR-15: header with a PSI link opening safely in a new tab, and the seven tabs."""
    header = _open_detail(page, sample.any)
    detail = api.get(f"/investigations/{sample.any}").json()
    psi = header.get_by_role("link", name="View in PSI")
    expect(psi).to_have_attribute("href", detail["psi_url"])
    expect(psi).to_have_attribute("target", "_blank")
    expect(psi).to_have_attribute("rel", re.compile(r"\bnoopener\b"))
    tabs = page.get_by_test_id("detail-tabs").get_by_role("tab")
    expect(tabs).to_have_text(_documented_detail_tabs(doc_table))


def test_runs_table_rows_equal_runs_endpoint(page: Page, api: httpx.Client, sample: Any) -> None:
    """FR-06: the Test runs tab lists the `/runs` page (empty state when none are recorded)."""
    runs = _runs_page(api, sample.any, 1)["items"]
    _open_detail(page, sample.any)
    page.get_by_test_id("detail-tabs").get_by_role("tab", name="Test runs").click()
    table = page.get_by_test_id("runs-table")
    if not runs:
        expect(table.locator("[data-state=empty]")).to_be_visible()
        return
    expect(table.locator("tbody tr")).to_have_count(len(runs))
    for index, run in enumerate(runs):
        expect(table.locator("tbody tr").nth(index)).to_contain_text(run["label"])


def _runs_page(api: httpx.Client, acronym: str, number: int) -> dict[str, Any]:
    params = {"page": number, "page_size": RUNS_PAGE_SIZE}
    return dict(api.get(f"/investigations/{quote(acronym, safe='')}/runs", params=params).json())


def test_runs_table_pages_through_the_largest_investigation(page: Page, api: httpx.Client) -> None:
    """FR-06: an investigation with more runs than one page pages through all of them."""
    items = api.get("/investigations", params={"page_size": RUNS_PAGE_SIZE}).json()["items"]
    totals = {item["acronym"]: _runs_page(api, item["acronym"], 1)["total"] for item in items}
    acronym = max(totals, key=lambda key: totals[key])
    if totals[acronym] <= RUNS_PAGE_SIZE:
        pytest.skip("no seeded investigation has more runs than one page (doc 01 OI-06)")
    last = -(-totals[acronym] // RUNS_PAGE_SIZE)
    page.goto(f"/investigations/{quote(acronym, safe='')}")
    page.get_by_test_id("detail-tabs").get_by_role("tab", name="Test runs").click()
    table = page.get_by_test_id("runs-table")
    pagination = table.get_by_role("navigation", name="Pagination")
    expect(pagination).to_contain_text(f"page 1 of {last}")
    for _ in range(last - 1):
        pagination.get_by_role("button", name="Next").click()
    expected = _runs_page(api, acronym, last)["items"]
    expect(pagination).to_contain_text(f"page {last} of {last}")
    expect(table.locator("tbody tr")).to_have_count(len(expected))
    expect(table.locator("tbody tr").last).to_contain_text(expected[-1]["label"])


def test_variables_panel_shows_varied_and_fixed(
    page: Page, api: httpx.Client, sample: Any
) -> None:
    """FR-06: the Variables tab shows the varied and fixed parameters of `/variables`."""
    variables = api.get(f"/investigations/{sample.any}/variables").json()
    _open_detail(page, sample.any)
    page.get_by_test_id("detail-tabs").get_by_role("tab", name="Variables").click()
    panel = page.get_by_role("tabpanel")
    if not variables["varied"] and not variables["fixed"]:
        expect(panel.locator("[data-state=empty]")).to_be_visible()
        return
    expect(panel.get_by_text("Varied parameters")).to_be_visible()
    expect(panel.get_by_text("Fixed parameters")).to_be_visible()
    expect(panel.locator("li")).to_have_count(len(variables["varied"]))
    expect(panel.locator("dl > div")).to_have_count(len(variables["fixed"]))


def _with_evidence(api: httpx.Client, acronyms: list[str]) -> tuple[str, dict[str, Any]]:
    for acronym in acronyms:
        detail = api.get(f"/investigations/{acronym}").json()
        for entry in detail["score_breakdown"].values():
            for item in (entry or {}).get("breakdown", []):
                if item["evidence"]:
                    return acronym, item["evidence"][0]
    raise AssertionError("no seeded investigation has score evidence (doc 13 FR-15)")


def test_scores_tab_source_link_opens_source(page: Page, api: httpx.Client, sample: Any) -> None:
    """FR-15: a criterion source link in the Scores tab opens its source in a new tab.

    The detail route shows the evidence inline (doc 10 section 5 lists no evidence drawer for
    `/investigations/[id]`; see DESIGN-CONFLICTS DC-50).
    """
    acronym, source = _with_evidence(api, sample.acronyms)
    _open_detail(page, acronym)
    page.get_by_test_id("detail-tabs").get_by_role("tab", name="Scores").click()
    link = page.get_by_role("tabpanel").locator(f"a[href='{source['uri']}']").first
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", re.compile(r"\bnoopener\b"))
    with page.context.expect_page() as opened:
        link.click()
    assert opened.value.url.startswith(source["uri"].split("?")[0])
    opened.value.close()
