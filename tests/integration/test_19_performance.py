"""Latency of non-LLM endpoints (document 12 section 2; document 01 NFR-04).

Requirements: NFR-04 (non-LLM endpoints under 300 ms p95 on the seed dataset). Every GET of
the document 05 section 11 inventory and `POST /rank` (CF-05) is called once to warm up,
then 30 times sequentially; the p95 values are printed in the terminal summary.
"""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.order(19)]

INVENTORY_DOC = Path(__file__).resolve().parents[2] / "docs/architecture/05-api-specification.md"
INVENTORY_HEADING = "## 11. Endpoint inventory"
GET_ENDPOINT = re.compile(r"`GET (/[^`]*)`")
CALLS = 30
PERCENTILE = 0.95
P95_LIMIT_MS = 300.0
MS_PER_S = 1000.0
RANK_BODY = {"lens": "overall"}
REPORT_SECTION = "NFR-04 latency (p95 over 30 sequential calls)"


def _documented_get_paths() -> list[str]:
    text = INVENTORY_DOC.read_text(encoding="utf-8")
    return GET_ENDPOINT.findall(text[text.index(INVENTORY_HEADING) :])


def _p95_ms(api: httpx.Client, method: str, path: str, body: dict[str, Any] | None) -> float:
    def call() -> float:
        started = time.perf_counter()
        response = api.request(method, path, json=body)
        elapsed = time.perf_counter() - started
        assert response.status_code == httpx.codes.OK, f"{method} {path}: {response.text}"
        return elapsed * MS_PER_S

    call()  # warm-up
    timings = sorted(call() for _ in range(CALLS))
    return timings[math.ceil(PERCENTILE * CALLS) - 1]


Endpoint = tuple[str, str, dict[str, Any] | None]
ENDPOINTS: list[Endpoint] = [
    *(("GET", path, None) for path in _documented_get_paths()),
    ("POST", "/rank", RANK_BODY),
]


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in ENDPOINTS])
def test_nfr04_p95_under_300_ms(
    endpoint: Endpoint,
    stack: str,
    api: httpx.Client,
    seed_acronyms: list[str],
    terminal_report: Any,
) -> None:
    """NFR-04: p95 over 30 sequential calls stays under 300 ms."""
    method, path, body = endpoint
    concrete = path.replace("{id}", sorted(seed_acronyms)[0])
    p95 = _p95_ms(api, method, concrete, body)
    terminal_report.add(REPORT_SECTION, f"{method:<4} {path:<40} p95 {p95:7.1f} ms")
    assert p95 < P95_LIMIT_MS, f"{method} {path} p95 {p95:.1f} ms"
