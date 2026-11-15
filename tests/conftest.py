"""Shared fixtures for every test level (document 12 section 4).

Unit tests always run against the mock provider with the repository data directory and
no outbound network (document 12 section 1; NFR determinism, ADR-07). Integration and
end-to-end tests drive the stack through the Makefile with `LLM_PROVIDER=mock` and
`EMBED_PROVIDER=mock` injected into every `make` and compose call (document 12 intro), so
results do not depend on the provider chosen in `.env`.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest

from flamescope_common.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "src" / "data"
SEED_INVESTIGATIONS_DIR = DATA_DIR / "seed" / "investigations"
ENV_FILE = REPO_ROOT / ".env"
DOCS_DIR = REPO_ROOT / "docs" / "architecture"
TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
TABLE_RULE = re.compile(r"^\|[\s:|-]+\|\s*$")
COMPOSE_PROJECT = "flamescope"
COMPOSE_FILE = "deploy/docker/compose.yaml"
API_PREFIX = "/api/v1"
API_TIMEOUT_S = 30.0
MAKE_TIMEOUT_S = 1800.0
COMPOSE_TIMEOUT_S = 600.0
# Document 11 section 3 defaults, used when neither the environment nor .env sets a value.
DOCUMENTED_DEFAULTS = {
    "API_PORT": "8000",
    "UI_PORT": "3000",
    "DB_PORT": "5432",
    "POSTGRES_USER": "flamescope",
    "POSTGRES_PASSWORD": "flamescope",
    "POSTGRES_DB": "flamescope",
    "EMBED_DIM": "768",
    "LLM_TIMEOUT_S": "60",
    "CORS_ORIGINS": "http://localhost:3000",
    "OLLAMA_BASE_URL": "http://host.docker.internal:11434",
    "LLM_MODEL": "qwen2.5:0.5b",
    "EMBED_MODEL": "nomic-embed-text",
}
WAIT_POLL_INTERVAL_S = 1.0
HTTP_OK_LIMIT = 400
MOCK_ENVIRONMENT = {"LLM_PROVIDER": "mock", "EMBED_PROVIDER": "mock"}
# Only in-process unit tests point DATA_DIR at the checkout; containers keep their own path.
UNIT_ENVIRONMENT = {**MOCK_ENVIRONMENT, "DATA_DIR": str(DATA_DIR)}


class NetworkAccessError(RuntimeError):
    """Raised when a unit test opens a socket to a non-loopback address."""


def env_file_value(name: str) -> str | None:
    """The value of the last `NAME=value` line of `.env`, as the Makefile reads it; else None."""
    if not ENV_FILE.is_file():
        return None
    prefix = f"{name}="
    values = [
        line[len(prefix) :].strip()
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines()
        if line.startswith(prefix)
    ]
    return values[-1] if values and values[-1] else None


def env_setting(name: str) -> str:
    """Setting precedence of the Makefile: environment, then `.env`, then the document default."""
    return os.environ.get(name) or env_file_value(name) or DOCUMENTED_DEFAULTS[name]


def api_base_url() -> str:
    return f"http://localhost:{env_setting('API_PORT')}{API_PREFIX}"


def ui_base_url() -> str:
    return f"http://localhost:{env_setting('UI_PORT')}"


def _mock_process_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    return {**os.environ, **MOCK_ENVIRONMENT, **(extra or {})}


def _is_loopback(address: object) -> bool:
    host = address[0] if isinstance(address, tuple) else address
    if not isinstance(host, str):
        return True
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def mock_settings_environment(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Force mock mode (and, for unit tests, the repository data directory)."""
    is_unit = request.node.get_closest_marker("unit") is not None
    for name, value in (UNIT_ENVIRONMENT if is_unit else MOCK_ENVIRONMENT).items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def block_external_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unit tests must not reach the network (document 12 section 1)."""
    if request.node.get_closest_marker("unit") is None:
        return
    original_connect = socket.socket.connect

    def guarded_connect(sock: socket.socket, address: object) -> None:
        if not _is_loopback(address):
            raise NetworkAccessError(f"unit test attempted network access to {address!r}")
        original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def acronym_sort_key(acronym: str) -> tuple[str, str]:
    """Document 05 section 4 acronym order: case-insensitive, the exact acronym breaks ties."""
    return (acronym.lower(), acronym)


@pytest.fixture(scope="session")
def acronym_key() -> Callable[[str], tuple[str, str]]:
    """The documented acronym order as a sort key (`sorted(names, key=acronym_key)`)."""
    return acronym_sort_key


@pytest.fixture(scope="session")
def seed_acronyms() -> list[str]:
    """Seed file names `<acronym>.yaml` (document 06 section 5) in the documented order."""
    stems = (path.stem for path in SEED_INVESTIGATIONS_DIR.glob("*.yaml"))
    acronyms = sorted(stems, key=acronym_sort_key)
    assert acronyms, f"no seed files in {SEED_INVESTIGATIONS_DIR}"
    return acronyms


@pytest.fixture(scope="session")
def run_make() -> Callable[..., subprocess.CompletedProcess[str]]:
    """`run_make(target, env=None, timeout=...)`; mock providers are always injected."""

    def run(
        target: str, env: dict[str, str] | None = None, timeout: float = MAKE_TIMEOUT_S
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - fixed executable, target from test code
            ["make", target],  # noqa: S607 - make is resolved from PATH by design
            cwd=REPO_ROOT,
            env=_mock_process_environment(env),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )

    return run


def compose_command(*args: str) -> list[str]:
    """`docker compose` with the project name, file and env file of the Makefile `COMPOSE`."""
    env_file = ["--env-file", str(ENV_FILE)] if ENV_FILE.is_file() else []
    return ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, *env_file, *args]


@pytest.fixture(scope="session")
def compose() -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - fixed executable, arguments from test code
            compose_command(*args),
            cwd=REPO_ROOT,
            env=_mock_process_environment(),
            capture_output=True,
            text=True,
            check=False,
            timeout=COMPOSE_TIMEOUT_S,
        )

    return run


@pytest.fixture
def api() -> Iterator[httpx.Client]:
    """`httpx.Client` on `http://localhost:{API_PORT}/api/v1` (document 05 base path)."""
    with httpx.Client(base_url=api_base_url(), timeout=API_TIMEOUT_S) as client:
        yield client


@pytest.fixture(scope="session")
def setting() -> Callable[[str], str]:
    """`setting(NAME)`: environment, then `.env`, then the document 11 section 3 default."""
    return env_setting


@pytest.fixture(scope="session")
def api_url() -> str:
    return api_base_url()


@pytest.fixture(scope="session")
def ui_url() -> str:
    return ui_base_url()


def _section_lines(document: str, heading: str) -> list[str]:
    lines = (DOCS_DIR / document).read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(heading))
    level = len(heading) - len(heading.lstrip("#"))
    body: list[str] = []
    for line in lines[start + 1 :]:
        is_heading = line.startswith("#") and len(line) - len(line.lstrip("#")) <= level
        if is_heading:
            break
        body.append(line)
    return body


def _cells(line: str) -> list[str]:
    match = TABLE_ROW.match(line)
    assert match is not None, line
    return [cell.strip() for cell in match.group(1).split("|")]


@pytest.fixture(scope="session")
def doc_section() -> Callable[[str, str], str]:
    """Text of a document section (from its heading to the next heading of the same level)."""

    def read(document: str, heading: str) -> str:
        return "\n".join(_section_lines(document, heading))

    return read


@pytest.fixture(scope="session")
def doc_table() -> Callable[[str, str], list[dict[str, str]]]:
    """Rows of the first Markdown table in a document section, keyed by header cell."""

    def read(document: str, heading: str) -> list[dict[str, str]]:
        table = [line for line in _section_lines(document, heading) if line.startswith("|")]
        header = _cells(table[0])
        rows = [line for line in table[1:] if not TABLE_RULE.match(line)]
        return [dict(zip(header, _cells(line), strict=True)) for line in rows]

    return read


@pytest.fixture(scope="session")
def wait_for() -> Callable[[str, float], bool]:
    def wait(url: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if httpx.get(url, timeout=WAIT_POLL_INTERVAL_S).status_code < HTTP_OK_LIMIT:
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(WAIT_POLL_INTERVAL_S)
        return False

    return wait
