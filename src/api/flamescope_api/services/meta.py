"""`MetaService`: statistics, readiness and component status (document 05 section 3)."""

from __future__ import annotations

from dataclasses import dataclass

from flamescope_api.repositories.investigations import InvestigationRepo
from flamescope_common.config import Settings
from flamescope_common.errors import LLMError
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.rubric import Rubric
from flamescope_common.schemas.api import (
    ComponentStatus,
    ReadyResponse,
    StatsResponse,
    StatusResponse,
)

LLM_PROBE_TEXT = "ping"


@dataclass(frozen=True)
class Readiness:
    """The `/ready` body and whether it is served as 200 or 503."""

    report: ReadyResponse
    is_ready: bool


class MetaService:
    """Corpus statistics and live component status."""

    def __init__(
        self,
        investigations: InvestigationRepo,
        settings: Settings,
        rubric: Rubric,
        gateway: LLMGateway,
    ) -> None:
        self._investigations = investigations
        self._settings = settings
        self._rubric = rubric
        self._gateway = gateway

    def stats(self) -> StatsResponse:
        corpus = self._investigations.stats()
        last_run = self._investigations.last_ingest_run()
        return StatsResponse(
            investigations=corpus.investigations,
            test_runs=corpus.test_runs,
            publications=corpus.publications,
            findings=corpus.findings,
            chunks=corpus.chunks,
            hardware=corpus.hardware,
            fuel_phase_counts=corpus.fuel_phase_counts,
            o2_range=corpus.o2_range,
            pressure_range_kpa=corpus.pressure_range_kpa,
            rubric_version=self._rubric.rubric_version,
            last_ingest=(last_run.finished_at or last_run.started_at) if last_run else None,
            ingest_mode=last_run.mode if last_run else None,  # type: ignore[arg-type]  # why: DB column is str, schema field is a Literal validated at ingest
        )

    def ready(self) -> Readiness:
        """Ready needs a reachable database, applied migrations and at least one investigation."""
        reachable = self._investigations.ping()
        revision = self._investigations.schema_revision() if reachable else None
        count = self._investigations.stats().investigations if revision else 0
        report = ReadyResponse(db=reachable, migrations=revision, investigations=count)
        return Readiness(report=report, is_ready=reachable and revision is not None and count > 0)

    def status(self) -> StatusResponse:
        reachable = self._investigations.ping()
        return StatusResponse(
            components=[
                ComponentStatus(id="C-API", status="up", detail="serving requests"),
                ComponentStatus(
                    id="C-DB",
                    status="up" if reachable else "down",
                    detail="PostgreSQL reachable" if reachable else "PostgreSQL unreachable",
                ),
                self._llm_status(),
                self._ingest_status(reachable),
            ]
        )

    def _llm_status(self) -> ComponentStatus:
        provider = self._settings.llm_provider
        if provider == "mock":
            return ComponentStatus(id="C-LLM", status="mock", provider="mock", model="mock")
        model = self._settings.llm_model
        try:
            self._gateway.embed([LLM_PROBE_TEXT])
        except LLMError as error:
            return ComponentStatus(
                id="C-LLM", status="down", provider=provider, model=model, detail=error.message
            )
        return ComponentStatus(id="C-LLM", status="up", provider=provider, model=model)

    def _ingest_status(self, database_reachable: bool) -> ComponentStatus:
        last_run = self._investigations.last_ingest_run() if database_reachable else None
        if last_run is None:
            return ComponentStatus(id="C-ING", status="idle", detail="no ingest run recorded")
        return ComponentStatus(
            id="C-ING",
            status="idle",
            last_run={
                "mode": last_run.mode,
                "status": last_run.status,
                "started_at": last_run.started_at.isoformat(),
                "finished_at": last_run.finished_at.isoformat() if last_run.finished_at else None,
            },
        )
