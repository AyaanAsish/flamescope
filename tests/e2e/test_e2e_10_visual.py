"""Visual and accessibility checks on every route.

Requirement NFR-03 (dark professional UI) with the binding quality rules of document 10
section 2.3 (contrast at least 4.5:1, visible `--accent` focus ring, 150 ms motion that respects
`prefers-reduced-motion`). Full-page screenshots of every route at 1440x900 go to
`tests/e2e/artifacts/screens/<route>.png` (they feed the decks and README). axe-core is the copy
installed under `src/ui/node_modules` by `make ui-install` (document 12 section 3).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENS_DIR = Path(__file__).resolve().parent / "artifacts" / "screens"
AXE_SCRIPT = REPO_ROOT / "src" / "ui" / "node_modules" / "axe-core" / "axe.min.js"
DOC_10 = "10-ui-architecture.md"
DETAIL_ROUTE = "/investigations/[id]"
BLOCKING_IMPACTS = {"serious", "critical"}
VIEWPORT_WIDTH = 1440
VIEWPORT_HEIGHT = 900
SIDEBAR_LINKS = 10
MAX_TABS_TO_SIDEBAR = 10
MOTION_SECONDS = 0.15
REDUCED_MOTION_MAX_SECONDS = 0.001
DURATION = re.compile(r"([\d.e-]+)(m?s)")
RUN_AXE = """async () => {
  const result = await axe.run(document, {resultTypes: ['violations']});
  return result.violations.map((v) => ({id: v.id, impact: v.impact, help: v.help,
    nodes: v.nodes.slice(0, 5).map((n) => n.target.join(' '))}));
}"""


def _routes(doc_table: Callable[[str, str], list[dict[str, str]]], acronym: str) -> list[str]:
    routes = [row["Route"].strip("`") for row in doc_table(DOC_10, "## 5. Routes")]
    return [f"/investigations/{acronym}" if route == DETAIL_ROUTE else route for route in routes]


def _screen_name(route: str) -> str:
    if route == "/":
        return "overview"
    if route.startswith("/investigations/"):
        return "investigation-detail"
    return route.strip("/")


def _full_page_screenshot(page: Page, path: Path) -> None:
    """The dashboard scrolls inside `main`, so the viewport grows to the content height first."""
    content_height = page.evaluate(
        "() => document.querySelector('main').scrollHeight"
        " + document.querySelector('header').offsetHeight"
    )
    page.set_viewport_size(
        {"width": VIEWPORT_WIDTH, "height": max(VIEWPORT_HEIGHT, content_height)}
    )
    page.wait_for_load_state("networkidle")
    page.screenshot(path=path, full_page=True)
    page.set_viewport_size({"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})


def _seconds(duration: str) -> float:
    match = DURATION.match(duration.split(",")[0].strip())
    assert match is not None, duration
    value = float(match.group(1))
    return value / 1000 if match.group(2) == "ms" else value


@pytest.mark.parametrize("route_index", range(11))
def test_route_screenshot_and_axe(
    route_index: int,
    goto: Callable[..., Page],
    doc_table: Callable[[str, str], list[dict[str, str]]],
    sample: Any,
) -> None:
    """NFR-03: screenshot each route; axe-core finds no serious or critical violation."""
    assert AXE_SCRIPT.is_file(), f"{AXE_SCRIPT} missing: run `make ui-install`"
    route = _routes(doc_table, sample.any)[route_index]
    page = goto(route)
    SCREENS_DIR.mkdir(parents=True, exist_ok=True)
    _full_page_screenshot(page, SCREENS_DIR / f"{_screen_name(route)}.png")
    page.add_script_tag(path=AXE_SCRIPT)
    violations = page.evaluate(RUN_AXE)
    blocking = [v for v in violations if v["impact"] in BLOCKING_IMPACTS]
    assert blocking == [], f"{route}: {blocking}"


def _focused_sidebar_link(page: Page) -> dict[str, str] | None:
    return page.evaluate(
        """async () => {
          const el = document.activeElement;
          if (!el || !el.closest('nav[aria-label=Main]')) return null;
          // The ring fades in over the 150 ms colour transition; read it once that finishes.
          await Promise.all(el.getAnimations().map((animation) => animation.finished));
          const style = getComputedStyle(el);
          return {href: el.getAttribute('href'), style: style.outlineStyle,
                  width: style.outlineWidth, color: style.outlineColor};
        }"""
    )


def test_sidebar_focus_ring_is_visible(
    goto: Callable[..., Page], css_var: Callable[..., str]
) -> None:
    """NFR-03: tabbing reaches every sidebar link, each with a visible `--accent` outline."""
    page = goto("/")
    accent = page.evaluate(
        "(value) => { const el = document.createElement('i'); el.style.color = value;"
        " document.body.append(el); const c = getComputedStyle(el).color; el.remove();"
        " return c; }",
        css_var(page, "--accent"),
    )
    for _ in range(MAX_TABS_TO_SIDEBAR):
        page.keyboard.press("Tab")
        if _focused_sidebar_link(page):
            break
    seen = []
    for _ in range(SIDEBAR_LINKS):
        focus = _focused_sidebar_link(page)
        assert focus is not None, f"focus left the sidebar after {seen}"
        assert (focus["style"], focus["color"]) == ("solid", accent), focus
        assert focus["width"] != "0px", focus
        seen.append(focus["href"])
        page.keyboard.press("Tab")
    assert len(set(seen)) == SIDEBAR_LINKS


def _sidebar_transition(page: Page) -> float:
    duration = (
        page.get_by_role("navigation", name="Main")
        .get_by_role("link")
        .first.evaluate("el => getComputedStyle(el).transitionDuration")
    )
    return _seconds(str(duration))


def test_reduced_motion_disables_transitions(goto: Callable[..., Page]) -> None:
    """NFR-03: transitions run 150 ms, and `prefers-reduced-motion: reduce` disables them."""
    page = goto("/")
    assert _sidebar_transition(page) == pytest.approx(MOTION_SECONDS)
    page.emulate_media(reduced_motion="reduce")
    assert _sidebar_transition(page) <= REDUCED_MOTION_MAX_SECONDS
