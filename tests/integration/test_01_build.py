"""`make build` and the image rules of document 11 section 1 (document 12 section 2).

Requirements: NFR-01 (Mac with Docker, host architecture, one build command).
Call flow: CF-01 (`make build` -> `compose build api ingest ui`).
"""

from __future__ import annotations

import json
import platform
import subprocess
from collections.abc import Callable
from typing import Any, cast

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.lifecycle,
    pytest.mark.slow,
    pytest.mark.order(1),
]

IMAGES = ("flamescope-api:local", "flamescope-ingest:local", "flamescope-ui:local")
NON_ROOT_UID = "10001"
DOCKER_ARCHITECTURES = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64"}
COMPILER_TOOLS = ("gcc", "cc", "g++", "make")
OCI_LABELS = (
    "org.opencontainers.image.title",
    "org.opencontainers.image.description",
    "org.opencontainers.image.version",
)
DOCKER_TIMEOUT_S = 120.0


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed executable, arguments from test code
        ["docker", *args],  # noqa: S607 - docker is resolved from PATH
        capture_output=True,
        text=True,
        check=False,
        timeout=DOCKER_TIMEOUT_S,
    )


def _inspect(image: str) -> dict[str, Any]:
    inspected = _docker("image", "inspect", image)
    assert inspected.returncode == 0, inspected.stderr
    return dict(json.loads(inspected.stdout)[0])


def _run_in(image: str, command: str) -> str:
    ran = _docker("run", "--rm", "--entrypoint", "sh", image, "-c", command)
    assert ran.returncode == 0, ran.stderr
    return ran.stdout.strip()


@pytest.fixture(scope="module")
def built(run_make: Callable[..., Any]) -> subprocess.CompletedProcess[str]:
    return cast("subprocess.CompletedProcess[str]", run_make("build"))


def test_nfr01_make_build_exits_zero(built: subprocess.CompletedProcess[str]) -> None:
    """NFR-01, CF-01: `make build` succeeds."""
    assert built.returncode == 0, f"{built.stdout[-4000:]}\n{built.stderr[-4000:]}"


@pytest.mark.parametrize("image", IMAGES)
def test_nfr01_image_tag_exists(image: str, built: subprocess.CompletedProcess[str]) -> None:
    """NFR-01: the three documented tags exist after the build."""
    assert _inspect(image)["RepoTags"]


@pytest.mark.parametrize("image", IMAGES)
def test_nfr01_image_runs_as_non_root(image: str, built: subprocess.CompletedProcess[str]) -> None:
    """NFR-01, doc 11 s1: non-root user uid 10001."""
    assert _inspect(image)["Config"]["User"] not in ("", "root", "0", "0:0")
    assert _run_in(image, "id -u") == NON_ROOT_UID


@pytest.mark.parametrize("image", IMAGES)
def test_nfr01_image_matches_host_architecture(
    image: str, built: subprocess.CompletedProcess[str]
) -> None:
    """NFR-01, doc 11 s1: images build for the host architecture, no platform pins."""
    assert _inspect(image)["Architecture"] == DOCKER_ARCHITECTURES[platform.machine()]


@pytest.mark.parametrize("image", IMAGES)
def test_nfr01_final_image_has_no_compiler(
    image: str, built: subprocess.CompletedProcess[str]
) -> None:
    """NFR-01, doc 11 s1: no build tools in the final stage."""
    probe = "; ".join(f"command -v {tool} || true" for tool in COMPILER_TOOLS)
    assert _run_in(image, probe) == ""


@pytest.mark.parametrize("image", IMAGES)
def test_nfr01_image_has_oci_labels(image: str, built: subprocess.CompletedProcess[str]) -> None:
    """NFR-01: OCI labels title, description and version are set."""
    labels = _inspect(image)["Config"]["Labels"] or {}
    assert {label: bool(labels.get(label)) for label in OCI_LABELS} == dict.fromkeys(
        OCI_LABELS, True
    )
