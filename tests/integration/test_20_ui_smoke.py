"""UI container smoke test (document 12 section 2; document 10 sections 3 and 5).

Requirements: FR-13 (Architecture page and its draw.io download), NFR-01 (UI served by the
container), NFR-08 (every UI route answers). Call flows: CF-01 (UI readiness), CF-04 to
CF-12 (each route's page shell), with `/api/*` proxied through the Next.js rewrite.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(20)]

DOC_10 = "10-ui-architecture.md"
DETAIL_PLACEHOLDER = "[id]"
HTML = "text/html"
# Document 10 section 3: `public/flamescope-architecture.drawio`.
DRAWIO_PATH = "/flamescope-architecture.drawio"
UNKNOWN_ROUTE = "/no-such-page"


@pytest.fixture(scope="module")
def routes(
    doc_table: Callable[[str, str], list[dict[str, str]]], seed_acronyms: list[str]
) -> list[str]:
    """Document 10 section 5 routes; the detail route uses a seeded acronym."""
    documented = [row["Route"].strip("`") for row in doc_table(DOC_10, "## 5. Routes")]
    return [route.replace(DETAIL_PLACEHOLDER, sorted(seed_acronyms)[0]) for route in documented]


def test_nfr08_every_route_serves_html(stack: str, ui: httpx.Client, routes: list[str]) -> None:
    """NFR-08, doc 10 s5: every route returns 200 with `text/html`."""
    responses = {route: ui.get(route) for route in routes}
    failing = {
        route: (response.status_code, response.headers.get("content-type", ""))
        for route, response in responses.items()
        if response.status_code != httpx.codes.OK
        or not response.headers.get("content-type", "").startswith(HTML)
    }
    assert failing == {}
    assert len(routes) > 1


def test_cf01_api_health_through_ui_rewrite(stack: str, ui: httpx.Client) -> None:
    """CF-01, doc 10 s3: `/api/v1/health` through the UI origin reaches the API."""
    response = ui.get("/api/v1/health")
    assert (response.status_code, response.json()) == (httpx.codes.OK, {"status": "ok"})


def test_nfr08_unknown_route_is_404_page(stack: str, ui: httpx.Client) -> None:
    """NFR-08, doc 10 s3 `not-found.tsx`: an unknown route renders the HTML 404 page."""
    response = ui.get(UNKNOWN_ROUTE)
    assert response.status_code == httpx.codes.NOT_FOUND
    assert response.headers["content-type"].startswith(HTML)


def test_fr13_drawio_download(stack: str, ui: httpx.Client) -> None:
    """FR-13, doc 10 s3: the draw.io architecture file is served."""
    response = ui.get(DRAWIO_PATH)
    assert response.status_code == httpx.codes.OK
    assert "<mxfile" in response.text
