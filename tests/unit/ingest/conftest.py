"""Fixtures for the ingestion unit tests (document 06): synthetic cards, layouts and settings.

Every value here is synthetic test input, never a scientific fact about an investigation.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from flamescope_common.config import Settings
from flamescope_ingest.discover import Manifest, ManifestFile, RawLayout
from flamescope_ingest.seed import FuelEntry, FuelTaxonomy

TEST_S3_URI = "s3://nasa-psi/combustion/TEST-1/overview.html"
TEST_PREFIX = "combustion/TEST-1/"
TEST_ACRONYM = "TEST-1"
SECTION_HEADING = re.compile(r"^#{2,3} ", re.MULTILINE)

CardFactory = Callable[..., dict[str, Any]]
ManifestFactory = Callable[[list[tuple[str, int]]], Manifest]


@pytest.fixture(scope="session")
def docs_dir(repo_root: Path) -> Path:
    return repo_root / "docs" / "architecture"


@pytest.fixture(scope="session")
def repo_data_dir(repo_root: Path) -> Path:
    return repo_root / "src" / "data"


@pytest.fixture(scope="session")
def doc_section() -> Callable[[Path, str], str]:
    """Text of the document section whose heading starts with `title` (up to the next one)."""

    def section(path: Path, title: str) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index(title)
        following = SECTION_HEADING.search(text, start + len(title))
        return text[start : following.start() if following else len(text)]

    return section


@pytest.fixture
def source() -> dict[str, str]:
    return {"kind": "s3_object", "uri": TEST_S3_URI}


@pytest.fixture
def make_card(source: dict[str, str]) -> CardFactory:
    """A minimal seed-shaped mapping; keyword arguments replace top-level keys."""

    def build(**overrides: Any) -> dict[str, Any]:
        card: dict[str, Any] = {
            "acronym": TEST_ACRONYM,
            "title": "Synthetic test investigation",
            "psi_url": "https://psi.nasa.gov/physci/repo/test",
            "objectives": [{"text": "Synthetic objective.", "source": dict(source)}],
            "fuels": [],
            "fire_safety_tags": [],
        }
        card.update(overrides)
        return card

    return build


@pytest.fixture
def make_fuel(source: dict[str, str]) -> Callable[..., dict[str, Any]]:
    def build(name: str, phase: str = "solid", **extra: Any) -> dict[str, Any]:
        return {"name": name, "phase": phase, "source": dict(source), **extra}

    return build


@pytest.fixture
def taxonomy() -> FuelTaxonomy:
    return FuelTaxonomy(
        fuels=[
            FuelEntry(name="PMMA", phase="solid", material_class="polymer", aliases=["acrylic"]),
            FuelEntry(name="n-heptane", phase="liquid", material_class="alkane", aliases=["C7"]),
        ]
    )


@pytest.fixture
def raw_layout(tmp_path: Path) -> RawLayout:
    return RawLayout(tmp_path / "raw")


@pytest.fixture
def ingest_settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    (data_dir / "overrides").mkdir(parents=True)
    return Settings(raw_dir=tmp_path / "raw", data_dir=data_dir)


@pytest.fixture
def make_manifest() -> ManifestFactory:
    """A manifest as the discover stage writes it, from (file name, size in bytes) pairs."""

    def build(files: list[tuple[str, int]]) -> Manifest:
        entries = [
            ManifestFile(
                key=f"{TEST_PREFIX}{name}",
                size=size,
                extension=Path(name).suffix.lower(),
                etag=f"etag-{name}",
            )
            for name, size in files
        ]
        return Manifest(
            acronym=TEST_ACRONYM, prefix=TEST_PREFIX, listing_hash="test", files=entries
        )

    return build
