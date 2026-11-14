"""Stage 2, harvest: download only the allowed files within limits (document 06 section 3.2).

Video, images, archives and binaries are never downloaded (NFR-10); they stay in the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

from flamescope_common.config import BYTES_PER_MB, Settings
from flamescope_common.errors import IngestError
from flamescope_ingest.discover import (
    Manifest,
    ManifestFile,
    RawLayout,
    call_with_retries,
    read_json,
    write_json,
)

logger = structlog.get_logger(__name__)

TEXT_EXTENSIONS = frozenset({".html", ".htm", ".txt", ".md", ".json", ".xml"})
DOC_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".ppt", ".pptx"})
TABLE_EXTENSIONS = frozenset({".csv", ".tsv", ".xls", ".xlsx"})
TEXT_MAX_BYTES = 5 * BYTES_PER_MB
PREFERRED_TABLE_NAMES = ("summary", "matrix", "overview")
ETAG_FILE = ".etags.json"
RANK_TEXT, RANK_DOC, RANK_TABLE = 0, 1, 2


class SkippedFile(BaseModel):
    key: str
    reason: str


class DownloadPlan(BaseModel):
    selected: list[ManifestFile] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)


class HarvestResult(BaseModel):
    downloaded: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)
    failed: list[SkippedFile] = Field(default_factory=list)


def _rank(extension: str) -> int | None:
    if extension in TEXT_EXTENSIONS:
        return RANK_TEXT
    if extension in DOC_EXTENSIONS:
        return RANK_DOC
    if extension in TABLE_EXTENSIONS:
        return RANK_TABLE
    return None


def _preference(item: ManifestFile) -> tuple[int, int, str]:
    """Order: text, documents, tables; summary or test-matrix tables first."""
    rank = _rank(item.extension)
    name = Path(item.key).name.lower()
    preferred = rank == RANK_TABLE and any(hint in name for hint in PREFERRED_TABLE_NAMES)
    return (rank if rank is not None else RANK_TABLE + 1, 0 if preferred else 1, item.key)


def _size_limit(rank: int, settings: Settings) -> int:
    if rank == RANK_TEXT:
        return TEXT_MAX_BYTES
    if rank == RANK_DOC:
        return settings.harvest_max_doc_bytes
    return settings.harvest_max_table_bytes


def plan_downloads(manifest: Manifest, settings: Settings) -> DownloadPlan:
    """Apply the download rules to a manifest without touching the network."""
    plan = DownloadPlan()
    total = 0
    tables = 0
    for item in sorted(manifest.files, key=_preference):
        rank = _rank(item.extension)
        reason = _rejection(item, rank, settings, tables, total)
        if reason is not None or rank is None:
            plan.skipped.append(SkippedFile(key=item.key, reason=reason or "not downloadable"))
            continue
        plan.selected.append(item)
        total += item.size
        tables += rank == RANK_TABLE
    return plan


def _rejection(
    item: ManifestFile, rank: int | None, settings: Settings, tables: int, total: int
) -> str | None:
    if rank is None:
        return "video, image, archive, binary or unknown type: manifest only"
    if item.size > _size_limit(rank, settings):
        return f"larger than the {item.extension} size limit"
    if rank == RANK_TABLE and tables >= settings.harvest_max_tables:
        return f"more than {settings.harvest_max_tables} tables"
    if total + item.size > settings.harvest_max_total_bytes:
        return f"total cap of {settings.harvest_max_total_mb} MB reached"
    return None


@dataclass
class _HarvestRun:
    """Mutable state of one harvest of one investigation."""

    prefix: str
    raw_dir: Path
    etags: dict[str, str]
    force: bool
    result: HarvestResult


class Harvester:
    """Downloads the planned files into `<raw>/<acronym>/raw/`, skipping unchanged ETags."""

    def __init__(self, settings: Settings, client: Any, layout: RawLayout) -> None:
        self._settings = settings
        self._client = client
        self._layout = layout

    def harvest(self, manifest: Manifest, *, force: bool = False) -> HarvestResult:
        plan = plan_downloads(manifest, self._settings)
        raw_dir = self._layout.raw_dir(manifest.acronym)
        run = _HarvestRun(
            prefix=manifest.prefix,
            raw_dir=raw_dir,
            etags=self._read_etags(raw_dir),
            force=force,
            result=HarvestResult(skipped=plan.skipped),
        )
        for item in plan.selected:
            self._fetch_one(run, item)
        write_json(raw_dir / ETAG_FILE, run.etags)
        return run.result

    def _fetch_one(self, run: _HarvestRun, item: ManifestFile) -> None:
        try:
            target = self._target(run.raw_dir, run.prefix, item.key)
            if not run.force and target.is_file() and run.etags.get(item.key) == item.etag:
                run.result.unchanged.append(item.key)
                return
            self._download(item, target)
        except (IngestError, OSError) as error:
            logger.warning("harvest_file_failed", key=item.key, error=str(error))
            run.result.failed.append(SkippedFile(key=item.key, reason=str(error)))
            return
        run.etags[item.key] = item.etag
        run.result.downloaded.append(item.key)

    @staticmethod
    def _target(raw_dir: Path, prefix: str, key: str) -> Path:
        relative = key.removeprefix(prefix).lstrip("/")
        target = (raw_dir / relative).resolve()
        if not target.is_relative_to(raw_dir.resolve()):
            raise IngestError(f"Refusing a key that leaves the raw directory: {key}")
        return target

    def _download(self, item: ManifestFile, target: Path) -> None:
        response = call_with_retries(
            lambda: self._client.get_object(Bucket=self._settings.psi_bucket, Key=item.key),
            f"get {item.key}",
        )
        body = response["Body"].read()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    @staticmethod
    def _read_etags(raw_dir: Path) -> dict[str, str]:
        path = raw_dir / ETAG_FILE
        return dict(read_json(path)) if path.is_file() else {}
