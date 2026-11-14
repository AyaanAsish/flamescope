"""Undeploy: `make undeploy` removes everything of the compose project and is repeatable.

Requirement NFR-01 (Mac + Docker lifecycle); document 11 section 4 (`undeploy`), call flow
CF-13 (`docker compose -p flamescope down -v --remove-orphans`). Runs last; skipped when
`KEEP_STACK=1` so the stack stays up for inspection.
"""

from __future__ import annotations

import os
import socket
import subprocess
from collections.abc import Callable
from typing import Any

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.lifecycle,
    pytest.mark.skipif(os.environ.get("KEEP_STACK") == "1", reason="KEEP_STACK=1 keeps the stack"),
]

PROJECT_LABEL = "label=com.docker.compose.project=flamescope"
LOCALHOST = "127.0.0.1"
CONNECT_TIMEOUT_S = 2.0
DOCKER_LISTINGS = {
    "containers": ["docker", "ps", "-a", "--filter", PROJECT_LABEL, "--format", "{{.Names}}"],
    "networks": ["docker", "network", "ls", "--filter", PROJECT_LABEL, "--format", "{{.Name}}"],
    "volumes": ["docker", "volume", "ls", "--filter", PROJECT_LABEL, "--format", "{{.Name}}"],
}


def _leftovers() -> dict[str, list[str]]:
    found = {}
    for kind, command in DOCKER_LISTINGS.items():
        listed = subprocess.run(command, capture_output=True, text=True, check=True)  # noqa: S603
        found[kind] = listed.stdout.split()
    return found


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(CONNECT_TIMEOUT_S)
        return probe.connect_ex((LOCALHOST, port)) == 0


def test_undeploy_removes_everything_and_is_repeatable(
    run_make: Callable[..., Any], setting: Callable[[str], str]
) -> None:
    """NFR-01, CF-13: undeploy exits 0, leaves no labelled resources or open ports, and repeats."""
    first = run_make("undeploy")
    assert first.returncode == 0, f"{first.stdout}\n{first.stderr}"
    assert _leftovers() == {kind: [] for kind in DOCKER_LISTINGS}
    ports = {name: int(setting(name)) for name in ("API_PORT", "UI_PORT")}
    assert {name: _port_is_open(port) for name, port in ports.items()} == dict.fromkeys(
        ports, False
    )
    again = run_make("undeploy")
    assert again.returncode == 0, f"{again.stdout}\n{again.stderr}"
