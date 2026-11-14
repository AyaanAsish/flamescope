"""`Pipeline`: stage ordering, one transaction per investigation, `ingest_run` audit rows."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cached_property
from typing import Any, Literal

import structlog
from pydantic import ValidationError as SchemaValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.config import Settings, get_settings
from flamescope_common.errors import FlameScopeError, IngestError, LLMError, NotFoundError
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.models import IngestRun, Investigation
from flamescope_common.rubric import Rubric
from flamescope_common.schemas.card import SeedInvestigation
from flamescope_ingest.discover import (
    Discoverer,
    RawLayout,
    build_s3_client,
    list_discovered_acronyms,
    load_manifest,
    read_json,
    write_json,
)
from flamescope_ingest.embedder import Embedder, TextEmbedder, parsed_sections, seed_sections
from flamescope_ingest.extract_stage import REPORT_KEY, ExtractStage
from flamescope_ingest.harvester import Harvester
from flamescope_ingest.linker import CrossrefResolver, DoiResolver, Linker
from flamescope_ingest.loader import Loader
from flamescope_ingest.normalizer import Normalizer
from flamescope_ingest.overrides import OverrideResult, apply_override, deep_merge, load_override
from flamescope_ingest.parser import Parser, load_parsed_docs
from flamescope_ingest.review import (
    EarthCandidateWriter,
    ReviewFacts,
    ReviewItem,
    candidate_items,
    earth_findings,
    known_applications,
    review_record,
)
from flamescope_ingest.score_stage import (
    MAX_EXCERPTS,
    ORIGIN_LLM,
    ORIGIN_OVERRIDE,
    ScoreRequest,
    ScoreStage,
)
from flamescope_ingest.seed import (
    has_seed,
    list_seed_acronyms,
    load_earth_applications,
    load_fuel_taxonomy,
    load_hardware_catalog,
    load_s3_map,
    load_seed_mapping,
    select_acronyms,
)

logger = structlog.get_logger(__name__)

Mode = Literal["seed", "harvest"]
STAGE_ORDER = (
    "discover",
    "harvest",
    "parse",
    "extract",
    "normalize",
    "link",
    "score",
    "index",
    "review",
)
SEED_STAGES = ("normalize", "link", "score", "index", "review")
STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"
RECOVERABLE_ERRORS = (FlameScopeError, SchemaValidationError, OSError, ValueError, KeyError)


@dataclass
class InvestigationRun:
    """State shared by the stages of one investigation within one pipeline run."""

    acronym: str
    mode: Mode
    stages: list[str]
    force: bool
    session: Session | None = None
    record: SeedInvestigation | None = None
    overrides: OverrideResult = field(default_factory=lambda: OverrideResult(data={}))
    draft: dict[str, Any] | None = None
    completed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)
    quote_failures: list[str] = field(default_factory=list)
    review_items: list[ReviewItem] = field(default_factory=list)
    llm_calls: int = 0
    status: str = STATUS_OK

    @property
    def db(self) -> Session:
        if self.session is None:
            raise IngestError("No database session is open", {"acronym": self.acronym})
        return self.session


@dataclass(frozen=True)
class PipelineOptions:
    """Optional collaborators: the S3 client (harvest) and the DOI resolver (harvest linking)."""

    s3_client_factory: Callable[[], Any] | None = None
    doi_resolver: DoiResolver | None = None


@dataclass
class PipelineResult:
    """Outcome of `Pipeline.run`: overall status and one run per investigation."""

    status: str = STATUS_OK
    runs: list[InvestigationRun] = field(default_factory=list)

    def add(self, run: InvestigationRun) -> None:
        self.runs.append(run)
        if STATUS_FAILED in {run.status, self.status}:
            self.status = STATUS_FAILED
        elif run.status == STATUS_PARTIAL:
            self.status = STATUS_PARTIAL


def _ordered(stages: Sequence[str]) -> list[str]:
    unknown = [stage for stage in stages if stage not in STAGE_ORDER]
    if unknown:
        raise NotFoundError(
            f"Unknown stage(s): {', '.join(unknown)}", {"known": list(STAGE_ORDER)}
        )
    return [stage for stage in STAGE_ORDER if stage in stages]


class Pipeline:
    """Runs ingestion stages per investigation; dependencies are injected."""

    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        orchestrator: AgentOrchestrator,
        embedder: TextEmbedder,
        options: PipelineOptions | None = None,
    ) -> None:
        options = options or PipelineOptions()
        self._settings = settings
        self._session_factory = session_factory
        self._orchestrator = orchestrator
        self._s3_client_factory = options.s3_client_factory or (lambda: build_s3_client(settings))
        self._layout = RawLayout(settings.raw_dir)
        self._catalog = load_hardware_catalog(settings.data_dir)
        self._normalizer = Normalizer(load_fuel_taxonomy(settings.data_dir))
        self._scorer = ScoreStage(orchestrator, Rubric.load(settings.data_dir / "rubric.yaml"))
        self._embedder = Embedder(embedder)
        self._linkers = {
            "seed": Linker(self._catalog),
            "harvest": Linker(self._catalog, options.doi_resolver or CrossrefResolver()),
        }
        self._handlers: dict[str, Callable[[InvestigationRun], None]] = {
            "harvest": self._stage_harvest,
            "parse": self._stage_parse,
            "extract": self._stage_extract,
            "normalize": self._stage_normalize,
            "link": self._stage_link,
            "score": self._stage_score,
            "index": self._stage_index,
            "review": self._stage_review,
        }

    # --- public ------------------------------------------------------------------------

    def run(
        self,
        investigation_ids: Sequence[str],
        stages: Sequence[str],
        *,
        mode: Mode | None = None,
        force: bool = False,
    ) -> PipelineResult:
        """Run `stages` for each investigation; stop only on a database failure."""
        ordered = _ordered(stages)
        if "discover" in ordered:
            self.discover(force=force)
            ordered.remove("discover")
        result = PipelineResult()
        for acronym in self._acronyms(investigation_ids, mode):
            run = self._run_investigation(acronym, ordered, mode or self._mode_of(acronym), force)
            result.add(run)
            if run.status == STATUS_FAILED:
                break
        if mode == "seed" and "link" in ordered and result.status != STATUS_FAILED:
            self.load_earth_applications()
        return result

    def discover(self, *, force: bool = False) -> list[str]:
        manifests = self._discoverer.discover(force=force)
        return [manifest.acronym for manifest in manifests]

    def load_earth_applications(self) -> None:
        """Seed `earth_applications.yaml` once per run; links to absent acronyms are logged."""
        catalog = load_earth_applications(self._settings.data_dir)
        with self._session_factory() as session:
            missing = Loader(session).upsert_earth_applications(catalog)
            session.commit()
        if missing:
            logger.warning(
                "earth_application_unknown_investigations", acronyms=sorted(set(missing))
            )

    def last_runs(self) -> list[IngestRun]:
        """Latest `ingest_run` per investigation (document 06 `status`)."""
        acronym = IngestRun.report["acronym"].astext
        statement = (
            select(IngestRun)
            .distinct(acronym)
            .order_by(acronym, IngestRun.started_at.desc(), IngestRun.id.desc())
        )
        with self._session_factory() as session:
            return list(session.scalars(statement))

    # --- wiring ------------------------------------------------------------------------

    @cached_property
    def _s3_client(self) -> Any:
        return self._s3_client_factory()

    @cached_property
    def _discoverer(self) -> Discoverer:
        s3_map = load_s3_map(self._settings.data_dir)
        return Discoverer(self._settings, self._s3_client, self._layout, s3_map)

    @cached_property
    def _harvester(self) -> Harvester:
        return Harvester(self._settings, self._s3_client, self._layout)

    @cached_property
    def _parser(self) -> Parser:
        return Parser(self._settings, self._layout)

    @cached_property
    def _extractor(self) -> ExtractStage:
        return ExtractStage(self._settings, self._orchestrator, self._layout)

    @cached_property
    def _earth_candidates(self) -> EarthCandidateWriter:
        known = known_applications(load_earth_applications(self._settings.data_dir))
        return EarthCandidateWriter(self._orchestrator, self._layout, known)

    def _mode_of(self, acronym: str) -> Mode:
        return "seed" if has_seed(self._settings.data_dir, acronym) else "harvest"

    def _acronyms(self, requested: Sequence[str], mode: Mode | None) -> list[str]:
        """The requested investigations (validated), or every one available for the mode."""
        return select_acronyms(self._available_acronyms(mode), requested)

    def _available_acronyms(self, mode: Mode | None) -> list[str]:
        if mode == "seed":
            return list_seed_acronyms(self._settings.data_dir)
        if mode == "harvest":
            return list_discovered_acronyms(self._layout)
        with self._session_factory() as session:
            return list(
                session.scalars(select(Investigation.acronym).order_by(Investigation.acronym))
            )

    # --- one investigation -------------------------------------------------------------

    def _run_investigation(
        self, acronym: str, stages: list[str], mode: Mode, force: bool
    ) -> InvestigationRun:
        run = InvestigationRun(acronym=acronym, mode=mode, stages=list(stages), force=force)
        started = datetime.now(UTC)
        try:
            with self._session_factory() as session:
                run.session = session
                for stage in stages:
                    self._handlers[stage](run)
                    run.completed.append(stage)
                session.commit()
        except SQLAlchemyError as error:
            logger.error("ingest_database_error", acronym=acronym, error=str(error))
            run.errors.append(f"database: {error}")
            run.status = STATUS_FAILED
        except RECOVERABLE_ERRORS as error:
            logger.warning("ingest_stage_failed", acronym=acronym, error=str(error))
            run.errors.append(f"{type(error).__name__}: {error}")
        run.status = self._final_status(run)
        self._audit(run, started)
        return run

    @staticmethod
    def _final_status(run: InvestigationRun) -> str:
        if run.status == STATUS_FAILED:
            return STATUS_FAILED
        return STATUS_PARTIAL if run.errors else STATUS_OK

    def _audit(self, run: InvestigationRun, started: datetime) -> None:
        """Write the `ingest_run` row in its own transaction so failures are recorded too."""
        report = {
            **run.report,
            "acronym": run.acronym,
            "completed_stages": run.completed,
            "errors": run.errors,
            "llm_calls": run.llm_calls,
            "overridden_fields": sorted(run.overrides.paths),
            "review": [item.model_dump() for item in run.review_items],
        }
        try:
            with self._session_factory() as session:
                session.add(
                    IngestRun(
                        investigation_id=Loader(session).investigation_id(run.acronym),
                        mode=run.mode,
                        stages=run.stages,
                        status=run.status,
                        started_at=started,
                        finished_at=datetime.now(UTC),
                        report=report,
                    )
                )
                session.commit()
        except SQLAlchemyError as error:
            logger.error("ingest_run_not_recorded", acronym=run.acronym, error=str(error))
            run.status = STATUS_FAILED

    # --- stages 2 to 4 (harvest mode) --------------------------------------------------

    def _stage_harvest(self, run: InvestigationRun) -> None:
        manifest = load_manifest(self._layout, run.acronym)
        result = self._harvester.harvest(manifest, force=run.force)
        run.report["harvest"] = {
            "downloaded": len(result.downloaded),
            "unchanged": len(result.unchanged),
            "skipped": [item.model_dump() for item in result.skipped],
            "failed": [item.model_dump() for item in result.failed],
        }
        run.errors += [f"harvest {item.key}: {item.reason}" for item in result.failed]

    def _stage_parse(self, run: InvestigationRun) -> None:
        result = self._parser.parse(run.acronym, force=run.force)
        run.report["parse"] = result.model_dump()
        run.errors += [f"parse {name}" for name in result.failed]

    def _stage_extract(self, run: InvestigationRun) -> None:
        result = self._extractor.extract(run.acronym, force=run.force)
        run.draft = result.card
        run.llm_calls += result.llm_calls
        run.quote_failures = result.quote_failures
        run.report["extract"] = {
            "skipped": result.skipped,
            "quote_failures": result.quote_failures,
        }

    # --- stage 5 -----------------------------------------------------------------------

    def _raw_card(self, run: InvestigationRun) -> dict[str, Any]:
        if run.mode == "seed":
            return load_seed_mapping(self._settings.data_dir, run.acronym)
        if run.draft is not None:
            return run.draft
        for path in (self._layout.draft_path(run.acronym), self._layout.card_path(run.acronym)):
            if path.is_file():
                return dict(read_json(path))
        raise IngestError(f"No extracted card for {run.acronym}; run extract first")

    def _stage_normalize(self, run: InvestigationRun) -> None:
        raw = self._raw_card(run)
        merged = apply_override(raw, self._settings.data_dir, run.acronym)
        normalized = self._normalizer.normalize(merged.data)
        record = self._reapply_overrides(normalized.record, run.acronym)
        run.record, run.overrides = record, merged
        run.quote_failures = run.quote_failures or raw.get(REPORT_KEY, {}).get(
            "quote_failures", []
        )
        run.report["normalize"] = {
            "dropped_tags": normalized.notes.dropped_tags,
            "renamed_fuels": normalized.notes.renamed_fuels,
            "aggregate_runs": normalized.notes.aggregate_runs,
        }
        self._write_card_artifact(run.acronym, record)

    def _reapply_overrides(self, record: SeedInvestigation, acronym: str) -> SeedInvestigation:
        """Overrides win over normalization too (document 06 stages diagram)."""
        patch = load_override(self._settings.data_dir, acronym)
        if not patch:
            return record
        merged = deep_merge(record.model_dump(mode="json"), patch)
        return SeedInvestigation.model_validate(merged.data)

    def _write_card_artifact(self, acronym: str, record: SeedInvestigation) -> None:
        try:
            write_json(self._layout.card_path(acronym), record.model_dump(mode="json"))
        except OSError as error:
            logger.warning("card_artifact_not_written", acronym=acronym, error=str(error))

    def _record(self, run: InvestigationRun) -> SeedInvestigation:
        if run.record is None:
            self._stage_normalize(run)
        if run.record is None:
            raise IngestError(f"No card for {run.acronym}")
        return run.record

    # --- stages 6 to 9 -----------------------------------------------------------------

    def _investigation_id(self, run: InvestigationRun) -> int:
        investigation_id = Loader(run.db).investigation_id(run.acronym)
        if investigation_id is None:
            raise IngestError(f"{run.acronym} is not loaded; run the link stage first")
        return investigation_id

    def _stage_link(self, run: InvestigationRun) -> None:
        record = self._record(run)
        loader = Loader(run.db)
        loader.upsert_catalog(self._catalog)
        linked = self._linkers[run.mode].link(record)
        has_manifest = self._layout.manifest_path(run.acronym).is_file()
        manifest_ref = self._layout.manifest_ref(run.acronym) if has_manifest else None
        _, counts = loader.upsert_investigation(linked.record, manifest_ref)
        run.record = linked.record
        run.report["link"] = {
            **counts.model_dump(),
            "unknown_hardware": linked.unknown_hardware,
            "unresolved_dois": linked.unresolved_dois,
        }

    def _stage_score(self, run: InvestigationRun) -> None:
        record = self._record(run)
        loader = Loader(run.db)
        investigation_id = self._investigation_id(run)
        version = self._scorer.rubric_version
        outcome = self._scorer.score(
            record,
            ScoreRequest(
                overrides=run.overrides,
                scored_lenses=loader.scored_lenses(
                    investigation_id, version, (ORIGIN_LLM, ORIGIN_OVERRIDE)
                ),
                excerpts=loader.chunk_excerpts(investigation_id, MAX_EXCERPTS),
                force=run.force,
            ),
        )
        written = loader.upsert_scores(investigation_id, outcome.rows)
        run.llm_calls += outcome.llm_calls
        run.errors += outcome.errors
        run.report["score"] = {
            "rows": written,
            "rubric_version": version,
            "prompt_version": self._scorer.prompt_version,
            "skipped_lenses": outcome.skipped_lenses,
            "unknown_criteria": outcome.unknown_criteria,
        }

    def _stage_index(self, run: InvestigationRun) -> None:
        record = self._record(run)
        loader = Loader(run.db)
        investigation_id = self._investigation_id(run)
        documents = load_parsed_docs(self._layout, run.acronym) if run.mode == "harvest" else []
        sections = parsed_sections(documents) if documents else seed_sections(record)
        drafts = self._embedder.build_chunks(sections)
        stored = {} if run.force else loader.embedded_chunk_texts(investigation_id)
        try:
            embedded = self._embedder.embed_stale(drafts, stored, force=run.force)
        except LLMError as error:
            run.errors.append(f"embedding: {error.message}")
            run.report["index"] = {"chunks": 0, "skipped": True}
            return
        run.report["index"] = {"chunks": loader.sync_chunks(investigation_id, embedded)}

    def _stage_review(self, run: InvestigationRun) -> None:
        record = self._record(run)
        investigation_id = self._investigation_id(run)
        facts = ReviewFacts(
            run_count=len(record.runs),
            null_scores=Loader(run.db).null_score_keys(investigation_id),
            quote_failures=run.quote_failures,
        )
        run.review_items = review_record(record, facts)
        if run.mode == "harvest":
            self._propose_earth_applications(run, investigation_id)

    def _propose_earth_applications(self, run: InvestigationRun, investigation_id: int) -> None:
        findings = earth_findings(run.acronym, Loader(run.db).findings(investigation_id))
        outcome = self._earth_candidates.propose(run.acronym, findings, force=run.force)
        run.llm_calls += outcome.llm_calls
        run.errors += outcome.errors
        run.review_items += candidate_items(run.acronym, outcome.candidates)


def build_pipeline(settings: Settings | None = None) -> Pipeline:
    """Production wiring: database sessions, the gateway for embeddings, the orchestrator."""
    from flamescope_common.db import SessionLocal

    resolved = settings or get_settings()
    gateway = LLMGateway(resolved)
    orchestrator = AgentOrchestrator(gateway, resolved)
    return Pipeline(resolved, SessionLocal, orchestrator, gateway)
