"""Stage 1, discover: list the public bucket and write manifests (document 06 section 3.1).

Nothing is downloaded here. `RawLayout` is the single owner of the `/data/raw` path layout.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import boto3
import structlog
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, Field

from flamescope_common.config import Settings
from flamescope_common.errors import IngestError
from flamescope_ingest.seed import S3Map

logger = structlog.get_logger(__name__)

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5
INDEX_DIR = "_index"
INDEX_FILE = "investigations.json"
MANIFEST_FILE = "manifest.json"
RAW_SUBDIR = "raw"
PARSED_SUBDIR = "parsed"
DRAFT_FILE = "card.draft.json"
CARD_FILE = "card.json"
EARTH_CANDIDATES_FILE = "earth_candidates.json"
JSON_INDENT = 2


class RawLayout:
    """Paths under the raw volume.

    `<root>/<acronym>/{manifest.json, raw/, parsed/, card.draft.json, card.json,
    earth_candidates.json}`.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def index_path(self) -> Path:
        return self.root / INDEX_DIR / INDEX_FILE

    def investigation_dir(self, acronym: str) -> Path:
        return self.root / acronym

    def manifest_path(self, acronym: str) -> Path:
        return self.investigation_dir(acronym) / MANIFEST_FILE

    def raw_dir(self, acronym: str) -> Path:
        return self.investigation_dir(acronym) / RAW_SUBDIR

    def parsed_dir(self, acronym: str) -> Path:
        return self.investigation_dir(acronym) / PARSED_SUBDIR

    def draft_path(self, acronym: str) -> Path:
        return self.investigation_dir(acronym) / DRAFT_FILE

    def card_path(self, acronym: str) -> Path:
        return self.investigation_dir(acronym) / CARD_FILE

    def earth_candidates_path(self, acronym: str) -> Path:
        return self.investigation_dir(acronym) / EARTH_CANDIDATES_FILE

    def manifest_ref(self, acronym: str) -> str:
        """`investigation.file_manifest_ref`: path of the manifest under the raw volume."""
        return f"{acronym}/{MANIFEST_FILE}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=JSON_INDENT, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestFile(BaseModel):
    key: str
    size: int
    extension: str
    etag: str = ""
    last_modified: str | None = None


class Manifest(BaseModel):
    """Keys, sizes, types and modification times of one investigation folder."""

    acronym: str
    prefix: str
    listing_hash: str
    files: list[ManifestFile] = Field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.files)


def call_with_retries[T](call: Callable[[], T], what: str) -> T:
    """Retry S3 calls 3 times with backoff, then raise `IngestError` (document 06 section 6)."""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return call()
        except (ClientError, BotoCoreError) as error:
            logger.warning("s3_call_failed", what=what, attempt=attempt, error=str(error))
            if attempt == RETRY_ATTEMPTS:
                raise IngestError(f"S3 request failed after {attempt} attempts: {what}") from error
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise IngestError(f"S3 request failed: {what}")


def build_s3_client(settings: Settings) -> Any:
    """Unsigned boto3 client for the public bucket; no credentials are read or needed."""
    return boto3.client(
        "s3", region_name=settings.psi_region, config=Config(signature_version=UNSIGNED)
    )


def _listing_hash(files: list[ManifestFile]) -> str:
    digest = hashlib.sha256()
    for item in sorted(files, key=lambda entry: entry.key):
        digest.update(f"{item.key}|{item.etag}\n".encode())
    return digest.hexdigest()


class Discoverer:
    """Lists investigation folders under `PSI_PREFIX` and writes their manifests."""

    def __init__(self, settings: Settings, client: Any, layout: RawLayout, s3_map: S3Map) -> None:
        self._settings = settings
        self._client = client
        self._layout = layout
        self._pinned = {mapping.prefix: mapping.acronym for mapping in s3_map.mappings}

    def discover(self, *, force: bool = False) -> list[Manifest]:
        """Write `manifest.json` per investigation and the index; unchanged listings are kept."""
        manifests = [
            self._manifest_for(prefix, acronym, force) for prefix, acronym in self._folders()
        ]
        write_json(
            self._layout.index_path(),
            {
                "bucket": self._settings.psi_bucket,
                "prefix": self._settings.psi_prefix,
                "investigations": [
                    {
                        "acronym": m.acronym,
                        "prefix": m.prefix,
                        "files": len(m.files),
                        "bytes": m.total_bytes,
                        "listing_hash": m.listing_hash,
                    }
                    for m in manifests
                ],
            },
        )
        return manifests

    def _folders(self) -> list[tuple[str, str]]:
        """(prefix, acronym) pairs: only pinned folders when `s3_map.yaml` pins any."""
        prefixes = [
            common["Prefix"]
            for page in self._pages(Delimiter="/", Prefix=self._settings.psi_prefix)
            for common in page.get("CommonPrefixes", [])
        ]
        if self._pinned:
            return [(p, self._pinned[p]) for p in prefixes if p in self._pinned]
        return [(prefix, prefix.rstrip("/").split("/")[-1]) for prefix in prefixes]

    def _pages(self, **params: str) -> Iterator[dict[str, Any]]:
        paginator = self._client.get_paginator("list_objects_v2")
        pages = call_with_retries(
            lambda: list(paginator.paginate(Bucket=self._settings.psi_bucket, **params)),
            f"list {params.get('Prefix', '')!r}",
        )
        yield from pages

    def _manifest_for(self, prefix: str, acronym: str, force: bool) -> Manifest:
        files = [
            ManifestFile(
                key=entry["Key"],
                size=int(entry["Size"]),
                extension=Path(entry["Key"]).suffix.lower(),
                etag=str(entry.get("ETag", "")).strip('"'),
                last_modified=entry["LastModified"].isoformat()
                if entry.get("LastModified")
                else None,
            )
            for page in self._pages(Prefix=prefix)
            for entry in page.get("Contents", [])
            if not entry["Key"].endswith("/")
        ]
        manifest = Manifest(
            acronym=acronym, prefix=prefix, listing_hash=_listing_hash(files), files=files
        )
        path = self._layout.manifest_path(acronym)
        if force or not self._unchanged(path, manifest):
            write_json(path, manifest.model_dump(mode="json"))
        return manifest

    @staticmethod
    def _unchanged(path: Path, manifest: Manifest) -> bool:
        if not path.is_file():
            return False
        return bool(read_json(path).get("listing_hash") == manifest.listing_hash)


def load_manifest(layout: RawLayout, acronym: str) -> Manifest:
    path = layout.manifest_path(acronym)
    if not path.is_file():
        raise IngestError(
            f"No manifest for {acronym}; run `flamescope-ingest discover` first",
            {"acronym": acronym},
        )
    return Manifest.model_validate(read_json(path))


def list_discovered_acronyms(layout: RawLayout) -> list[str]:
    path = layout.index_path()
    if not path.is_file():
        return []
    return sorted(entry["acronym"] for entry in read_json(path).get("investigations", []))
