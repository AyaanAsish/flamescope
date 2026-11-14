"""NFR-01, FR-13, FR-14: `MetaService` stats, readiness and component status (doc 05 s3).

The repository and the gateway are fakes; no database, network or model is used.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from flamescope_api.services.meta import MetaService
from flamescope_common.config import Settings
from flamescope_common.errors import LLMError
from flamescope_common.rubric import Rubric

pytestmark = pytest.mark.unit

STARTED = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
FINISHED = datetime(2026, 11, 1, 12, 5, tzinfo=UTC)
REVISION = "0001_initial"
SEEDED_INVESTIGATIONS = 24


def _corpus(investigations: int) -> SimpleNamespace:
    return SimpleNamespace(
        investigations=investigations,
        test_runs=40,
        publications=30,
        findings=50,
        chunks=600,
        hardware=12,
        fuel_phase_counts={"gas": 3, "liquid": 5, "solid": 16},
        o2_range=(0.1, 1.0),
        pressure_range_kpa=(29.6, 101.3),
    )


class FakeInvestigationRepo:
    """Stand-in for the health queries of `InvestigationRepo`."""

    def __init__(
        self,
        *,
        reachable: bool = True,
        revision: str | None = REVISION,
        investigations: int = SEEDED_INVESTIGATIONS,
        last_run: SimpleNamespace | None = None,
    ) -> None:
        self._reachable = reachable
        self._revision = revision
        self._investigations = investigations
        self._last_run = last_run

    def ping(self) -> bool:
        return self._reachable

    def schema_revision(self) -> str | None:
        return self._revision

    def stats(self) -> SimpleNamespace:
        return _corpus(self._investigations)

    def last_ingest_run(self) -> SimpleNamespace | None:
        return self._last_run


class FakeGateway:
    def __init__(self, error: LLMError | None = None) -> None:
        self._error = error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._error is not None:
            raise self._error
        return [[1.0] for _ in texts]


def _seed_run(finished_at: datetime | None = FINISHED) -> SimpleNamespace:
    return SimpleNamespace(mode="seed", status="ok", started_at=STARTED, finished_at=finished_at)


def _service(
    rubric: Rubric, repo: FakeInvestigationRepo, provider: str = "mock", gateway: Any = None
) -> MetaService:
    settings = Settings(_env_file=None, llm_provider=provider)  # type: ignore[call-arg]
    return MetaService(repo, settings, rubric, gateway or FakeGateway())  # type: ignore[arg-type]


class TestReady:
    @pytest.mark.parametrize(
        ("repo_state", "expected"),
        [
            ({}, (True, REVISION, SEEDED_INVESTIGATIONS, True)),
            ({"reachable": False}, (False, None, 0, False)),
            ({"revision": None}, (True, None, 0, False)),
            ({"investigations": 0}, (True, REVISION, 0, False)),
        ],
    )
    def test_nfr01_ready_needs_db_migrations_and_investigations(
        self, rubric: Rubric, repo_state: dict[str, Any], expected: tuple[Any, ...]
    ) -> None:
        """NFR-01: ready only with a reachable DB, applied migrations and investigations."""
        readiness = _service(rubric, FakeInvestigationRepo(**repo_state)).ready()
        report = readiness.report
        observed = (report.db, report.migrations, report.investigations, readiness.is_ready)
        assert observed == expected


class TestStats:
    def test_fr14_stats_from_corpus_rubric_and_last_ingest(self, rubric: Rubric) -> None:
        """FR-14: `/meta/stats` counts, ranges, rubric version and last ingest."""
        repo = FakeInvestigationRepo(last_run=_seed_run())
        stats = _service(rubric, repo).stats()
        observed = (
            stats.investigations,
            stats.fuel_phase_counts,
            stats.pressure_range_kpa,
            stats.rubric_version,
            stats.last_ingest,
            stats.ingest_mode,
        )
        assert observed == (
            SEEDED_INVESTIGATIONS,
            {"gas": 3, "liquid": 5, "solid": 16},
            (29.6, 101.3),
            rubric.rubric_version,
            FINISHED,
            "seed",
        )

    def test_fr14_unfinished_ingest_reports_its_start(self, rubric: Rubric) -> None:
        repo = FakeInvestigationRepo(last_run=_seed_run(finished_at=None))
        assert _service(rubric, repo).stats().last_ingest == STARTED

    def test_fr14_no_ingest_run_gives_nulls(self, rubric: Rubric) -> None:
        stats = _service(rubric, FakeInvestigationRepo()).stats()
        assert (stats.last_ingest, stats.ingest_mode) == (None, None)


class TestStatus:
    def test_fr13_component_order_and_mock_llm(self, rubric: Rubric) -> None:
        """FR-13: C-API, C-DB, C-LLM, C-ING; mock mode reports `mock`."""
        components = _service(rubric, FakeInvestigationRepo()).status().components
        observed = [(item.id, item.status, item.provider, item.model) for item in components]
        assert observed == [
            ("C-API", "up", None, None),
            ("C-DB", "up", None, None),
            ("C-LLM", "mock", "mock", "mock"),
            ("C-ING", "idle", None, None),
        ]

    def test_fr13_unreachable_db_is_down_and_skips_ingest_lookup(self, rubric: Rubric) -> None:
        repo = FakeInvestigationRepo(reachable=False, last_run=_seed_run())
        components = _service(rubric, repo).status().components
        observed = (components[1].status, components[1].detail, components[3].last_run)
        assert observed == ("down", "PostgreSQL unreachable", None)

    def test_fr13_ingest_component_reports_last_run(self, rubric: Rubric) -> None:
        repo = FakeInvestigationRepo(last_run=_seed_run())
        ingest = _service(rubric, repo).status().components[3]
        assert ingest.last_run == {
            "mode": "seed",
            "status": "ok",
            "started_at": STARTED.isoformat(),
            "finished_at": FINISHED.isoformat(),
        }

    def test_fr13_ollama_up_when_the_probe_embeds(self, rubric: Rubric) -> None:
        llm = _service(rubric, FakeInvestigationRepo(), "ollama").status().components[2]
        assert (llm.status, llm.provider, llm.model) == ("up", "ollama", "qwen2.5:0.5b")

    def test_fr13_ollama_down_when_the_probe_fails(self, rubric: Rubric) -> None:
        gateway = FakeGateway(LLMError("Ollama unreachable"))
        service = _service(rubric, FakeInvestigationRepo(), "ollama", gateway)
        llm = service.status().components[2]
        assert (llm.status, llm.detail) == ("down", "Ollama unreachable")
