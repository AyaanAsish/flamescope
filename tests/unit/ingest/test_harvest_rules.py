"""NFR-10, FR-01: download rules of stage 2 and the S3 listing of stage 1 (document 06 s3.1-3.2).

Every case uses a fake S3 listing or client; nothing reaches the network.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from flamescope_common.config import Settings
from flamescope_ingest.discover import (
    Discoverer,
    Manifest,
    ManifestFile,
    RawLayout,
    list_discovered_acronyms,
    load_manifest,
)
from flamescope_ingest.harvester import Harvester, plan_downloads
from flamescope_ingest.seed import S3Map, S3Mapping

pytestmark = pytest.mark.unit

ManifestFactory = Callable[[list[tuple[str, int]]], Manifest]
MB = 1024 * 1024
# Document 06 section 3.2 and document 11 section 3 defaults.
TEXT_LIMIT_MB = 5
DOC_LIMIT_MB = 25
TABLE_LIMIT_MB = 5
MAX_TABLES = 20
TOTAL_CAP_MB = 300
TEXT_TYPES = (".html", ".htm", ".txt", ".md", ".json", ".xml")
DOC_TYPES = (".pdf", ".doc", ".docx", ".ppt", ".pptx")
TABLE_TYPES = (".csv", ".tsv", ".xls", ".xlsx")
NEVER_TYPES = (".mp4", ".avi", ".mov", ".jpg", ".png", ".tif", ".zip", ".tar", ".gz", ".bin")


def _selected_names(manifest: Manifest, settings: Settings) -> list[str]:
    return [Path(item.key).name for item in plan_downloads(manifest, settings).selected]


def _skipped_names(manifest: Manifest, settings: Settings) -> list[str]:
    return [Path(item.key).name for item in plan_downloads(manifest, settings).skipped]


@pytest.fixture
def settings() -> Settings:
    return Settings()


def test_defaults_equal_document_06(settings: Settings) -> None:
    """`HARVEST_MAX_DOC_MB` 25, `HARVEST_MAX_TABLE_MB` 5, `HARVEST_MAX_TABLES` 20, total 300."""
    assert settings.harvest_max_doc_mb == DOC_LIMIT_MB
    assert settings.harvest_max_table_mb == TABLE_LIMIT_MB
    assert settings.harvest_max_tables == MAX_TABLES
    assert settings.harvest_max_total_mb == TOTAL_CAP_MB


@pytest.mark.parametrize("extension", TEXT_TYPES)
def test_text_files_up_to_5_mb(
    extension: str, settings: Settings, make_manifest: ManifestFactory
) -> None:
    manifest = make_manifest([(f"small{extension}", MB), (f"big{extension}", 6 * MB)])
    assert _selected_names(manifest, settings) == [f"small{extension}"]
    assert _skipped_names(manifest, settings) == [f"big{extension}"]


@pytest.mark.parametrize("extension", DOC_TYPES)
def test_documents_up_to_doc_limit(
    extension: str, settings: Settings, make_manifest: ManifestFactory
) -> None:
    manifest = make_manifest([(f"ok{extension}", 20 * MB), (f"huge{extension}", 30 * MB)])
    assert _selected_names(manifest, settings) == [f"ok{extension}"]


@pytest.mark.parametrize("extension", TABLE_TYPES)
def test_tables_up_to_table_limit(
    extension: str, settings: Settings, make_manifest: ManifestFactory
) -> None:
    manifest = make_manifest([(f"ok{extension}", 4 * MB), (f"huge{extension}", 6 * MB)])
    assert _selected_names(manifest, settings) == [f"ok{extension}"]


@pytest.mark.parametrize("extension", NEVER_TYPES)
def test_video_images_archives_binaries_never(
    extension: str, settings: Settings, make_manifest: ManifestFactory
) -> None:
    """NFR-10: manifest only, never downloaded, whatever the size."""
    manifest = make_manifest([(f"file{extension}", 1)])
    plan = plan_downloads(manifest, settings)
    assert plan.selected == []
    assert [Path(item.key).name for item in plan.skipped] == [f"file{extension}"]


def test_limits_follow_settings(make_manifest: ManifestFactory) -> None:
    """Limits are configuration (`HARVEST_MAX_DOC_MB`, `HARVEST_MAX_TABLE_MB`)."""
    tight = Settings(harvest_max_doc_mb=1, harvest_max_table_mb=1)
    manifest = make_manifest([("a.pdf", 2 * MB), ("b.csv", 2 * MB), ("c.html", 2 * MB)])
    assert _selected_names(manifest, tight) == ["c.html"]


def test_at_most_max_tables_preferring_summary_and_matrix(
    settings: Settings, make_manifest: ManifestFactory
) -> None:
    """At most `HARVEST_MAX_TABLES` per investigation, preferring summary or test-matrix names."""
    files = [(f"data_{index:02d}.csv", 1000) for index in range(MAX_TABLES + 5)]
    files += [("zz_summary.csv", 1000), ("zz_test_matrix.xlsx", 1000)]
    selected = _selected_names(make_manifest(files), settings)
    assert len(selected) == MAX_TABLES
    assert {"zz_summary.csv", "zz_test_matrix.xlsx"} <= set(selected)


def test_table_cap_does_not_limit_documents(
    settings: Settings, make_manifest: ManifestFactory
) -> None:
    files = [(f"t{index:02d}.csv", 10) for index in range(MAX_TABLES + 1)]
    files += [(f"d{index}.pdf", 10) for index in range(3)]
    selected = _selected_names(make_manifest(files), settings)
    assert sum(name.endswith(".pdf") for name in selected) == 3
    assert sum(name.endswith(".csv") for name in selected) == MAX_TABLES


def test_total_cap_per_investigation(settings: Settings, make_manifest: ManifestFactory) -> None:
    """Total cap `HARVEST_MAX_TOTAL_MB` (300) per investigation; skipped files are listed."""
    files = [(f"report{index:02d}.pdf", 24 * MB) for index in range(15)]
    plan = plan_downloads(make_manifest(files), settings)
    assert sum(item.size for item in plan.selected) <= TOTAL_CAP_MB * MB
    assert len(plan.selected) == (TOTAL_CAP_MB * MB) // (24 * MB)
    assert len(plan.selected) + len(plan.skipped) == len(files)
    assert all(item.reason for item in plan.skipped)


@dataclass
class FakeBody:
    content: bytes

    def read(self) -> bytes:
        return self.content


@dataclass
class FakeS3:
    """In-memory stand-in for the unsigned boto3 client: listing and object reads."""

    objects: dict[str, bytes] = field(default_factory=dict)
    folders: list[str] = field(default_factory=list)
    gets: list[str] = field(default_factory=list)

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803 - boto3 names
        self.gets.append(Key)
        return {"Body": FakeBody(self.objects[Key])}

    def get_paginator(self, operation: str) -> FakeS3:
        assert operation == "list_objects_v2"
        return self

    def paginate(self, Bucket: str, **params: str) -> Iterator[dict[str, Any]]:  # noqa: N803
        prefix = params.get("Prefix", "")
        if params.get("Delimiter") == "/":
            yield {"CommonPrefixes": [{"Prefix": p} for p in self.folders if p.startswith(prefix)]}
            return
        yield {"Contents": [self._entry(key) for key in self.objects if key.startswith(prefix)]}

    def _entry(self, key: str) -> dict[str, Any]:
        return {
            "Key": key,
            "Size": len(self.objects[key]),
            "ETag": f'"{len(self.objects[key])}"',
            "LastModified": datetime(2026, 1, 1, tzinfo=UTC),
        }


def _manifest_with(keys: dict[str, bytes], prefix: str = "combustion/TEST-1/") -> Manifest:
    files = [
        ManifestFile(key=key, size=len(body), extension=Path(key).suffix, etag=f"e{len(body)}")
        for key, body in keys.items()
    ]
    return Manifest(acronym="TEST-1", prefix=prefix, listing_hash="h", files=files)


def test_harvester_downloads_only_planned_files(ingest_settings: Settings) -> None:
    """Artifact `/data/raw/<acr>/raw/*` for allowed files only (document 06 section 2)."""
    objects = {"combustion/TEST-1/overview.html": b"<p>x</p>", "combustion/TEST-1/v.mp4": b"v"}
    client = FakeS3(objects=objects)
    layout = RawLayout(ingest_settings.raw_dir)
    result = Harvester(ingest_settings, client, layout).harvest(_manifest_with(objects))
    assert result.downloaded == ["combustion/TEST-1/overview.html"]
    assert [item.key for item in result.skipped] == ["combustion/TEST-1/v.mp4"]
    assert client.gets == ["combustion/TEST-1/overview.html"]
    assert (layout.raw_dir("TEST-1") / "overview.html").read_bytes() == b"<p>x</p>"


def test_harvester_skips_unchanged_etag_and_force_refetches(ingest_settings: Settings) -> None:
    """Idempotency key: S3 ETag per key; `--force` reruns (document 06 section 2)."""
    objects = {"combustion/TEST-1/notes.txt": b"abc"}
    client = FakeS3(objects=objects)
    harvester = Harvester(ingest_settings, client, RawLayout(ingest_settings.raw_dir))
    manifest = _manifest_with(objects)
    harvester.harvest(manifest)
    assert harvester.harvest(manifest).unchanged == ["combustion/TEST-1/notes.txt"]
    assert harvester.harvest(manifest, force=True).downloaded == ["combustion/TEST-1/notes.txt"]
    assert len(client.gets) == 2


def test_harvester_refuses_key_outside_raw_dir(ingest_settings: Settings) -> None:
    objects = {"combustion/TEST-1/../../escape.txt": b"x"}
    harvester = Harvester(
        ingest_settings, FakeS3(objects=objects), RawLayout(ingest_settings.raw_dir)
    )
    result = harvester.harvest(_manifest_with(objects))
    assert result.downloaded == []
    assert [item.key for item in result.failed] == ["combustion/TEST-1/../../escape.txt"]


def test_discover_uses_folder_names_when_nothing_pinned(ingest_settings: Settings) -> None:
    """No pinned mapping: every folder under `PSI_PREFIX` is one investigation (doc 06 s3.1)."""
    client = FakeS3(
        objects={"A1/doc.pdf": b"12345", "A1/clip.mp4": b"1", "B2/x.html": b"1"},
        folders=["A1/", "B2/"],
    )
    layout = RawLayout(ingest_settings.raw_dir)
    manifests = Discoverer(ingest_settings, client, layout, S3Map()).discover()
    assert [m.acronym for m in manifests] == ["A1", "B2"]
    assert client.gets == [], "discover downloads nothing"
    stored = load_manifest(layout, "A1")
    assert {(f.key, f.size, f.extension) for f in stored.files} == {
        ("A1/doc.pdf", 5, ".pdf"),
        ("A1/clip.mp4", 1, ".mp4"),
    }
    assert list_discovered_acronyms(layout) == ["A1", "B2"]
    index = json.loads(layout.index_path().read_text())
    assert [entry["acronym"] for entry in index["investigations"]] == ["A1", "B2"]


def test_discover_only_pinned_folders_when_any_pinned(ingest_settings: Settings) -> None:
    """When at least one mapping is pinned, only the pinned folders are investigations."""
    client = FakeS3(objects={"f1/a.txt": b"1", "f2/b.txt": b"2"}, folders=["f1/", "f2/"])
    pinned = S3Map(mappings=[S3Mapping(prefix="f2/", acronym="PINNED")])
    discoverer = Discoverer(ingest_settings, client, RawLayout(ingest_settings.raw_dir), pinned)
    assert [m.acronym for m in discoverer.discover()] == ["PINNED"]
