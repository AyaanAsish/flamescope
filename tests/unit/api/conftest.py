"""Fixtures for the API unit tests: rubric, presets and record builders (document 12 s1).

Everything here is synthetic and in-process: no database, no network, no LLM. Acronyms
such as `ALPHA` are placeholders, not PSI investigations, so no scientific fact is implied.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flamescope_agents.citation_verifier import CitationVerifier
from flamescope_api import deps
from flamescope_api.main import create_app
from flamescope_api.repositories.runs import RunRecord
from flamescope_api.services.scenario import ScenarioService
from flamescope_common.rubric import Presets, Rubric
from flamescope_common.schemas.api import RangePair

DATA_DIR = Path(__file__).resolve().parents[3] / "src" / "data"
TEST_SOURCE = {"kind": "psi_page", "uri": "https://psi.nasa.gov/test", "locator": "page 1"}

ANALOGUE_ACRONYM = "ANALOGUE"
ANALOGUE_OBJECTIVE = "Analogue objective."

RunFactory = Callable[..., RunRecord]
RowFactory = Callable[..., SimpleNamespace]
ScenarioServiceFactory = Callable[..., ScenarioService]


@pytest.fixture(scope="session")
def rubric() -> Rubric:
    """The binding rubric of document 08 section 1, loaded from the repository."""
    return Rubric.load(DATA_DIR / "rubric.yaml")


@pytest.fixture(scope="session")
def presets() -> Presets:
    """The binding presets of document 08 sections 3 and 4, loaded from the repository."""
    return Presets.load(DATA_DIR / "presets.yaml")


@pytest.fixture
def make_run() -> RunFactory:
    """Build a `RunRecord`; keyword arguments override the neutral defaults."""
    counter = iter(range(1, 10_000))

    def build(**overrides: Any) -> RunRecord:
        defaults: dict[str, Any] = {
            "run_id": next(counter),
            "investigation_id": 1,
            "investigation": "ALPHA",
            "label": "run",
            "source": dict(TEST_SOURCE),
            "confidence": 0.8,
        }
        return RunRecord(**{**defaults, **overrides})

    return build


@pytest.fixture
def make_investigation_row() -> RowFactory:
    """Build an object shaped like `InvestigationRow` (investigation ORM fields + names)."""

    def build(
        acronym: str, identifier: int, card: dict[str, Any] | None = None
    ) -> SimpleNamespace:
        investigation = SimpleNamespace(
            id=identifier,
            acronym=acronym,
            title=f"{acronym} title",
            platform=None,
            gravity_level=None,
            fuel_phases=[],
            summary=None,
            fire_safety_tags=[],
            o2_min=None,
            o2_max=None,
            pressure_min_kpa=None,
            pressure_max_kpa=None,
            flow_min_cm_s=None,
            flow_max_cm_s=None,
            reviewed=False,
            psi_url=None,
            objectives=[],
            card=card or {"acronym": acronym, "title": f"{acronym} title"},
        )
        return SimpleNamespace(investigation=investigation, project=None, hardware=())

    return build


@pytest.fixture
def app(rubric: Rubric, presets: Presets) -> FastAPI:
    """`create_app()` with rubric and presets injected; tests override the services."""
    application = create_app()
    application.dependency_overrides[deps.get_rubric] = lambda: rubric
    application.dependency_overrides[deps.get_presets] = lambda: presets
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """In-process HTTP client; server errors become responses so the envelope is visible."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class FakeScenarioRunRepo:
    """`RunRepo` stand-in: fixed runs and catalog ranges."""

    def __init__(self, runs: list[RunRecord], ranges: dict[str, RangePair]) -> None:
        self._runs = runs
        self._ranges = ranges

    def condition_ranges(self) -> dict[str, RangePair]:
        return dict(self._ranges)

    def query(self, filters: Any = None) -> list[RunRecord]:
        return list(self._runs)


class FakeAnalogueRepo:
    """`InvestigationRepo` stand-in: one `partial_gravity_analogue` investigation."""

    def search(self, filters: Any, page: Any = None) -> SimpleNamespace:
        analogue = SimpleNamespace(
            acronym=ANALOGUE_ACRONYM,
            title="Analogue title",
            summary=None,
            objectives=[{"text": ANALOGUE_OBJECTIVE}],
        )
        return SimpleNamespace(rows=[SimpleNamespace(investigation=analogue)], total=1)


@pytest.fixture
def make_scenario_service(presets: Presets) -> ScenarioServiceFactory:
    """`ScenarioService` over fake repositories, the real presets and the real verifier."""

    def build(
        runs: list[RunRecord], ranges: dict[str, RangePair], orchestrator: Any = None
    ) -> ScenarioService:
        return ScenarioService(
            FakeScenarioRunRepo(runs, ranges),  # type: ignore[arg-type]
            FakeAnalogueRepo(),  # type: ignore[arg-type]
            presets,
            orchestrator,
            CitationVerifier(),
        )

    return build
