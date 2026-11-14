"""Host prerequisites for the stack (document 12 section 2; document 11 sections 1 to 4).

Requirements: NFR-01 (Mac with Docker, one command per lifecycle step), NFR-06 (`.env`
from the committed `.env.example`). Call flow: CF-01 (preconditions of bring-up).
"""

from __future__ import annotations

import re
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.lifecycle, pytest.mark.order(0)]

COMPOSE_V2 = re.compile(r"v?2\.\d+")
PORT_SETTINGS = ("API_PORT", "UI_PORT", "DB_PORT")
CONNECT_TIMEOUT_S = 1.0
DOCKER_TIMEOUT_S = 60.0


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed executable, arguments from test code
        ["docker", *args],  # noqa: S607 - docker is resolved from PATH
        capture_output=True,
        text=True,
        check=False,
        timeout=DOCKER_TIMEOUT_S,
    )


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(CONNECT_TIMEOUT_S)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _ports_published_by_stack() -> set[int]:
    listing = _docker(
        "ps", "--filter", "label=com.docker.compose.project=flamescope", "--format", "{{.Ports}}"
    )
    return {int(port) for port in re.findall(r":(\d+)->", listing.stdout)}


def test_nfr01_docker_daemon_reachable() -> None:
    """NFR-01: the Docker daemon answers."""
    info = _docker("info", "--format", "{{.ServerVersion}}")
    assert info.returncode == 0, info.stderr
    assert info.stdout.strip()


def test_nfr01_compose_v2_present() -> None:
    """NFR-01: Docker Compose v2 (`docker compose`) is installed."""
    version = _docker("compose", "version", "--short")
    assert version.returncode == 0, version.stderr
    assert COMPOSE_V2.match(version.stdout.strip()), version.stdout


@pytest.mark.parametrize("port_setting", PORT_SETTINGS)
def test_nfr01_port_free_or_owned_by_stack(
    port_setting: str, setting: Callable[[str], str]
) -> None:
    """NFR-01: each host port is free, or published by our own `flamescope` stack."""
    port = int(setting(port_setting))
    if not _port_in_use(port):
        return
    assert port in _ports_published_by_stack(), f"{port_setting}={port} is used by another process"


def test_nfr06_env_file_exists(run_make: Callable[..., Any], repo_root: Path) -> None:
    """NFR-06: `make env` leaves a `.env` (created from `.env.example` when missing)."""
    created = run_make("env")
    assert created.returncode == 0, created.stderr
    assert (repo_root / ".env").is_file()
    assert (repo_root / ".env.example").is_file()
