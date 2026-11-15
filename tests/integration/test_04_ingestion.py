"""Seed ingestion result (document 12 section 2; document 06 sections 2, 3 and 5).

Requirements: FR-01 (one card per seed file), FR-03 (scores for three lenses), FR-11 (chunks),
FR-12 (hardware links), FR-15 (provenance on findings), NFR-05 (idempotent re-run).
Call flows: CF-01 (ingest job in deploy), CF-02 (seed ingestion: normalize, link, score,
index, review).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.order(4)]

Rows = Callable[..., list[dict[str, Any]]]

# Catalog tables written by the seed stages; `ingest_run` is an audit log and grows by design.
CATALOG_TABLES = (
    "project", "hardware", "investigation", "investigation_hardware", "fuel", "test_run",
    "condition", "measurement", "publication", "finding", "earth_application",
    "finding_earth_application", "earth_application_investigation", "relevance_score", "chunk",
)  # fmt: skip


def _per_investigation(sql: Rows, statement: str) -> dict[str, int]:
    return {row["acronym"]: row["n"] for row in sql(statement)}


def _counts(sql: Rows) -> dict[str, int]:
    return {
        table: sql(f'SELECT count(*) AS n FROM "{table}"')[0]["n"]  # noqa: S608 - fixed names
        for table in CATALOG_TABLES
    }


def _seed_count(record: dict[str, Any], key: str) -> int:
    return len(record.get(key) or [])


def _expected_runs(record: dict[str, Any]) -> int:
    """Doc 06 s3.5: one row per explicit run, otherwise one aggregate run per fuel."""
    return _seed_count(record, "runs") or _seed_count(record, "fuels")


def test_fr01_one_investigation_per_seed_file(
    stack: str, seed_acronyms: list[str], sql: Rows, acronym_key: Callable[[str], Any]
) -> None:
    """FR-01, CF-02: investigations equal the seed files, keyed by acronym (one row each)."""
    acronyms = [row["acronym"] for row in sql("SELECT acronym FROM investigation")]
    assert sorted(acronyms, key=acronym_key) == seed_acronyms


@pytest.mark.parametrize(
    ("seed_key", "table"),
    [("runs", "test_run"), ("findings", "finding"), ("publications", "publication"),
     ("measurements", "measurement")],
)  # fmt: skip
def test_fr01_child_rows_match_seed_files(
    seed_key: str, table: str, stack: str, seed_records: dict[str, dict[str, Any]], sql: Rows
) -> None:
    """FR-01, CF-02: runs, findings, publications and measurements per investigation."""
    count = _expected_runs if seed_key == "runs" else lambda record: _seed_count(record, seed_key)
    expected = {acronym: count(record) for acronym, record in seed_records.items()}
    actual = _per_investigation(
        sql,
        f"SELECT i.acronym, count(t.id) AS n FROM investigation i "  # noqa: S608 - fixed names
        f'LEFT JOIN "{table}" t ON t.investigation_id = i.id GROUP BY i.acronym',
    )
    assert actual == expected


def test_fr03_every_investigation_has_three_lenses_of_scores(
    stack: str, rubric_file: dict[str, Any], sql: Rows
) -> None:
    """FR-03, CF-02: one score row per rubric criterion of the three lenses (current version)."""
    expected = sorted(
        (lens, criterion["id"])
        for lens, definition in rubric_file["lenses"].items()
        for criterion in definition["criteria"]
    )
    rows = sql(
        "SELECT i.acronym, r.lens, r.criterion FROM investigation i "
        "LEFT JOIN relevance_score r ON r.investigation_id = i.id "
        "AND r.rubric_version = :version ORDER BY 1, 2, 3",
        version=rubric_file["rubric_version"],
    )
    by_investigation: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        by_investigation.setdefault(row["acronym"], []).append((row["lens"], row["criterion"]))
    assert {acronym: pairs == expected for acronym, pairs in by_investigation.items()} == (
        dict.fromkeys(by_investigation, True)
    )


def test_fr11_every_investigation_has_a_chunk(stack: str, sql: Rows) -> None:
    """FR-11, CF-02: the index stage wrote at least one chunk per investigation."""
    chunks = _per_investigation(
        sql,
        "SELECT i.acronym, count(c.id) AS n FROM investigation i "
        "LEFT JOIN chunk c ON c.investigation_id = i.id GROUP BY i.acronym",
    )
    assert [acronym for acronym, count in chunks.items() if count == 0] == []


def test_fr12_hardware_links_match_seed_files(
    stack: str, seed_records: dict[str, dict[str, Any]], sql: Rows
) -> None:
    """FR-12, CF-02: every investigation links exactly its seed hardware with the stated role;
    a seed file without hardware (unknown) has no links."""
    expected = sorted(
        (acronym, item["name"], item["role"])
        for acronym, record in seed_records.items()
        for item in record.get("hardware") or []
    )
    rows = sql(
        "SELECT i.acronym, h.name, ih.role FROM investigation_hardware ih "
        "JOIN investigation i ON i.id = ih.investigation_id "
        "JOIN hardware h ON h.id = ih.hardware_id"
    )
    assert sorted((row["acronym"], row["name"], row["role"]) for row in rows) == expected
    unlinked = sql(
        "SELECT acronym FROM investigation i WHERE NOT EXISTS "
        "(SELECT 1 FROM investigation_hardware ih WHERE ih.investigation_id = i.id)"
    )
    without_hardware = {
        acronym for acronym, record in seed_records.items() if not record.get("hardware")
    }
    assert {row["acronym"] for row in unlinked} == without_hardware


def test_cf02_latest_ingest_run_per_investigation_is_ok(stack: str, sql: Rows) -> None:
    """CF-02, doc 06 s6: the latest `ingest_run` of every investigation is a seed run, `ok`."""
    rows = sql(
        "SELECT DISTINCT ON (i.acronym) i.acronym, r.mode, r.status FROM investigation i "
        "LEFT JOIN ingest_run r ON r.investigation_id = i.id "
        "ORDER BY i.acronym, r.started_at DESC"
    )
    assert [row for row in rows if (row["mode"], row["status"]) != ("seed", "ok")] == []


def test_fr15_findings_carry_provenance(
    stack: str, sql: Rows, source_ref_is_valid: Callable[[dict[str, Any]], bool]
) -> None:
    """FR-15: every finding has a `SourceRef` with `kind` and `uri` and a confidence."""
    findings = sql("SELECT id, source, confidence FROM finding")
    invalid = [
        row["id"]
        for row in findings
        if not source_ref_is_valid(row["source"] or {}) or row["confidence"] is None
    ]
    assert invalid == []


def test_nfr05_ingest_seed_is_idempotent(
    stack: str, run_make: Callable[..., Any], sql: Rows
) -> None:
    """NFR-05, CF-02: `make ingest-seed` again keeps row counts and every `card_version`."""
    counts_before = _counts(sql)
    versions_before = sql("SELECT acronym, card_version FROM investigation ORDER BY 1")
    runs_before = sql("SELECT count(*) AS n FROM ingest_run")[0]["n"]
    rerun = run_make("ingest-seed")
    assert rerun.returncode == 0, f"{rerun.stdout[-4000:]}\n{rerun.stderr[-4000:]}"
    assert _counts(sql) == counts_before
    assert sql("SELECT acronym, card_version FROM investigation ORDER BY 1") == versions_before
    new_runs = sql("SELECT status FROM ingest_run ORDER BY id OFFSET :offset", offset=runs_before)
    assert new_runs
    assert {row["status"] for row in new_runs} == {"ok"}
