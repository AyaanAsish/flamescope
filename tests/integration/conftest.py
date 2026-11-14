"""Integration harness (document 12 sections 2 and 4).

The lifecycle files (`test_00` to `test_04`) build and deploy the stack first; the session
`stack` fixture makes the API files usable on their own against an already running stack
and brings the stack up in mock mode when it is missing. The stack is left running at the
end of the session (end-to-end tests reuse it; `make undeploy` or the last end-to-end test
removes it).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from sqlalchemy import Engine, create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "src" / "data"
SEED_INVESTIGATIONS_DIR = DATA_DIR / "seed" / "investigations"
API_TIMEOUT_S = 30.0
READY_TIMEOUT_S = 180.0
MOCK_STATUS = "mock"
LLM_COMPONENT_ID = "C-LLM"


@dataclass
class TerminalReport:
    """Lines printed in the pytest terminal summary, grouped by section title.

    `test_19_performance.py` reports its p95 timings and `test_21_llm_ollama.py` the live-model
    outcome here, so both are visible in `make test-integration` output.
    """

    sections: dict[str, list[str]] = field(default_factory=dict)

    def add(self, section: str, line: str) -> None:
        self.sections.setdefault(section, []).append(line)


REPORT_KEY = pytest.StashKey[TerminalReport]()


def pytest_configure(config: pytest.Config) -> None:
    config.stash[REPORT_KEY] = TerminalReport()


def pytest_terminal_summary(terminalreporter: Any, config: pytest.Config) -> None:
    report = config.stash.get(REPORT_KEY, None)
    for section, lines in (report.sections if report else {}).items():
        terminalreporter.section(section)
        for line in lines:
            terminalreporter.write_line(line)


@pytest.fixture(scope="session")
def terminal_report(pytestconfig: pytest.Config) -> TerminalReport:
    return pytestconfig.stash[REPORT_KEY]


# --- stack ---------------------------------------------------------------------------------


def _stack_is_ready_in_mock_mode(api_url: str) -> bool:
    try:
        ready = httpx.get(f"{api_url}/ready", timeout=API_TIMEOUT_S)
        status = httpx.get(f"{api_url}/meta/status", timeout=API_TIMEOUT_S)
    except httpx.HTTPError:
        return False
    if ready.status_code != httpx.codes.OK or status.status_code != httpx.codes.OK:
        return False
    components = {item["id"]: item for item in status.json()["components"]}
    return bool(components.get(LLM_COMPONENT_ID, {}).get("status") == MOCK_STATUS)


@pytest.fixture(scope="session")
def stack(run_make: Callable[..., Any], api_url: str) -> str:
    """The API base URL of a ready stack in mock mode; deploys it (mock) when needed."""
    if not _stack_is_ready_in_mock_mode(api_url):
        deployed = run_make("deploy")
        assert deployed.returncode == 0, (
            f"make deploy failed:\n{deployed.stdout}\n{deployed.stderr}"
        )
    assert _stack_is_ready_in_mock_mode(api_url), "stack not ready in mock mode after make deploy"
    return api_url


@pytest.fixture
def ui(ui_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=ui_url, timeout=API_TIMEOUT_S) as client:
        yield client


# --- database ------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db(setting: Callable[[str], str]) -> Iterator[Engine]:
    """SQLAlchemy engine on `localhost:{DB_PORT}` built from the `.env` values."""
    url = (
        f"postgresql+psycopg://{setting('POSTGRES_USER')}:{setting('POSTGRES_PASSWORD')}"
        f"@localhost:{setting('DB_PORT')}/{setting('POSTGRES_DB')}"
    )
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def sql(db: Engine) -> Callable[..., list[dict[str, Any]]]:
    """Run a read-only query and return its rows as dictionaries."""

    def run(statement: str, **params: Any) -> list[dict[str, Any]]:
        with db.connect() as connection:
            return [dict(row) for row in connection.execute(text(statement), params).mappings()]

    return run


@pytest.fixture(scope="session")
def scalar(db: Engine) -> Callable[..., Any]:
    def run(statement: str, **params: Any) -> Any:
        with db.connect() as connection:
            return connection.execute(text(statement), params).scalar()

    return run


MAX_PAGE_SIZE = 100


def _list_page(api_url: str, params: list[tuple[str, Any]], page: int) -> dict[str, Any]:
    query = [*params, ("page", page), ("page_size", MAX_PAGE_SIZE)]
    response = httpx.get(f"{api_url}/investigations", params=query, timeout=API_TIMEOUT_S)
    assert response.status_code == httpx.codes.OK, response.text
    return dict(response.json())


@pytest.fixture(scope="session")
def listed(stack: str) -> Callable[[Mapping[str, Any]], list[str]]:
    """Sorted acronyms of every page of `GET /investigations` for the given query."""

    def acronyms(params: Mapping[str, Any]) -> list[str]:
        pairs = list(params.items())
        found: list[str] = []
        page = 1
        while True:
            body = _list_page(stack, pairs, page)
            found += [item["acronym"] for item in body["items"]]
            if len(found) >= body["total"] or not body["items"]:
                return sorted(found)
            page += 1

    return acronyms


@pytest.fixture(scope="session")
def queried(sql: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[str]]:
    """Sorted acronyms of investigations (alias `i`) matching a SQL condition."""

    def acronyms(where: str, **params: Any) -> list[str]:
        statement = f"SELECT acronym FROM investigation i WHERE {where} ORDER BY acronym"  # noqa: S608
        return [row["acronym"] for row in sql(statement, **params)]

    return acronyms


@pytest.fixture(scope="session")
def lineage(stack: str) -> dict[str, Any]:
    """`GET /hardware`: the FR-12 lineage graph."""
    response = httpx.get(f"{stack}/hardware", timeout=API_TIMEOUT_S)
    assert response.status_code == httpx.codes.OK, response.text
    return dict(response.json())


@pytest.fixture(scope="session")
def lineage_edges(lineage: dict[str, Any]) -> Callable[..., set[tuple[str, str]]]:
    """`(source, target)` pairs of the lineage graph, optionally for one edge role."""

    def edges(role: str | None = None) -> set[tuple[str, str]]:
        chosen = [edge for edge in lineage["edges"] if role is None or edge["role"] == role]
        return {(edge["source"], edge["target"]) for edge in chosen}

    return edges


# --- documents and data files --------------------------------------------------------------


# `doc_section` and `doc_table` are shared with the end-to-end suite in `tests/conftest.py`.


@pytest.fixture(scope="session")
def code_names() -> Callable[[str], list[str]]:
    """Backticked names in a line of document text, in order."""

    def names(line: str) -> list[str]:
        return re.findall(r"`([^`]+)`", line)

    return names


DOC_08 = "08-scoring-and-scenario.md"
LENSES = ("habitat", "modeling", "controls")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
CRITERION_WEIGHT = re.compile(r"`(\w+)` (\d+(?:\.\d+)?)")


@pytest.fixture(scope="session")
def rubric_criteria(
    doc_table: Callable[[str, str], list[dict[str, str]]],
) -> dict[str, dict[str, float]]:
    """Document 08 section 1: criterion IDs and default weights per lens."""
    tables = {lens: doc_table(DOC_08, f"### Lens `{lens}`") for lens in LENSES}
    return {
        lens: {row["Criterion ID"].strip("`"): float(row["Default weight"]) for row in rows}
        for lens, rows in tables.items()
    }


def _preset_criterion_weights(
    emphasis: str, rubric_criteria: dict[str, dict[str, float]]
) -> dict[str, dict[str, float]]:
    lens_of = {criterion: lens for lens, ids in rubric_criteria.items() for criterion in ids}
    weights: dict[str, dict[str, float]] = {}
    for criterion, weight in CRITERION_WEIGHT.findall(emphasis):
        weights.setdefault(lens_of[criterion], {})[criterion] = float(weight)
    return weights


@pytest.fixture(scope="session")
def ranking_presets(
    doc_table: Callable[[str, str], list[dict[str, str]]],
    rubric_criteria: dict[str, dict[str, float]],
) -> dict[str, dict[str, Any]]:
    """Document 08 section 3: lens weights and criterion emphasis of every ranking preset."""
    return {
        row["Preset"].strip("`"): {
            "lens_weights": dict(
                zip(LENSES, map(float, NUMBER.findall(row["Lens weights"])), strict=True)
            ),
            "criterion_weights": _preset_criterion_weights(
                row["Criterion emphasis"], rubric_criteria
            ),
        }
        for row in doc_table(DOC_08, "## 3. Ranking presets")
    }


@pytest.fixture(scope="session")
def seed_records() -> dict[str, dict[str, Any]]:
    """Seed files keyed by acronym (document 06 section 5)."""
    records = {}
    for path in sorted(SEED_INVESTIGATIONS_DIR.glob("*.yaml")):
        records[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return records


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rubric_file() -> dict[str, Any]:
    return dict(_load_yaml(DATA_DIR / "rubric.yaml"))


@pytest.fixture(scope="session")
def presets_file() -> dict[str, Any]:
    return dict(_load_yaml(DATA_DIR / "presets.yaml"))


@pytest.fixture(scope="session")
def hardware_file() -> dict[str, Any]:
    return dict(_load_yaml(DATA_DIR / "seed" / "hardware.yaml"))


@pytest.fixture(scope="session")
def earth_file() -> dict[str, Any]:
    return dict(_load_yaml(DATA_DIR / "seed" / "earth_applications.yaml"))


# --- response helpers ----------------------------------------------------------------------


@pytest.fixture(scope="session")
def assert_error_envelope() -> Callable[[httpx.Response, int, str], dict[str, Any]]:
    """Document 05 section 2: `{"error": {code, message, details, request_id}}`."""

    def check(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
        assert response.status_code == status, response.text
        error = response.json()["error"]
        assert set(error) == {"code", "message", "details", "request_id"}
        assert (error["code"], error["request_id"]) == (code, response.headers["x-request-id"])
        assert error["message"]
        return dict(error)

    return check


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: dict[str, Any]


def parse_sse(body: str) -> list[SseEvent]:
    """Split a `text/event-stream` body into `event:` / `data:` frames."""
    events = []
    for frame in body.replace("\r\n", "\n").split("\n\n"):
        fields: dict[str, list[str]] = {}
        for line in frame.splitlines():
            name, _, value = line.partition(":")
            fields.setdefault(name, []).append(value.removeprefix(" "))
        if "event" in fields:
            events.append(SseEvent(fields["event"][0], json.loads("\n".join(fields["data"]))))
    return events


@pytest.fixture(scope="session")
def sse_events() -> Callable[[str], list[SseEvent]]:
    return parse_sse


@pytest.fixture(scope="session")
def source_ref_is_valid() -> Callable[[Mapping[str, Any]], bool]:
    """A `SourceRef` has the required `kind` and `uri` (document 04 section 3)."""
    kinds = {"psi_page", "document", "publication", "s3_object", "curated"}

    def valid(source: Mapping[str, Any]) -> bool:
        return source.get("kind") in kinds and bool(source.get("uri"))

    return valid


# The seed set has no test runs yet (doc 01 OI-06), so the matching path is exercised with
# clearly labelled fixture runs that exist only for the duration of one test.
FIXTURE_SOURCE = json.dumps(
    {
        "kind": "curated",
        "uri": "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/",
        "title": "Integration test fixture run (not catalog data)",
    }
)
FIXTURE_RUNS = (
    {"label": "fixture-cabin", "o2": 0.21, "kpa": 101.3, "flow": 10.0, "g": 0.0},
    {"label": "fixture-enriched", "o2": 0.40, "kpa": 50.0, "flow": 5.0, "g": 1.0},
)
INSERT_RUN = (
    "INSERT INTO test_run (investigation_id, label, source, confidence) "
    "VALUES (:investigation, :label, CAST(:source AS jsonb), 1) RETURNING id"
)
INSERT_CONDITION = (
    "INSERT INTO condition (test_run_id, o2_fraction, pressure_kpa, flow_speed_cm_s, "
    "gravity_g, source) VALUES (:run, :o2, :kpa, :flow, :g, CAST(:source AS jsonb))"
)


@pytest.fixture
def fixture_runs(stack: str, db: Engine) -> Iterator[list[int]]:
    """Two labelled runs on the first seeded investigation; removed after the test."""
    with db.begin() as connection:
        investigation = connection.execute(
            text("SELECT id FROM investigation ORDER BY acronym LIMIT 1")
        ).scalar_one()
        ids = [_insert_fixture_run(connection, investigation, run) for run in FIXTURE_RUNS]
    yield ids
    with db.begin() as connection:
        connection.execute(text("DELETE FROM test_run WHERE id = ANY(:ids)"), {"ids": ids})


def _insert_fixture_run(connection: Any, investigation: int, run: Mapping[str, Any]) -> int:
    params = {"investigation": investigation, "label": run["label"], "source": FIXTURE_SOURCE}
    run_id = int(connection.execute(text(INSERT_RUN), params).scalar_one())
    values = {key: run[key] for key in ("o2", "kpa", "flow", "g")}
    connection.execute(text(INSERT_CONDITION), {"run": run_id, "source": FIXTURE_SOURCE, **values})
    return run_id
