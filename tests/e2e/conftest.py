"""End-to-end harness: Playwright for Python on the deployed stack (document 12 sections 3, 4).

The session `stack` fixture reuses a stack that is ready in mock mode and otherwise runs
`make deploy` once with `LLM_PROVIDER=mock EMBED_PROVIDER=mock` (through `run_make`). Each test
gets a fresh Chromium context at 1440x900 (`small_page`: 1024x768); console errors and failed
requests are collected and must be empty when the test ends. A failing test leaves a screenshot
and a Playwright trace in `tests/e2e/artifacts/`. Selectors are the `data-testid` values of
document 10 section 5; everything shown is cross-checked against the API (document 05).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Playwright,
    Request,
    Response,
    expect,
    sync_playwright,
)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
VIEWPORT = {"width": 1440, "height": 900}
SMALL_VIEWPORT = {"width": 1024, "height": 768}
EXPECT_TIMEOUT_MS = 15_000
NAVIGATION_TIMEOUT_MS = 30_000
API_TIMEOUT_S = 30.0
# A request the page itself cancels (navigation, React Query unmount) is not a failure.
CANCELLED_REQUEST = "net::ERR_ABORTED"
HTTP_ERROR_STATUS = 400
MOCK_STATUS = "mock"
LLM_COMPONENT_ID = "C-LLM"
PAGE_SIZE = 100
PHASE_TAGS = {"solid": "solid_fuel", "liquid": "liquid_fuel", "gas": "gaseous_fuel"}
PARTIAL_GRAVITY_GAP = "partial_gravity"
# Source links point at public sites; tests stay offline by answering them with a stub page.
EXTERNAL_URL = re.compile(r"^https?://(?!localhost[:/]|127\.0\.0\.1[:/])")
EXTERNAL_STUB = "<!doctype html><title>external source</title>"
REPORTS_KEY = pytest.StashKey[dict[str, pytest.TestReport]]()


# --- reporting -----------------------------------------------------------------------------


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Any:
    report = yield
    item.stash.setdefault(REPORTS_KEY, {})[report.when] = report
    return report


def _test_failed(item: pytest.Item) -> bool:
    reports = item.stash.get(REPORTS_KEY, {})
    return any(report.failed for report in reports.values())


def _artifact_stem(item: pytest.Item) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", item.nodeid.split("/")[-1])


# --- stack ---------------------------------------------------------------------------------


def _is_ready_in_mock_mode(api_url: str, ui_url: str) -> bool:
    try:
        ready = httpx.get(f"{api_url}/ready", timeout=API_TIMEOUT_S)
        status = httpx.get(f"{api_url}/meta/status", timeout=API_TIMEOUT_S)
        ui = httpx.get(ui_url, timeout=API_TIMEOUT_S)
    except httpx.HTTPError:
        return False
    if ready.status_code != httpx.codes.OK or ui.status_code != httpx.codes.OK:
        return False
    components = {item["id"]: item for item in status.json()["components"]}
    return components.get(LLM_COMPONENT_ID, {}).get("status") == MOCK_STATUS


@pytest.fixture(scope="session")
def stack(run_make: Callable[..., Any], api_url: str, ui_url: str) -> str:
    """The UI base URL of a stack that is ready in mock mode; `make deploy` (mock) once if not."""
    if not _is_ready_in_mock_mode(api_url, ui_url):
        deployed = run_make("deploy")
        assert deployed.returncode == 0, (
            f"make deploy failed:\n{deployed.stdout}\n{deployed.stderr}"
        )
    assert _is_ready_in_mock_mode(api_url, ui_url), "stack not ready in mock mode after deploy"
    return ui_url


# --- browser and pages ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def playwright_driver() -> Iterator[Playwright]:
    with sync_playwright() as driver:
        expect.set_options(timeout=EXPECT_TIMEOUT_MS)
        yield driver


@pytest.fixture(scope="session")
def browser(playwright_driver: Playwright) -> Iterator[Browser]:
    """Chromium, headless unless `HEADED=1`."""
    chromium = playwright_driver.chromium.launch(headless=os.environ.get("HEADED") != "1")
    yield chromium
    chromium.close()


@dataclass
class PageProblems:
    """Console errors and failed requests seen by one page."""

    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)

    def watch(self, page: Page) -> None:
        page.on("console", self._on_console)
        page.on("pageerror", lambda error: self.console_errors.append(f"pageerror: {error}"))
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

    def _on_console(self, message: ConsoleMessage) -> None:
        if message.type == "error":
            self.console_errors.append(f"{message.text} ({message.location.get('url')})")

    def _on_request_failed(self, request: Request) -> None:
        if request.failure != CANCELLED_REQUEST:
            self.failed_requests.append(f"{request.method} {request.url}: {request.failure}")

    def _on_response(self, response: Response) -> None:
        if response.status >= HTTP_ERROR_STATUS:
            self.failed_requests.append(
                f"{response.request.method} {response.url}: HTTP {response.status}"
            )


def _close_context(
    context: BrowserContext, page: Page, item: pytest.Item, problems: PageProblems
) -> None:
    stem = _artifact_stem(item)
    if _test_failed(item):
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=ARTIFACTS_DIR / f"{stem}.png", full_page=True)
        context.tracing.stop(path=ARTIFACTS_DIR / f"{stem}.trace.zip")
    else:
        context.tracing.stop()
    context.close()
    assert problems.console_errors == [], f"console errors: {problems.console_errors}"
    assert problems.failed_requests == [], f"failed requests: {problems.failed_requests}"


def _open_page(
    browser: Browser, ui_url: str, viewport: dict[str, int], item: pytest.Item
) -> Iterator[Page]:
    context = browser.new_context(viewport=viewport, base_url=ui_url, accept_downloads=True)
    context.route(
        EXTERNAL_URL, lambda route: route.fulfill(body=EXTERNAL_STUB, content_type="text/html")
    )
    context.tracing.start(screenshots=True, snapshots=True)
    page = context.new_page()
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    problems = PageProblems()
    problems.watch(page)
    yield page
    _close_context(context, page, item, problems)


@pytest.fixture
def page(browser: Browser, stack: str, request: pytest.FixtureRequest) -> Iterator[Page]:
    """A 1440x900 page; the test fails when a console error or failed request occurred."""
    yield from _open_page(browser, stack, VIEWPORT, request.node)


@pytest.fixture
def small_page(browser: Browser, stack: str, request: pytest.FixtureRequest) -> Iterator[Page]:
    """A 1024x768 page (NFR-03: usable at 1024 px)."""
    yield from _open_page(browser, stack, SMALL_VIEWPORT, request.node)


# --- helpers -------------------------------------------------------------------------------


def navigate(page: Page, route: str) -> Page:
    page.goto(route)
    page.wait_for_load_state("networkidle")
    return page


@pytest.fixture
def goto(request: pytest.FixtureRequest) -> Callable[..., Page]:
    """`goto(route, page=None)`: open a route (default on the 1440x900 page) and settle."""

    def open_route(route: str, target: Page | None = None) -> Page:
        return navigate(target or request.getfixturevalue("page"), route)

    return open_route


def no_layout_overflow(page: Page) -> None:
    widths = page.evaluate(
        """() => [document.documentElement, document.querySelector('main')]
            .filter(Boolean).map((el) => [el.scrollWidth, el.clientWidth])"""
    )
    assert all(scroll <= client for scroll, client in widths), f"horizontal overflow: {widths}"


@pytest.fixture(scope="session")
def expect_no_layout_overflow() -> Callable[[Page], None]:
    """Asserts neither the document nor the scrolling `main` region has a horizontal scrollbar."""
    return no_layout_overflow


@pytest.fixture(scope="session")
def css_var() -> Callable[[Page, str], str]:
    """Computed value of a CSS custom property on `html`, trimmed and lower-cased."""

    def read(page: Page, name: str) -> str:
        script = "(name) => getComputedStyle(document.documentElement).getPropertyValue(name)"
        return str(page.evaluate(script, name)).strip().lower()

    return read


# --- API cross-checks ----------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_session(stack: str, api_url: str) -> Iterator[httpx.Client]:
    """A session-wide API client for cross-checks (document 05)."""
    with httpx.Client(base_url=api_url, timeout=API_TIMEOUT_S) as client:
        yield client


def _all_investigations(client: httpx.Client) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_number = 1
    while True:
        response = client.get(
            "/investigations", params={"page": page_number, "page_size": PAGE_SIZE}
        )
        response.raise_for_status()
        body = response.json()
        items += body["items"]
        if len(items) >= body["total"] or not body["items"]:
            return items
        page_number += 1


def _with_phase(items: list[dict[str, Any]], phase: str) -> str | None:
    by_phase = [item["acronym"] for item in items if phase in item["fuel_phases"]]
    by_tag = [item["acronym"] for item in items if PHASE_TAGS[phase] in item["fire_safety_tags"]]
    return next(iter(by_phase + by_tag), None)


def _analogue(client: httpx.Client) -> str | None:
    gaps = client.get("/insights/gaps").json()["gaps"]
    related = [gap["related"] for gap in gaps if gap["id"] == PARTIAL_GRAVITY_GAP]
    return related[0][0] if related and related[0] else None


@dataclass(frozen=True)
class SeedSample:
    """Seeded acronyms picked from the API: one per fuel phase (by phase, else by fuel tag)."""

    acronyms: list[str]
    solid: str | None
    liquid: str | None
    gas: str | None
    analogue: str | None

    @property
    def any(self) -> str:
        return next(name for name in (self.solid, self.liquid, self.gas, *self.acronyms) if name)


@pytest.fixture(scope="session")
def sample(api_session: httpx.Client) -> SeedSample:
    items = _all_investigations(api_session)
    return SeedSample(
        acronyms=[item["acronym"] for item in items],
        solid=_with_phase(items, "solid"),
        liquid=_with_phase(items, "liquid"),
        gas=_with_phase(items, "gas"),
        analogue=_analogue(api_session),
    )
