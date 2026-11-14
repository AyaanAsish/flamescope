"""`make deploy` bring-up and health (document 12 section 2; document 11 sections 2, 4, 5).

Requirements: NFR-01 (one deploy command on a Mac), NFR-02 (mock mode forced by the harness),
NFR-05 (re-running deploy is idempotent). Call flows: CF-01 (bring-up order db, ingest job,
api, ui; readiness waits), CF-02 (the seed ingest job inside deploy).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.lifecycle,
    pytest.mark.slow,
    pytest.mark.order(2),
]

LONG_RUNNING_SERVICES = ("db", "api", "ui")
INGEST_BANNER = "Running ingest job (migrate + seed)"
AFTER_INGEST_BANNER = "Starting api and ui"
CARD_VERSIONS = "SELECT acronym, card_version FROM investigation ORDER BY acronym"


@pytest.fixture(scope="module")
def deployed(run_make: Callable[..., Any]) -> subprocess.CompletedProcess[str]:
    return cast("subprocess.CompletedProcess[str]", run_make("deploy"))


def _services(compose: Callable[..., Any]) -> dict[str, dict[str, Any]]:
    listing = compose("ps", "--all", "--format", "json")
    assert listing.returncode == 0, listing.stderr
    rows = [json.loads(line) for line in listing.stdout.splitlines() if line.strip()]
    return {row["Service"]: row for row in rows}


def test_nfr01_make_deploy_exits_zero(deployed: subprocess.CompletedProcess[str]) -> None:
    """NFR-01, CF-01: `make deploy` succeeds and prints the URLs."""
    assert deployed.returncode == 0, f"{deployed.stdout[-4000:]}\n{deployed.stderr[-4000:]}"
    assert "FlameScope is up" in deployed.stdout


@pytest.mark.parametrize("service", LONG_RUNNING_SERVICES)
def test_nfr01_service_running_and_healthy(
    service: str, deployed: subprocess.CompletedProcess[str], compose: Callable[..., Any]
) -> None:
    """CF-01: db, api and ui containers are `running` and `healthy`."""
    row = _services(compose)[service]
    assert (row["State"], row["Health"]) == ("running", "healthy")


def test_cf02_ingest_job_exited_zero(
    deployed: subprocess.CompletedProcess[str], sql: Callable[..., list[dict[str, Any]]]
) -> None:
    """CF-01, CF-02: the one-shot ingest job ran before api/ui and recorded `ok` seed runs.

    `compose run --rm` removes the job container, and `make deploy` stops on a non-zero
    job exit, so the job exit code is proven by the order of the deploy banners.
    """
    output = deployed.stdout
    assert INGEST_BANNER in output
    assert output.index(INGEST_BANNER) < output.index(AFTER_INGEST_BANNER)
    statuses = sql("SELECT DISTINCT mode, status FROM ingest_run")
    assert {"mode": "seed", "status": "ok"} in statuses


def test_cf01_health_and_ready_return_200(
    deployed: subprocess.CompletedProcess[str], api: httpx.Client
) -> None:
    """CF-01: `/api/v1/health` and `/api/v1/ready` return 200."""
    assert api.get("/health").status_code == httpx.codes.OK
    assert api.get("/ready").status_code == httpx.codes.OK


def test_cf01_ui_root_returns_200(
    deployed: subprocess.CompletedProcess[str], ui: httpx.Client
) -> None:
    """CF-01: the UI answers 200 at `/`."""
    assert ui.get("/").status_code == httpx.codes.OK


def test_nfr05_deploy_again_is_idempotent(
    deployed: subprocess.CompletedProcess[str],
    run_make: Callable[..., Any],
    sql: Callable[..., list[dict[str, Any]]],
    api: httpx.Client,
) -> None:
    """NFR-05: a second `make deploy` exits 0 and changes no catalog row or card version."""
    before = sql(CARD_VERSIONS)
    again = run_make("deploy")
    assert again.returncode == 0, f"{again.stdout[-4000:]}\n{again.stderr[-4000:]}"
    assert sql(CARD_VERSIONS) == before
    assert api.get("/ready").json()["investigations"] == len(before)


def test_nfr01_make_status_mentions_every_service(
    deployed: subprocess.CompletedProcess[str], run_make: Callable[..., Any]
) -> None:
    """NFR-01, doc 11 s4: `make status` shows compose ps, `/ready` and `/meta/stats`."""
    status = run_make("status")
    assert status.returncode == 0, status.stderr
    service_lines = {
        service: any(f"-{service}-" in line for line in status.stdout.splitlines())
        for service in LONG_RUNNING_SERVICES
    }
    assert service_lines == dict.fromkeys(LONG_RUNNING_SERVICES, True), status.stdout
    assert "ready: " in status.stdout
    assert "stats: " in status.stdout
