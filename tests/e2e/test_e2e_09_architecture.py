"""Architecture page: seven tabs, React Flow diagrams, node panel, call flows, live status.

Requirement FR-13 (architecture page); document 10 section 6 (tabs, content JSON, node types,
interaction), document 03 (component IDs), document 09 (CF-01 to CF-13), call flow CF-12
(`GET /meta/status`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from itertools import combinations
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

pytestmark = pytest.mark.e2e

DOC_03 = "03-component-design.md"
DOC_09 = "09-call-flows.md"
DOC_10 = "10-ui-architecture.md"
CONTENT_DIR = Path(__file__).resolve().parents[2] / "src" / "ui" / "content" / "architecture"
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "architecture"
COMPONENT_ID = re.compile(r"\bC-[A-Z]+\b")
FLOW_HEADING = re.compile(r"^## (CF-\d{2}) ", re.MULTILINE)
REACT_FLOW = "React Flow"
DIMMED_OPACITY = "0.35"
SAMPLE_NODE = "C-SVC"
ZOOM_STEPS = 3
TRIAL_CLICK_MS = 1_500


def _tabs(doc_table: Callable[[str, str], list[dict[str, str]]]) -> list[dict[str, str]]:
    return doc_table(DOC_10, "### 6.1 Tabs")


def _canvas_tabs(doc_table: Callable[[str, str], list[dict[str, str]]]) -> list[tuple[str, str]]:
    rows = [row for row in _tabs(doc_table) if row["Renderer"].startswith(REACT_FLOW)]
    return [(row["Tab"], row["Content file"].strip("`")) for row in rows]


def _diagram(content_file: str) -> dict[str, Any]:
    return dict(json.loads((CONTENT_DIR / content_file).read_text(encoding="utf-8")))


def _open_tab(page: Page, label: str) -> Locator:
    page.get_by_test_id("arch-tabs").get_by_role("tab", name=label, exact=True).click()
    canvas = page.get_by_test_id("arch-canvas")
    expect(canvas.get_by_test_id("arch-node").first).to_be_visible()
    return canvas


def _node(canvas: Locator, node_id: str) -> Locator:
    return canvas.locator(f".react-flow__node[data-id='{node_id}']")


def _overlaps(boxes: list[dict[str, float]]) -> list[tuple[int, int]]:
    def intersects(a: dict[str, float], b: dict[str, float]) -> bool:
        apart_x = a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
        apart_y = a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]
        return not (apart_x or apart_y)

    pairs = combinations(range(len(boxes)), 2)
    return [(i, j) for i, j in pairs if intersects(boxes[i], boxes[j])]


def _covered_nodes(nodes: Locator) -> list[str]:
    """Nodes a click cannot reach because an overlay (legend, controls, minimap) covers them."""
    covered = []
    for index in range(nodes.count()):
        try:
            nodes.nth(index).click(trial=True, timeout=TRIAL_CLICK_MS)
        except PlaywrightTimeoutError:
            covered.append(nodes.nth(index).inner_text().splitlines()[0])
    return covered


def _token_color(page: Page, token: str) -> str:
    """The computed colour a CSS variable resolves to, in the form `getComputedStyle` reports."""
    script = """(token) => { const probe = document.createElement('div');
        probe.style.backgroundColor = `var(${token})`; document.body.append(probe);
        const color = getComputedStyle(probe).backgroundColor; probe.remove(); return color; }"""
    return str(page.evaluate(script, token))


def _background(locator: Locator) -> str:
    return str(locator.evaluate("(el) => getComputedStyle(el).backgroundColor"))


def test_seven_tabs_in_documented_order(
    goto: Callable[..., Page], doc_table: Callable[[str, str], list[dict[str, str]]]
) -> None:
    """FR-13: the Architecture page has the seven tabs of doc 10 s6.1 in order."""
    labels = [row["Tab"] for row in _tabs(doc_table)]
    assert len(labels) == 7
    tabs = goto("/architecture").get_by_test_id("arch-tabs").get_by_role("tab")
    expect(tabs).to_have_text(labels)


@pytest.mark.parametrize("tab_index", range(6))
def test_canvas_tab_renders_json_nodes_edges_minimap_legend(
    tab_index: int,
    goto: Callable[..., Page],
    doc_table: Callable[[str, str], list[dict[str, str]]],
) -> None:
    """FR-13: each React Flow tab draws its content JSON nodes and edges, minimap and legend,
    with no two node rectangles overlapping on screen (doc 10 s6.2)."""
    label, content_file = _canvas_tabs(doc_table)[tab_index]
    diagram = _diagram(content_file)
    canvas = _open_tab(goto("/architecture"), label)
    nodes = canvas.get_by_test_id("arch-node")
    expect(nodes).to_have_count(len(diagram["nodes"]))
    expect(canvas.locator(".react-flow__edge")).to_have_count(len(diagram["edges"]))
    expect(canvas.locator(".react-flow__minimap")).to_be_visible()
    expect(canvas.get_by_text("Legend", exact=True)).to_be_visible()
    boxes = [box for box in (nodes.nth(i).bounding_box() for i in range(nodes.count())) if box]
    assert len(boxes) == len(diagram["nodes"])
    assert _overlaps(boxes) == []
    assert _covered_nodes(nodes) == []


def test_canvas_minimap_and_controls_are_dark(
    goto: Callable[..., Page], doc_table: Callable[[str, str], list[dict[str, str]]]
) -> None:
    """FR-13, NFR-03: the minimap and zoom controls use the dark `--surface-1` token (doc 10
    s6.3 "minimap (dark)", s2.3 no pure white)."""
    page = goto("/architecture")
    canvas = _open_tab(page, _canvas_tabs(doc_table)[0][0])
    surface = _token_color(page, "--surface-1")
    shown = {
        "minimap": _background(canvas.locator(".react-flow__minimap")),
        "controls": _background(canvas.locator(".react-flow__controls-button").first),
    }
    assert shown == {"minimap": surface, "controls": surface}


def test_components_tab_has_every_doc_03_component(goto: Callable[..., Page]) -> None:
    """FR-13: the Components tab has a node for every component ID of document 03."""
    text = (DOCS_DIR / DOC_03).read_text(encoding="utf-8")
    component_ids = sorted(set(COMPONENT_ID.findall(text)))
    canvas = _open_tab(goto("/architecture"), "Components")
    for component_id in component_ids:
        expect(_node(canvas, component_id)).to_have_count(1)


def test_node_panel_and_related_flow_link(goto: Callable[..., Page]) -> None:
    """FR-13: clicking a node opens its panel; a related flow switches to the Call flows tab."""
    data = next(n for n in _diagram("components.json")["nodes"] if n["id"] == SAMPLE_NODE)["data"]
    page = goto("/architecture")
    canvas = _open_tab(page, "Components")
    _node(canvas, SAMPLE_NODE).click()
    panel = page.get_by_test_id("arch-node-panel")
    expect(panel).to_contain_text(data["responsibility"])
    for item in [*data["interfaces"], *data["files"]]:
        expect(panel.get_by_text(item, exact=True)).to_be_visible()
    flows = panel.get_by_role("button", name=re.compile(r"^CF-\d{2}$"))
    expect(flows).to_have_text(data["flows"])
    flows.first.click()
    expect(page).to_have_url(re.compile(rf"tab=flows&cf={data['flows'][0]}"))
    expect(page.get_by_test_id("arch-sequence")).to_have_attribute("data-flow", data["flows"][0])
    selected = page.get_by_role("list", name="Call flows").locator("button[aria-current=true]")
    expect(selected).to_contain_text(data["flows"][0])


def test_every_call_flow_renders_svg(goto: Callable[..., Page]) -> None:
    """FR-13: CF-01 to CF-13 of document 09 each render a non-empty sequence diagram."""
    flow_ids = FLOW_HEADING.findall((DOCS_DIR / DOC_09).read_text(encoding="utf-8"))
    assert flow_ids == [f"CF-{number:02d}" for number in range(1, 14)]
    page = goto("/architecture?tab=flows")
    flow_list = page.get_by_role("list", name="Call flows").get_by_role("button")
    expect(flow_list).to_have_count(len(flow_ids))
    for index, flow_id in enumerate(flow_ids):
        flow_list.nth(index).click()
        sequence = page.get_by_test_id("arch-sequence")
        expect(sequence).to_have_attribute("data-flow", flow_id)
        expect(sequence.locator("svg g").first).to_be_attached()


def test_status_badges_match_meta_status(goto: Callable[..., Page], api: httpx.Client) -> None:
    """FR-13, NFR-02: node status badges show `/meta/status` (C-LLM shows mock)."""
    statuses = {c["id"]: c["status"] for c in api.get("/meta/status").json()["components"]}
    assert statuses["C-LLM"] == "mock"
    canvas = _open_tab(goto("/architecture"), "Components")
    for node in _diagram("components.json")["nodes"]:
        key = node["data"].get("statusKey")
        if key:
            badge = _node(canvas, node["id"]).locator("[data-status]")
            expect(badge).to_have_attribute("data-status", statuses[key])


def test_hover_dims_unrelated_nodes(goto: Callable[..., Page]) -> None:
    """FR-13: hovering a node dims every node not connected to it (doc 10 s6.4)."""
    diagram = _diagram("components.json")
    related = {SAMPLE_NODE}
    for edge in diagram["edges"]:
        if SAMPLE_NODE in (edge["source"], edge["target"]):
            related |= {edge["source"], edge["target"]}
    canvas = _open_tab(goto("/architecture"), "Components")
    _node(canvas, SAMPLE_NODE).hover()
    for node in diagram["nodes"]:
        card = _node(canvas, node["id"]).get_by_test_id("arch-node")
        opacity = "1" if node["id"] in related else DIMMED_OPACITY
        expect(card).to_have_css("opacity", opacity)


NODES_OUTSIDE_CANVAS = """canvas => {
  const frame = canvas.getBoundingClientRect();
  return [...canvas.querySelectorAll('[data-testid=arch-node]')].filter((node) => {
    const box = node.getBoundingClientRect();
    return box.left < frame.left || box.right > frame.right
      || box.top < frame.top || box.bottom > frame.bottom;
  }).length;
}"""


def _nodes_outside(canvas: Locator) -> int:
    return int(canvas.evaluate(NODES_OUTSIDE_CANVAS))


def test_fit_view_control_brings_every_node_into_view(goto: Callable[..., Page]) -> None:
    """FR-13: after zooming in, the fit-view control shows every node inside the canvas again."""
    page = goto("/architecture")
    canvas = _open_tab(page, "Components")
    assert _nodes_outside(canvas) == 0
    for _ in range(ZOOM_STEPS):
        canvas.locator(".react-flow__controls-zoomin").click()
    page.wait_for_function(
        f"() => ({NODES_OUTSIDE_CANVAS})(document.querySelector('[data-testid=arch-canvas]')) > 0"
    )
    canvas.locator(".react-flow__controls-fitview").click()
    page.wait_for_function(
        f"() => ({NODES_OUTSIDE_CANVAS})("
        "document.querySelector('[data-testid=arch-canvas]')) === 0"
    )


def test_download_drawio_returns_file(goto: Callable[..., Page]) -> None:
    """FR-13: the "Download draw.io" control downloads the draw.io file."""
    page = goto("/architecture")
    with page.expect_download() as download:
        page.get_by_test_id("arch-canvas").get_by_role("link", name="Download draw.io").click()
    assert download.value.suggested_filename == "flamescope-architecture.drawio"
    assert download.value.path().read_text(encoding="utf-8").startswith("<mxfile")
