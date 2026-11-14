"""Compare: picker, difference matrix, cited narrative, hardware lineage.

Requirements FR-05 (compare) and FR-12 (lineage); document 10 section 5 (`/compare`),
document 05 section 6 (matrix attribute order), call flow CF-06 (`POST /compare`,
`GET /hardware`).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.e2e

DOC_05 = "05-api-specification.md"
ATTRIBUTE_ORDER = re.compile(r"Attributes in the matrix, in order: (.+?)\.\n")
PICKED = 3
COMPARE_MAX = 4


def _picked(sample: Any, count: int = PICKED) -> list[str]:
    return sample.acronyms[:count]


def _compare(api: httpx.Client, acronyms: list[str], *, narrative: bool) -> dict[str, Any]:
    body = {"investigations": acronyms, "narrative": narrative}
    return dict(api.post("/compare", json=body).json())


def _ids_in_url(acronyms: list[str]) -> re.Pattern[str]:
    """`ids=` as the URL holds it: comma-separated, the comma possibly percent-encoded."""
    return re.compile("ids=" + "(?:,|%2C)".join(map(re.escape, acronyms)) + "(?:&|$)")


def _pick(page: Page, acronyms: list[str]) -> None:
    for acronym in acronyms:
        page.get_by_test_id("compare-add").select_option(acronym)
    expect(page).to_have_url(_ids_in_url(acronyms))


def _matrix_columns(page: Page) -> Locator:
    return page.get_by_test_id("diff-matrix").locator("thead th")


def test_pick_three_shows_matrix_in_documented_order(
    goto: Callable[..., Page],
    api: httpx.Client,
    sample: Any,
    doc_section: Callable[[str, str], str],
) -> None:
    """FR-05: three picks give the matrix rows in the doc 05 s6 attribute order."""
    acronyms = _picked(sample)
    page = goto("/compare")
    _pick(page, acronyms)
    expect(_matrix_columns(page)).to_have_text(["Attribute", *acronyms, "Match"])
    match = ATTRIBUTE_ORDER.search(doc_section(DOC_05, "## 6. Compare"))
    assert match is not None
    documented = re.findall(r"`([^`]+)`", match.group(1))
    matrix = _compare(api, acronyms, narrative=False)["matrix"]
    assert [row["attribute"] for row in matrix] == documented
    labels = page.get_by_test_id("diff-matrix").locator("tbody tr td:first-child")
    expect(labels).to_have_count(len(matrix))
    for index, row in enumerate(matrix):
        expect(labels.nth(index)).to_contain_text(row["label"])


def test_same_and_different_markers_carry_text_and_icon(
    goto: Callable[..., Page], api: httpx.Client, sample: Any
) -> None:
    """FR-05: each row says Same or Different with an icon, matching the API `same` flag."""
    acronyms = _picked(sample)
    matrix = _compare(api, acronyms, narrative=False)["matrix"]
    rows = (
        goto(f"/compare?ids={','.join(acronyms)}")
        .get_by_test_id("diff-matrix")
        .locator("tbody tr")
    )
    expect(rows).to_have_count(len(matrix))
    for index, row in enumerate(matrix):
        marker = rows.nth(index).locator("td").last
        expect(rows.nth(index)).to_have_attribute("data-same", str(row["same"]).lower())
        expect(marker).to_have_text("Same" if row["same"] else "Different")
        expect(marker.locator("svg")).to_have_count(1)


def test_narrative_sentences_have_citations(
    goto: Callable[..., Page], api: httpx.Client, sample: Any
) -> None:
    """FR-05, FR-15: the mock narrative shows each verified sentence with its source links."""
    acronyms = _picked(sample)
    narrative = _compare(api, acronyms, narrative=True)["narrative"]
    assert narrative["status"] == "ok"
    panel = goto(f"/compare?ids={','.join(acronyms)}").get_by_test_id("compare-narrative")
    sentences = panel.locator("ol > li")
    expect(sentences).to_have_count(len(narrative["sentences"]))
    for index, sentence in enumerate(narrative["sentences"]):
        expect(sentences.nth(index)).to_contain_text(sentence["text"])
        assert sentence["citations"]
        expect(sentences.nth(index).locator("a[target=_blank]")).to_have_count(
            len(sentence["citations"])
        )


def test_removing_one_updates_matrix(goto: Callable[..., Page], sample: Any) -> None:
    """FR-05: removing a selected investigation drops its matrix column and URL entry."""
    acronyms = _picked(sample)
    page = goto(f"/compare?ids={','.join(acronyms)}")
    expect(_matrix_columns(page)).to_have_text(["Attribute", *acronyms, "Match"])
    page.get_by_test_id("compare-picker").get_by_role(
        "button", name=f"Remove {acronyms[0]}", exact=True
    ).click()
    expect(_matrix_columns(page)).to_have_text(["Attribute", *acronyms[1:], "Match"])
    expect(page).to_have_url(_ids_in_url(acronyms[1:]))


def _neighbours(edges: list[dict[str, str]], ids: set[str]) -> set[str]:
    touching = [edge for edge in edges if ids & {edge["source"], edge["target"]}]
    return {end for edge in touching for end in (edge["source"], edge["target"])}


def _hosts(edges: list[dict[str, str]], ids: set[str]) -> set[str]:
    return {
        edge["target"] for edge in edges if edge["role"] == "hosted_in" and edge["source"] in ids
    }


def _lineage_labels(api: httpx.Client, acronyms: list[str]) -> set[str]:
    """Selected investigations, their direct neighbours and the facilities hosting those."""
    graph = api.get("/hardware").json()
    keep = {f"inv:{acronym}" for acronym in acronyms}
    keep |= _neighbours(graph["edges"], keep)
    keep |= _hosts(graph["edges"], keep)
    return {node["label"] for node in graph["nodes"] if node["id"] in keep}


def test_lineage_graph_renders_selection_and_hardware(
    goto: Callable[..., Page], api: httpx.Client, sample: Any
) -> None:
    """FR-12: the lineage graph has a node for each selected investigation and its hardware."""
    acronyms = _picked(sample)
    expected = _lineage_labels(api, acronyms)
    assert set(acronyms) <= expected
    graph = goto(f"/compare?ids={','.join(acronyms)}").get_by_test_id("lineage-graph")
    nodes = graph.locator(".react-flow__node")
    expect(nodes).to_have_count(len(expected))
    shown = {nodes.nth(index).locator("p").first.inner_text() for index in range(nodes.count())}
    assert shown == expected


def test_picker_prevents_a_fifth_selection(goto: Callable[..., Page], sample: Any) -> None:
    """FR-05: with four investigations selected the picker is disabled (2 to 4, doc 05 s6)."""
    page = goto("/compare")
    _pick(page, _picked(sample, COMPARE_MAX))
    picker = page.get_by_test_id("compare-add")
    expect(picker).to_be_disabled()
    expect(picker.locator("option").first).to_have_text(f"Maximum of {COMPARE_MAX} reached")
    expect(_matrix_columns(page)).to_have_count(COMPARE_MAX + 2)
