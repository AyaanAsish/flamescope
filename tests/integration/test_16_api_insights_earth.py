"""Safety tech, gaps and Earth applications (document 12 s2; document 05 s9; document 08 s5).

Requirements: FR-09 (findings grouped by control type), FR-10 (Earth applications and sector
filter), FR-14 (known data gaps on the Overview), FR-15 (finding sources), FR-16 (the
partial-gravity gap with LUCI and FM2). Call flows: CF-10 (Safety Tech, gaps, Earth
applications), CF-11 (Overview gaps card).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(16)]

Rows = Callable[..., list[dict[str, Any]]]
DOC_05 = "05-api-specification.md"
CATEGORY_ORDER_MARKER = "in the order"
PARTIAL_GRAVITY_GAP = "partial_gravity"
FUTURE_EXPERIMENTS = ["LUCI", "FM2"]  # doc 01 s6: expected to add partial-gravity data
ANALOGUE_TAG = "partial_gravity_analogue"
GAP_TITLE = "Untested oxygen and pressure region"
GRAVITY_TOLERANCE = 0.02
# Document 08 section 5 grid: oxygen bins of 0.05 from 0.10 to 1.00; pressure 10 kPa, 20 to 110.
O2_EDGES = [round(0.10 + 0.05 * step, 2) for step in range(19)]
PRESSURE_EDGES = [20 + 10 * step for step in range(10)]
CELL_COUNT = re.compile(r"(\d+) (?:grid )?cells?")
FINDINGS = (
    "SELECT f.id, f.category, i.acronym FROM finding f "
    "JOIN investigation i ON i.id = f.investigation_id"
)
PARTIAL_GRAVITY_RUNS = (
    "SELECT count(*) AS n FROM condition "
    "WHERE gravity_g > :tolerance AND gravity_g < 1 - :tolerance"
)
ANALOGUES = "SELECT acronym FROM investigation WHERE :tag = ANY(fire_safety_tags)"
RUN_SPANS = (
    "SELECT c.o2_fraction AS o2, c.pressure_kpa AS p, t.is_aggregate, t.varied_parameters AS v "
    "FROM test_run t JOIN condition c ON c.test_run_id = t.id"
)
Span = tuple[float, float]


def _span(point: Any, stated: Any) -> Span | None:
    if isinstance(stated, dict) and (stated.get("min"), stated.get("max")) != (None, None):
        low, high = stated.get("min"), stated.get("max")
        return (float("-inf") if low is None else low, float("inf") if high is None else high)
    return None if point is None else (float(point), float(point))


def _overlaps(span: Span, edges: Sequence[float], index: int) -> bool:
    low, high = edges[index], edges[index + 1]
    is_last = index == len(edges) - 2
    return span[0] <= high and span[1] >= low and (is_last or span[0] < high)


def _run_spans(sql: Rows) -> list[tuple[Span, Span]]:
    """Oxygen and pressure spans of every run that states both (doc 08 s4.2 and s5)."""
    spans = []
    for row in sql(RUN_SPANS):
        stated = row["v"] if row["is_aggregate"] else {}
        o2 = _span(row["o2"], stated.get("o2_fraction"))
        pressure = _span(row["p"], stated.get("pressure_kpa"))
        if o2 is not None and pressure is not None:
            spans.append((o2, pressure))
    return spans


def _is_covered(cell: tuple[int, int], spans: list[tuple[Span, Span]]) -> bool:
    i, j = cell
    return any(_overlaps(o2, O2_EDGES, i) and _overlaps(p, PRESSURE_EDGES, j) for o2, p in spans)


def _uncovered_cells(sql: Rows) -> set[tuple[int, int]]:
    spans = _run_spans(sql)
    cells = {(i, j) for i in range(len(O2_EDGES) - 1) for j in range(len(PRESSURE_EDGES) - 1)}
    return {cell for cell in cells if not _is_covered(cell, spans)}


def _cell_count(detail: str) -> int:
    match = CELL_COUNT.search(detail)
    assert match is not None, detail
    return int(match.group(1))


def _neighbours(cell: tuple[int, int]) -> Iterator[tuple[int, int]]:
    i, j = cell
    yield from ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1))


def _region_sizes(cells: set[tuple[int, int]]) -> list[int]:
    """Sizes of the 4-connected regions of uncovered cells (document 08 section 5)."""
    remaining, sizes = set(cells), []
    while remaining:
        frontier, size = [remaining.pop()], 0
        while frontier:
            size += 1
            for neighbour in _neighbours(frontier.pop()):
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    frontier.append(neighbour)
        sizes.append(size)
    return sorted(sizes)


@pytest.fixture(scope="module")
def category_order(
    doc_table: Callable[[str, str], list[dict[str, str]]], code_names: Callable[[str], list[str]]
) -> list[str]:
    """Document 05 section 9: the six finding categories, in order."""
    row = next(
        row
        for row in doc_table(DOC_05, "## 9. Insights")
        if row["Path"] == "`/insights/safety-tech`"
    )
    order_text = row["Response"].split(CATEGORY_ORDER_MARKER, 1)[1].split(";", 1)[0]
    return code_names(order_text)


@pytest.fixture(scope="module")
def gaps(stack: str) -> list[dict[str, Any]]:
    return list(httpx.get(f"{stack}/insights/gaps", timeout=30).json()["gaps"])


def test_fr09_all_categories_in_documented_order(
    stack: str, api: httpx.Client, category_order: list[str]
) -> None:
    """FR-09, doc 05 s9: always all six categories, in order, each with a label."""
    groups = api.get("/insights/safety-tech").json()["groups"]
    assert [group["category"] for group in groups] == category_order
    assert all(group["label"] for group in groups)


def test_fr09_findings_match_database_by_category(
    stack: str, api: httpx.Client, sql: Rows
) -> None:
    """FR-09: each group lists the stored findings of its category and their investigations."""
    groups = api.get("/insights/safety-tech").json()["groups"]
    rows = sql(FINDINGS)
    for group in groups:
        stored = [row for row in rows if row["category"] == group["category"]]
        assert sorted(finding["id"] for finding in group["findings"]) == sorted(
            row["id"] for row in stored
        )
        assert sorted(group["investigations"]) == sorted({row["acronym"] for row in stored})


def test_fr15_findings_have_sources_and_known_investigations(
    stack: str,
    api: httpx.Client,
    seed_acronyms: list[str],
    source_ref_is_valid: Callable[..., bool],
) -> None:
    """FR-09, FR-15: every finding has a valid source and an existing investigation."""
    findings = [
        finding
        for group in api.get("/insights/safety-tech").json()["groups"]
        for finding in group["findings"]
    ]
    invalid = [
        f["id"]
        for f in findings
        if not source_ref_is_valid(f["source"]) or f["investigation"] not in seed_acronyms
    ]
    assert invalid == []


def test_fr16_partial_gravity_gap(gaps: list[dict[str, Any]], sql: Rows) -> None:
    """FR-16, doc 05 s9: `partial_gravity` comes first while no run is strictly in (0 g, 1 g)."""
    partial_runs = sql(PARTIAL_GRAVITY_RUNS, tolerance=GRAVITY_TOLERANCE)[0]["n"]
    if partial_runs:
        assert PARTIAL_GRAVITY_GAP not in [gap["id"] for gap in gaps]
        return
    analogues = [row["acronym"] for row in sql(ANALOGUES, tag=ANALOGUE_TAG)]
    first = gaps[0]
    assert (first["id"], first["future"], sorted(first["related"])) == (
        PARTIAL_GRAVITY_GAP,
        FUTURE_EXPERIMENTS,
        sorted(analogues),
    )
    assert first["title"] and first["detail"]


def test_fr14_parameter_space_gaps_follow_grid_regions(
    gaps: list[dict[str, Any]], sql: Rows
) -> None:
    """FR-14, doc 08 s5: one `param_gap_<n>` per 4-connected uncovered region and its size."""
    regions = [gap for gap in gaps if gap["id"] != PARTIAL_GRAVITY_GAP]
    assert [gap["id"] for gap in regions] == [f"param_gap_{n}" for n in range(1, len(regions) + 1)]
    assert {(gap["title"], tuple(gap["related"]), tuple(gap["future"])) for gap in regions} <= {
        (GAP_TITLE, (), ())
    }
    counts = sorted(_cell_count(gap["detail"]) for gap in regions)
    assert counts == _region_sizes(_uncovered_cells(sql))


def test_fr10_earth_applications_from_curated_file(
    stack: str,
    api: httpx.Client,
    earth_file: dict[str, Any],
    seed_acronyms: list[str],
    source_ref_is_valid: Callable[..., bool],
) -> None:
    """FR-10, doc 04 s2: every curated application is listed with valid references and links."""
    items = api.get("/earth-applications").json()["items"]
    assert sorted((i["title"], i["sector"]) for i in items) == sorted(
        (a["title"], a["sector"]) for a in earth_file["applications"]
    )
    assert all(all(map(source_ref_is_valid, item["references"])) for item in items)
    assert {acronym for item in items for acronym in item["investigations"]} <= set(seed_acronyms)


def test_fr10_sector_filter(stack: str, api: httpx.Client, earth_file: dict[str, Any]) -> None:
    """FR-10, doc 05 s9: `sector` returns exactly the curated applications of that sector."""
    sectors = {application["sector"] for application in earth_file["applications"]}
    actual = {
        sector: sorted(
            i["title"]
            for i in api.get("/earth-applications", params={"sector": sector}).json()["items"]
        )
        for sector in sectors
    }
    expected = {
        sector: sorted(a["title"] for a in earth_file["applications"] if a["sector"] == sector)
        for sector in sectors
    }
    assert actual == expected
