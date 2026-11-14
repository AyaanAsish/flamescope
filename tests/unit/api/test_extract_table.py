"""FR-08: extract columns, provenance, null handling and exports (document 05 section 8)."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from typing import Any

import pytest

from flamescope_api.repositories.runs import RunRecord
from flamescope_api.services.extract import ExtractService, build_table
from flamescope_api.services.scenario import scenario_id_of
from flamescope_common.errors import ValidationError
from flamescope_common.rubric import Rubric
from flamescope_common.schemas.api import (
    ExportRequest,
    ExtractFilters,
    ExtractRequest,
    RangePair,
    ResolvedScenario,
)

pytestmark = pytest.mark.unit

RunFactory = Callable[..., RunRecord]
# Document 05 section 8, in order.
DEFAULT_COLUMNS = [
    "investigation",
    "run_label",
    "fuel_name",
    "fuel_phase",
    "shape",
    "characteristic_dimension_mm",
    "o2_fraction",
    "diluent",
    "pressure_kpa",
    "flow_speed_cm_s",
    "flow_direction",
    "gravity_g",
    "ignited",
    "flame_spread_rate_mm_s",
    "extinction",
    "is_aggregate",
    "confidence",
    "source_uri",
    "source_locator",
]
O2_DICTIONARY_ENTRY = {
    "name": "o2_fraction",
    "label": "Oxygen fraction",
    "unit": "fraction",
    "description": "Oxygen mole fraction, 0 to 1.",
}
COMMENT_MARK = "#"
RANGES: dict[str, RangePair] = {"o2_fraction": (0.1, 0.9)}


@pytest.fixture
def full_run(make_run: RunFactory) -> RunRecord:
    return make_run(
        investigation="ALPHA",
        label="sample 1",
        fuel_name="fuel-a",
        fuel_phase="solid",
        geometry={"shape": "rod", "dimensions_mm": {"diameter": 6.0, "length": 50.0}},
        o2_fraction=0.21,
        pressure_kpa=101.3,
        outcome={"ignited": True, "flame_spread_rate_mm_s": 1.5, "extinction": None},
        source={"kind": "document", "uri": "s3://nasa-psi/test/doc.pdf", "locator": "page 3"},
    )


@pytest.fixture
def sparse_run(make_run: RunFactory) -> RunRecord:
    return make_run(investigation="BRAVO", label="sample 2", o2_fraction=0.5, source={})


def _cell(table: Any, row: int, column: str) -> Any:
    names = [info.name for info in table.columns]
    return table.rows[row][names.index(column)]


class FakeRunRepo:
    def __init__(self, runs: list[RunRecord]) -> None:
        self._runs = runs

    def query(self, filters: ExtractFilters | None = None) -> list[RunRecord]:
        return list(self._runs)

    def condition_ranges(self) -> dict[str, RangePair]:
        return dict(RANGES)


def _service(runs: list[RunRecord], rubric: Rubric) -> ExtractService:
    return ExtractService(FakeRunRepo(runs), rubric)  # type: ignore[arg-type]


class TestBuildTable:
    def test_fr08_default_columns_in_documented_order(self, full_run: RunRecord) -> None:
        """FR-08: omitted columns mean the default columns of document 05 section 8."""
        table = build_table([full_run], None)
        assert [info.name for info in table.columns] == DEFAULT_COLUMNS
        assert [info.name for info in build_table([full_run], []).columns] == DEFAULT_COLUMNS

    def test_fr08_provenance_columns(self, full_run: RunRecord) -> None:
        """FR-08, FR-15: every row carries its source URI and locator."""
        table = build_table([full_run], None)
        assert _cell(table, 0, "source_uri") == "s3://nasa-psi/test/doc.pdf"
        assert _cell(table, 0, "source_locator") == "page 3"

    def test_fr08_characteristic_dimension_is_first_stated(self, full_run: RunRecord) -> None:
        """FR-08: first stated dimension of `geometry.dimensions_mm`, or null."""
        assert _cell(build_table([full_run], None), 0, "characteristic_dimension_mm") == 6.0

    def test_fr08_nulls_stay_null(self, sparse_run: RunRecord) -> None:
        """FR-08: unknown values are null, never guessed."""
        table = build_table([sparse_run], None)
        for column in (
            "fuel_name",
            "shape",
            "characteristic_dimension_mm",
            "pressure_kpa",
            "ignited",
            "source_uri",
            "source_locator",
        ):
            assert _cell(table, 0, column) is None

    def test_fr08_requested_columns_in_requested_order(self, full_run: RunRecord) -> None:
        """FR-08: an explicit column list is honoured in its order."""
        table = build_table([full_run], ["o2_fraction", "investigation"])
        assert [info.name for info in table.columns] == ["o2_fraction", "investigation"]
        assert table.rows == [[0.21, "ALPHA"]]

    def test_fr08_unknown_column_is_bad_request(self, full_run: RunRecord) -> None:
        """FR-08: an unknown column name is HTTP 400 `bad_request`."""
        with pytest.raises(ValidationError):
            build_table([full_run], ["investigation", "no_such_column"])


class TestPreviewAndDictionary:
    def test_fr08_preview_limit_bounds_rows_total_counts_all(
        self, rubric: Rubric, full_run: RunRecord, sparse_run: RunRecord
    ) -> None:
        """FR-08: `limit` bounds the preview rows; `total` counts every matching run."""
        table = _service([full_run, sparse_run], rubric).preview(ExtractRequest(limit=1))
        assert len(table.rows) == 1
        assert table.total == 2

    def test_fr08_dictionary_lists_columns_with_units(self, rubric: Rubric) -> None:
        """FR-08: dictionary entries carry name, label, unit (null if unitless), description."""
        columns = _service([], rubric).dictionary().columns
        by_name = {column.name: column for column in columns}
        assert set(DEFAULT_COLUMNS) <= set(by_name)
        assert by_name["o2_fraction"].model_dump() == O2_DICTIONARY_ENTRY
        assert by_name["pressure_kpa"].unit == "kPa"
        assert by_name["flow_speed_cm_s"].unit == "cm/s"
        assert by_name["investigation"].unit is None

    def test_fr08_scenario_id_keeps_runs_with_similarity_0_6(
        self, rubric: Rubric, make_run: RunFactory
    ) -> None:
        """FR-08: `scenario_id` keeps only runs with similarity >= 0.6 to the scenario."""
        near = make_run(investigation="NEAR", o2_fraction=0.30)
        far = make_run(investigation="FAR", o2_fraction=0.90)
        scenario_id = scenario_id_of(ResolvedScenario(o2_fraction=0.34))
        query = ExtractRequest(filters=ExtractFilters(scenario_id=scenario_id))
        table = _service([near, far], rubric).preview(query)
        assert table.total == 1
        assert _cell(table, 0, "investigation") == "NEAR"

    def test_fr08_invalid_scenario_id_is_bad_request(self, rubric: Rubric) -> None:
        """FR-08: an undecodable `scenario_id` is HTTP 400 `bad_request`."""
        query = ExtractRequest(filters=ExtractFilters(scenario_id="***"))
        with pytest.raises(ValidationError):
            _service([], rubric).preview(query)


def _csv_parts(content: bytes) -> tuple[list[str], list[list[str]]]:
    lines = content.decode().splitlines()
    comments = [line for line in lines if line.startswith(COMMENT_MARK)]
    body = [line for line in lines if not line.startswith(COMMENT_MARK)]
    return comments, list(csv.reader(io.StringIO("\n".join(body))))


class TestExport:
    def test_fr08_csv_has_header_block_and_parses(
        self, rubric: Rubric, full_run: RunRecord, sparse_run: RunRecord
    ) -> None:
        """FR-08: CSV with a commented header block (export time, filters, rubric version)."""
        file = _service([full_run, sparse_run], rubric).export(ExportRequest(limit=1), "csv")
        comments, rows = _csv_parts(file.content)
        header_text = "\n".join(comments)
        assert "exported_at" in header_text
        assert "filters" in header_text
        assert rubric.rubric_version in header_text
        assert rows[0] == DEFAULT_COLUMNS
        assert len(rows) == 3, "export ignores the preview limit"
        assert file.media_type == "text/csv"
        assert file.filename.endswith(".csv")

    def test_fr08_csv_null_is_empty_cell(self, rubric: Rubric, sparse_run: RunRecord) -> None:
        """FR-08: null values export as empty CSV cells."""
        file = _service([sparse_run], rubric).export(ExportRequest(), "csv")
        _, rows = _csv_parts(file.content)
        record = dict(zip(rows[0], rows[1], strict=True))
        assert record["fuel_name"] == ""
        assert record["o2_fraction"] == "0.5"

    def test_fr08_json_export(self, rubric: Rubric, full_run: RunRecord) -> None:
        """FR-08: JSON export is `application/json` and carries every row."""
        file = _service([full_run], rubric).export(ExportRequest(format="json"), "json")
        document = json.loads(file.content)
        assert file.media_type == "application/json"
        assert file.filename.endswith(".json")
        assert json.dumps(document).count("s3://nasa-psi/test/doc.pdf") == 1
