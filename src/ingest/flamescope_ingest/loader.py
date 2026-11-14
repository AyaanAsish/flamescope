"""Idempotent upserts for every catalog table (document 06; document 04 section 6)."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from flamescope_common.errors import IngestError
from flamescope_common.models import (
    Chunk,
    Condition,
    EarthApplication,
    EarthApplicationInvestigation,
    Finding,
    Fuel,
    Hardware,
    Investigation,
    InvestigationHardware,
    Measurement,
    Project,
    Publication,
    RelevanceScore,
    TestRun,
)
from flamescope_common.schemas.card import SeedInvestigation, SeedRun
from flamescope_common.sources import SourceRef
from flamescope_ingest.embedder import ChunkDraft, ChunkKey
from flamescope_ingest.normalizer import card_json, derive_columns, to_decimal
from flamescope_ingest.score_stage import ChunkExcerpt, ScoreRow
from flamescope_ingest.seed import CONDITION_COLUMNS, EarthApplicationCatalog, HardwareCatalog


class LoadCounts(BaseModel):
    """Rows written for one investigation, for the ingest report."""

    runs: int = 0
    measurements: int = 0
    findings: int = 0
    publications: int = 0
    hardware_links: int = 0
    card_version: int = 1
    card_changed: bool = False


def source_json(source: SourceRef) -> dict[str, Any]:
    return source.model_dump(mode="json", exclude_none=True)


def _index_by_key[Row, Key: Hashable](
    items: Iterable[Row], key_of: Callable[[Row], Key], what: str
) -> dict[Key, Row]:
    indexed: dict[Key, Row] = {}
    for item in items:
        key = key_of(item)
        if key in indexed:
            raise IngestError(f"Duplicate {what} key {key!r}", {"key": str(key)})
        indexed[key] = item
    return indexed


def _assign(row: Any, values: dict[str, Any]) -> bool:
    """Set only changed attributes; True when anything changed."""
    changed = False
    for column, value in values.items():
        if getattr(row, column) != value:
            setattr(row, column, value)
            changed = True
    return changed


class Loader:
    """Writes catalog rows through one session; the caller owns the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- shared helpers ----------------------------------------------------------------

    def _upsert(self, model: Any, lookup: dict[str, Any], values: dict[str, Any]) -> Any:
        row = self._session.scalar(select(model).filter_by(**lookup))
        if row is None:
            row = model(**lookup, **values)
            self._session.add(row)
        else:
            _assign(row, values)
        return row

    def _sync(
        self,
        model: Any,
        investigation_id: int,
        desired: dict[Hashable, dict[str, Any]],
        key_of: Callable[[Any], Hashable],
    ) -> dict[Hashable, Any]:
        """Update matching rows, insert new ones and delete stale ones for an investigation."""
        existing = {
            key_of(row): row
            for row in self._session.scalars(
                select(model).where(model.investigation_id == investigation_id)
            )
        }
        for key, row in existing.items():
            if key not in desired:
                self._session.delete(row)
        synced: dict[Hashable, Any] = {}
        for key, values in desired.items():
            row = existing.get(key)
            if row is None:
                row = model(investigation_id=investigation_id, **values)
                self._session.add(row)
            else:
                _assign(row, values)
            synced[key] = row
        self._session.flush()
        return synced

    def investigation_id(self, acronym: str) -> int | None:
        return self._session.scalar(
            select(Investigation.id).where(Investigation.acronym == acronym)
        )

    # --- catalog -----------------------------------------------------------------------

    def upsert_catalog(self, catalog: HardwareCatalog) -> None:
        for project in catalog.projects:
            self._upsert(Project, {"name": project.name}, {"description": project.description})
        for item in catalog.hardware:
            self._upsert(
                Hardware,
                {"name": item.name},
                {"kind": item.kind, "description": item.description},
            )
        self._session.flush()
        self._link_hardware_parents(catalog)

    def _link_hardware_parents(self, catalog: HardwareCatalog) -> None:
        ids = self._hardware_ids()
        for item in catalog.hardware:
            parent_id = ids.get(item.parent) if item.parent else None
            self._upsert(Hardware, {"name": item.name}, {"parent_id": parent_id})

    def _hardware_ids(self) -> dict[str, int]:
        return {
            name: row_id
            for row_id, name in self._session.execute(select(Hardware.id, Hardware.name))
        }

    def upsert_earth_applications(self, catalog: EarthApplicationCatalog) -> list[str]:
        """Upsert applications by title; returns acronyms that matched no investigation."""
        missing: list[str] = []
        for application in catalog.applications:
            row = self._upsert(
                EarthApplication,
                {"title": application.title},
                {
                    "sector": application.sector,
                    "description": application.description,
                    "maturity": application.maturity,
                    "references": [source_json(ref) for ref in application.references],
                },
            )
            self._session.flush()
            missing += self._link_application(row.id, application.investigations)
        return missing

    def _link_application(self, application_id: int, acronyms: Sequence[str]) -> list[str]:
        ids = {acronym: self.investigation_id(acronym) for acronym in acronyms}
        wanted = {value for value in ids.values() if value is not None}
        links = self._session.scalars(
            select(EarthApplicationInvestigation).where(
                EarthApplicationInvestigation.earth_application_id == application_id
            )
        ).all()
        for link in links:
            if link.investigation_id not in wanted:
                self._session.delete(link)
        present = {link.investigation_id for link in links}
        for investigation_id in wanted - present:
            self._session.add(
                EarthApplicationInvestigation(
                    earth_application_id=application_id, investigation_id=investigation_id
                )
            )
        return [acronym for acronym, found in ids.items() if found is None]

    # --- investigation -----------------------------------------------------------------

    def upsert_investigation(
        self, record: SeedInvestigation, file_manifest_ref: str | None = None
    ) -> tuple[Investigation, LoadCounts]:
        """Upsert the investigation row and every child table; `card_version` bumps on change."""
        values = self._investigation_values(record, file_manifest_ref)
        row = self._session.scalar(
            select(Investigation).where(Investigation.acronym == record.acronym)
        )
        if row is None:
            row = Investigation(acronym=record.acronym, card_version=1, **values)
            self._session.add(row)
            changed = True
        else:
            changed = _assign(row, values)
            if changed:
                row.card_version += 1
        self._session.flush()
        counts = self._load_children(row, record)
        counts.card_version = row.card_version
        counts.card_changed = changed
        return row, counts

    def _investigation_values(
        self, record: SeedInvestigation, file_manifest_ref: str | None
    ) -> dict[str, Any]:
        project_id = None
        if record.project:
            project = self._upsert(Project, {"name": record.project}, {})
            self._session.flush()
            project_id = project.id
        return {
            "title": record.title,
            "project_id": project_id,
            "psi_url": record.psi_url,
            "s3_prefix": record.data.s3_prefix,
            "platform": record.platform,
            "gravity_level": record.gravity_level,
            "status": record.status,
            "objectives": [
                item.model_dump(mode="json", exclude_none=True) for item in record.objectives
            ],
            "approach": record.approach.text if record.approach else None,
            "summary": record.summary,
            "fire_safety_tags": list(record.fire_safety_tags),
            "data_volume_bytes": record.data.volume_bytes,
            "file_manifest_ref": file_manifest_ref,
            "card": card_json(record),
            "reviewed": record.reviewed,
            **derive_columns(record),
        }

    def _load_children(self, row: Investigation, record: SeedInvestigation) -> LoadCounts:
        fuel_ids = self._upsert_fuels(record)
        runs = self._sync_runs(row.id, record.runs, fuel_ids)
        measurements = self._sync_measurements(row.id, record)
        findings = self._sync_findings(row.id, record)
        publications = self._sync_publications(row.id, record)
        links = self._sync_hardware_links(row.id, record)
        return LoadCounts(
            runs=runs,
            measurements=measurements,
            findings=findings,
            publications=publications,
            hardware_links=links,
        )

    def _upsert_fuels(self, record: SeedInvestigation) -> dict[str, int]:
        ids: dict[str, int] = {}
        for fuel in record.fuels:
            row = self._upsert(
                Fuel,
                {"name": fuel.name, "phase": fuel.phase},
                {"material_class": fuel.material_class},
            )
            self._session.flush()
            ids[fuel.name] = row.id
        return ids

    def _sync_runs(
        self, investigation_id: int, runs: list[SeedRun], fuel_ids: dict[str, int]
    ) -> int:
        desired: dict[Hashable, dict[str, Any]] = {}
        for run in runs:
            if run.label in desired:
                raise IngestError(f"Duplicate run label {run.label!r}", {"label": run.label})
            desired[run.label] = self._run_values(run, fuel_ids)
        synced = self._sync(TestRun, investigation_id, desired, lambda row: row.label)
        for run in runs:
            self._upsert_condition(synced[run.label].id, run)
        return len(runs)

    @staticmethod
    def _run_values(run: SeedRun, fuel_ids: dict[str, int]) -> dict[str, Any]:
        geometry = run.geometry.model_dump(mode="json") if run.geometry else {}
        return {
            "label": run.label,
            "fuel_id": fuel_ids.get(run.fuel) if run.fuel else None,
            "geometry": geometry,
            "varied_parameters": run.varied_parameters,
            "fixed_parameters": run.fixed_parameters,
            "outcome": run.outcome.model_dump(mode="json"),
            "source": source_json(run.source),
            "confidence": to_decimal(run.confidence),
            "is_aggregate": run.is_aggregate,
        }

    def _upsert_condition(self, test_run_id: int, run: SeedRun) -> None:
        raw = run.condition.model_dump(mode="json")
        values = {
            column: to_decimal(raw[column]) if isinstance(raw[column], float) else raw[column]
            for column in CONDITION_COLUMNS
        }
        values["source"] = source_json(run.source)
        self._upsert(Condition, {"test_run_id": test_run_id}, values)

    def _sync_keyed(
        self,
        model: Any,
        investigation_id: int,
        items: Sequence[Any],
        key_of: Callable[[Any], Hashable],
        values_of: Callable[[Any], dict[str, Any]],
    ) -> int:
        """Sync rows keyed by a natural key of the card item (document 06 stage 6)."""
        desired = {
            key: values_of(item)
            for key, item in _index_by_key(items, key_of, model.__name__).items()
        }
        self._sync(model, investigation_id, desired, lambda row: key_of(row))
        return len(desired)

    def _sync_measurements(self, investigation_id: int, record: SeedInvestigation) -> int:
        return self._sync_keyed(
            Measurement,
            investigation_id,
            record.measurements,
            lambda item: (item.instrument, item.quantity),
            lambda item: {
                **item.model_dump(exclude={"source"}),
                "source": source_json(item.source),
            },
        )

    def _sync_findings(self, investigation_id: int, record: SeedInvestigation) -> int:
        return self._sync_keyed(
            Finding,
            investigation_id,
            record.findings,
            lambda item: item.statement,
            lambda item: {
                **item.model_dump(exclude={"source", "confidence"}),
                "source": source_json(item.source),
                "confidence": to_decimal(item.confidence),
            },
        )

    def _sync_publications(self, investigation_id: int, record: SeedInvestigation) -> int:
        return self._sync_keyed(
            Publication,
            investigation_id,
            record.publications,
            lambda item: item.doi or item.title,
            lambda item: item.model_dump(),
        )

    def _sync_hardware_links(self, investigation_id: int, record: SeedInvestigation) -> int:
        ids = self._hardware_ids()
        wanted = {ids[ref.name]: ref.role for ref in record.hardware if ref.name in ids}
        links = self._session.scalars(
            select(InvestigationHardware).where(
                InvestigationHardware.investigation_id == investigation_id
            )
        ).all()
        for link in links:
            if link.hardware_id not in wanted:
                self._session.delete(link)
            elif link.role != wanted[link.hardware_id]:
                link.role = wanted[link.hardware_id]
        present = {link.hardware_id for link in links}
        for hardware_id, role in wanted.items():
            if hardware_id not in present:
                self._session.add(
                    InvestigationHardware(
                        investigation_id=investigation_id, hardware_id=hardware_id, role=role
                    )
                )
        return len(wanted)

    # --- scores ------------------------------------------------------------------------

    def upsert_scores(self, investigation_id: int, rows: Iterable[ScoreRow]) -> int:
        count = 0
        for score in rows:
            self._upsert(
                RelevanceScore,
                {
                    "investigation_id": investigation_id,
                    "lens": score.lens,
                    "criterion": score.criterion,
                    "rubric_version": score.rubric_version,
                },
                {
                    "value": to_decimal(score.value),
                    "rationale": score.rationale,
                    "evidence": [source_json(item) for item in score.evidence],
                    "origin": score.origin,
                },
            )
            count += 1
        self._session.flush()
        return count

    def scored_lenses(
        self, investigation_id: int, rubric_version: str, origins: Sequence[str]
    ) -> set[str]:
        """Lenses already holding rows of the given origins for this rubric version."""
        return set(
            self._session.scalars(
                select(RelevanceScore.lens)
                .where(
                    RelevanceScore.investigation_id == investigation_id,
                    RelevanceScore.rubric_version == rubric_version,
                    RelevanceScore.origin.in_(origins),
                )
                .distinct()
            )
        )

    def null_score_keys(self, investigation_id: int) -> list[str]:
        """`lens.criterion` of every stored score whose value is null (no evidence)."""
        rows = self._session.execute(
            select(RelevanceScore.lens, RelevanceScore.criterion)
            .where(
                RelevanceScore.investigation_id == investigation_id,
                RelevanceScore.value.is_(None),
            )
            .order_by(RelevanceScore.lens, RelevanceScore.criterion)
        )
        return [f"{lens}.{criterion}" for lens, criterion in rows]

    def findings(self, investigation_id: int) -> list[Finding]:
        """Stored findings of one investigation, by id (input of the Earth candidates step)."""
        return list(
            self._session.scalars(
                select(Finding)
                .where(Finding.investigation_id == investigation_id)
                .order_by(Finding.id)
            )
        )

    # --- chunks ------------------------------------------------------------------------

    def embedded_chunk_texts(self, investigation_id: int) -> dict[ChunkKey, str]:
        """Text of every stored chunk that already has an embedding, by chunk key."""
        rows = self._session.execute(
            select(Chunk.doc_ref, Chunk.char_start, Chunk.char_end, Chunk.text).where(
                Chunk.investigation_id == investigation_id, Chunk.embedding.is_not(None)
            )
        )
        return {(ref, start, end): text for ref, start, end, text in rows}

    def chunk_excerpts(self, investigation_id: int, limit: int) -> list[ChunkExcerpt]:
        rows = self._session.scalars(
            select(Chunk)
            .where(Chunk.investigation_id == investigation_id)
            .order_by(Chunk.id)
            .limit(limit)
        )
        return [
            ChunkExcerpt(
                chunk_id=row.id, text=row.text, source=SourceRef.model_validate(row.source)
            )
            for row in rows
        ]

    def sync_chunks(self, investigation_id: int, drafts: Sequence[ChunkDraft]) -> int:
        """Chunks keep their ids: changed or re-embedded rows update, stale rows are deleted."""
        desired = _index_by_key(drafts, lambda draft: draft.key, "chunk")
        existing = {
            (row.doc_ref, row.char_start, row.char_end): row
            for row in self._session.scalars(
                select(Chunk).where(Chunk.investigation_id == investigation_id)
            )
        }
        for key, row in existing.items():
            if key not in desired:
                self._session.delete(row)
        for key, draft in desired.items():
            self._write_chunk(investigation_id, existing.get(key), draft)
        self._session.flush()
        return len(desired)

    def _write_chunk(self, investigation_id: int, row: Chunk | None, draft: ChunkDraft) -> None:
        values: dict[str, Any] = {
            "doc_title": draft.doc_title,
            "section": draft.section,
            "text": draft.text,
            "source": source_json(draft.source),
        }
        if draft.embedding is not None:
            values["embedding"] = draft.embedding
        if row is None:
            self._session.add(
                Chunk(
                    investigation_id=investigation_id,
                    doc_ref=draft.doc_ref,
                    char_start=draft.char_start,
                    char_end=draft.char_end,
                    **values,
                )
            )
            return
        _assign(row, values)
