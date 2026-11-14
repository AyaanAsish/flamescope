"""Database schema equals document 04 (document 12 section 2; document 04 sections 2 and 6).

Requirements: FR-01 (card storage), FR-11 (chunk index for Ask), NFR-01 (migration applies
on deploy), NFR-04 (indexes). Call flows: CF-01 (`alembic upgrade head` in the ingest job),
CF-02 (tables written by seed ingestion).
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(3)]

MIGRATIONS_DIR = Path("src/common/flamescope_common/migrations/versions")
TIMESTAMP_COLUMNS = ("created_at", "updated_at")

# Written from document 04 section 2 (tables and their columns).
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "project": ("id", "name", "description"),
    "hardware": ("id", "name", "kind", "description", "parent_id"),
    "investigation": (
        "id", "acronym", "title", "discipline", "project_id", "psi_url", "s3_prefix",
        "platform", "gravity_level", "years", "status", "objectives", "approach", "summary",
        "fuel_phases", "fire_safety_tags", "o2_min", "o2_max", "pressure_min_kpa",
        "pressure_max_kpa", "flow_min_cm_s", "flow_max_cm_s", "data_volume_bytes",
        "file_manifest_ref", "card", "card_version", "reviewed", "search_tsv",
    ),
    "investigation_hardware": ("investigation_id", "hardware_id", "role"),
    "fuel": ("id", "name", "phase", "material_class"),
    "test_run": (
        "id", "investigation_id", "label", "fuel_id", "geometry", "varied_parameters",
        "fixed_parameters", "outcome", "data_files", "source", "confidence", "is_aggregate",
    ),
    "condition": (
        "test_run_id", "o2_fraction", "diluent", "pressure_kpa", "flow_speed_cm_s",
        "flow_direction", "gravity_g", "e_field_kv", "temperature_k", "source",
    ),
    "measurement": (
        "id", "investigation_id", "instrument", "hardware_id", "quantity", "units",
        "file_pattern", "notes", "source",
    ),
    "publication": (
        "id", "investigation_id", "doi", "title", "authors", "year", "venue", "abstract",
        "url", "key_findings",
    ),
    "finding": ("id", "investigation_id", "statement", "category", "source", "confidence"),
    "earth_application": ("id", "title", "sector", "description", "maturity", "references"),
    "finding_earth_application": ("finding_id", "earth_application_id"),
    "earth_application_investigation": ("earth_application_id", "investigation_id"),
    "relevance_score": (
        "id", "investigation_id", "lens", "criterion", "value", "rationale", "evidence",
        "rubric_version", "origin",
    ),
    "chunk": (
        "id", "investigation_id", "doc_ref", "doc_title", "section", "char_start", "char_end",
        "text", "embedding", "tsv", "source",
    ),
    "ingest_run": (
        "id", "investigation_id", "mode", "stages", "status", "started_at", "finished_at",
        "report",
    ),
    "llm_cache": ("key", "provider", "model", "response"),
}  # fmt: skip

# Column types stated in document 04 section 2 (Postgres `udt_name`).
KEY_COLUMN_TYPES: dict[tuple[str, str], str] = {
    ("investigation", "id"): "int8",
    ("investigation", "card"): "jsonb",
    ("investigation", "card_version"): "int4",
    ("investigation", "fuel_phases"): "_text",
    ("investigation", "fire_safety_tags"): "_text",
    ("investigation", "years"): "int4range",
    ("investigation", "search_tsv"): "tsvector",
    ("investigation", "reviewed"): "bool",
    ("test_run", "source"): "jsonb",
    ("test_run", "is_aggregate"): "bool",
    ("relevance_score", "evidence"): "jsonb",
    ("chunk", "embedding"): "vector",
    ("chunk", "tsv"): "tsvector",
    ("ingest_run", "stages"): "_text",
    ("publication", "authors"): "_text",
}

# Indexes of document 04 section 2: (table, access method, indexed expression fragment).
DOCUMENTED_INDEXES = (
    ("investigation", "gin", "(search_tsv)"),
    ("investigation", "gin", "(fire_safety_tags)"),
    ("investigation", "gin", "(fuel_phases)"),
    ("investigation", "gin", "(acronym gin_trgm_ops)"),
    ("investigation", "gin", "(title gin_trgm_ops)"),
    ("chunk", "hnsw", "(embedding vector_cosine_ops)"),
    ("chunk", "gin", "(tsv)"),
)

UNIQUE_KEYS = (
    ("project", ("name",)),
    ("hardware", ("name",)),
    ("investigation", ("acronym",)),
    ("fuel", ("name", "phase")),
    ("relevance_score", ("investigation_id", "lens", "criterion", "rubric_version")),
)


def _alembic_head(repo_root: Path) -> str:
    """The revision no other revision names as its `down_revision`."""
    revisions: dict[str, str | None] = {}
    for path in (repo_root / MIGRATIONS_DIR).glob("*.py"):
        assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("revision", "down_revision")
        }  # fmt: skip
        revisions[assignments["revision"]] = assignments.get("down_revision")
    heads = set(revisions) - set(revisions.values())
    assert len(heads) == 1, heads
    return heads.pop()


@pytest.fixture(scope="module")
def columns(stack: str, sql: Callable[..., list[dict[str, Any]]]) -> dict[str, dict[str, str]]:
    rows = sql(
        "SELECT table_name, column_name, udt_name FROM information_schema.columns "
        "WHERE table_schema = 'public'"
    )
    by_table: dict[str, dict[str, str]] = {}
    for row in rows:
        by_table.setdefault(row["table_name"], {})[row["column_name"]] = row["udt_name"]
    return by_table


def test_nfr01_alembic_head_applied(
    stack: str, scalar: Callable[..., Any], repo_root: Path
) -> None:
    """CF-01: the migration head (`0001_initial`) is applied."""
    assert scalar("SELECT version_num FROM alembic_version") == _alembic_head(repo_root)


def test_fr11_extensions_installed(stack: str, sql: Callable[..., list[dict[str, Any]]]) -> None:
    """Doc 04 intro: extensions `vector` and `pg_trgm`."""
    names = {row["extname"] for row in sql("SELECT extname FROM pg_extension")}
    assert {"vector", "pg_trgm"} <= names


def test_fr01_no_undocumented_tables(columns: dict[str, dict[str, str]]) -> None:
    """Doc 04 s2 and doc 13 rule 4: the tables are exactly the documented ones."""
    assert set(columns) - {"alembic_version"} == set(TABLE_COLUMNS)


@pytest.mark.parametrize("table", sorted(TABLE_COLUMNS))
def test_fr01_table_has_documented_columns(table: str, columns: dict[str, dict[str, str]]) -> None:
    """Doc 04 s2: every table exists with its key columns and the timestamp columns."""
    expected = {*TABLE_COLUMNS[table], *TIMESTAMP_COLUMNS}
    assert expected - set(columns.get(table, {})) == set()


def test_fr01_key_column_types(columns: dict[str, dict[str, str]]) -> None:
    """Doc 04 s2: key column types (bigint ids, jsonb card, text arrays, tsvector, vector)."""
    actual = {key: columns[key[0]][key[1]] for key in KEY_COLUMN_TYPES}
    assert actual == KEY_COLUMN_TYPES


@pytest.mark.parametrize(("table", "method", "expression"), DOCUMENTED_INDEXES)
def test_nfr04_documented_index_exists(
    table: str, method: str, expression: str, stack: str, sql: Callable[..., list[dict[str, Any]]]
) -> None:
    """Doc 04 s2: GIN on `search_tsv`, tags, phases, trigram; HNSW cosine on `chunk.embedding`."""
    definitions = [
        row["indexdef"]
        for row in sql(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = :table",
            table=table,
        )
    ]
    assert any(f"USING {method} {expression}" in definition for definition in definitions), (
        definitions
    )


@pytest.mark.parametrize(("table", "key"), UNIQUE_KEYS)
def test_fr01_unique_key(
    table: str, key: tuple[str, ...], stack: str, sql: Callable[..., list[dict[str, Any]]]
) -> None:
    """Doc 04 s2: natural keys are unique (upsert targets of the linker, doc 06 s2)."""
    definitions = [
        row["indexdef"]
        for row in sql(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = :table "
            "AND indexdef LIKE 'CREATE UNIQUE INDEX%'",
            table=table,
        )
    ]
    assert any(definition.endswith(f"({', '.join(key)})") for definition in definitions), (
        definitions
    )


def test_fr11_embedding_dimension_equals_embed_dim(
    stack: str, scalar: Callable[..., Any], setting: Callable[[str], str]
) -> None:
    """Doc 04 s6, OI-05: `chunk.embedding` is `vector(EMBED_DIM)`."""
    declared = scalar(
        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
        "WHERE attrelid = 'chunk'::regclass AND attname = 'embedding'"
    )
    assert declared == f"vector({setting('EMBED_DIM')})"
