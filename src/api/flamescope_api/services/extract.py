"""`ExtractService`: filtered run tables as preview, CSV or JSON export (FR-10)."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import JsonValue

from flamescope_api.repositories.runs import RunRecord, RunRepo
from flamescope_api.services.scenario import scenario_from_id
from flamescope_api.services.scenario_math import matching_runs
from flamescope_common.errors import ValidationError
from flamescope_common.rubric import Rubric
from flamescope_common.schemas.api import (
    ColumnInfo,
    DictionaryResponse,
    ExportFormat,
    ExportRequest,
    ExtractFilters,
    ExtractRequest,
    Table,
)

CSV_MEDIA_TYPE = "text/csv"
JSON_MEDIA_TYPE = "application/json"
COMMENT_PREFIX = "# "


@dataclass(frozen=True)
class ExportFile:
    """A downloadable file: bytes, media type and the `Content-Disposition` file name."""

    content: bytes
    media_type: str
    filename: str


@dataclass(frozen=True)
class _Column:
    info: ColumnInfo
    value: Callable[[RunRecord], JsonValue]


def _outcome(key: str) -> Callable[[RunRecord], JsonValue]:
    return lambda run: run.outcome.get(key)


def _first_dimension(run: RunRecord) -> JsonValue:
    dimensions = run.geometry.get("dimensions_mm") or {}
    return next((value for value in dimensions.values() if value is not None), None)


def _condition(name: str) -> Callable[[RunRecord], JsonValue]:
    return lambda run: run.value_of(name)


def _column(
    name: str,
    label: str,
    unit: str | None,
    description: str,
    value: Callable[[RunRecord], JsonValue],
) -> _Column:
    return _Column(ColumnInfo(name=name, label=label, unit=unit, description=description), value)


COLUMNS: tuple[_Column, ...] = (
    _column(
        "investigation", "Investigation", None, "Investigation acronym.", lambda r: r.investigation
    ),
    _column("run_label", "Run", None, "Sample or test point name.", lambda r: r.label),
    _column("fuel_name", "Fuel", None, "Fuel material name.", lambda r: r.fuel_name),
    _column("fuel_phase", "Fuel phase", None, "gas, liquid or solid.", lambda r: r.fuel_phase),
    _column("shape", "Shape", None, "Sample or burner shape.", lambda r: r.geometry.get("shape")),
    _column(
        "characteristic_dimension_mm",
        "Characteristic dimension",
        "mm",
        "First stated sample dimension.",
        _first_dimension,
    ),
    _column(
        "o2_fraction",
        "Oxygen fraction",
        "fraction",
        "Oxygen mole fraction, 0 to 1.",
        _condition("o2_fraction"),
    ),
    _column("diluent", "Diluent", None, "Diluent gas, for example N2.", lambda r: r.diluent),
    _column("pressure_kpa", "Pressure", "kPa", "Total pressure.", _condition("pressure_kpa")),
    _column(
        "flow_speed_cm_s",
        "Flow speed",
        "cm/s",
        "Ambient flow speed.",
        _condition("flow_speed_cm_s"),
    ),
    _column(
        "flow_direction",
        "Flow direction",
        None,
        "opposed, concurrent, quiescent or coflow.",
        lambda r: r.flow_direction,
    ),
    _column(
        "gravity_g",
        "Gravity",
        "g",
        "0 for microgravity, 1 for normal gravity.",
        _condition("gravity_g"),
    ),
    _column("ignited", "Ignited", None, "Whether ignition occurred.", _outcome("ignited")),
    _column(
        "flame_spread_rate_mm_s",
        "Flame spread rate",
        "mm/s",
        "Measured flame spread rate.",
        _outcome("flame_spread_rate_mm_s"),
    ),
    _column(
        "extinction", "Extinction", None, "Whether the flame extinguished.", _outcome("extinction")
    ),
    _column(
        "is_aggregate",
        "Aggregate",
        None,
        "True when the row states a range rather than one test.",
        lambda r: r.is_aggregate,
    ),
    _column(
        "confidence", "Confidence", None, "Extraction confidence, 0 to 1.", lambda r: r.confidence
    ),
    _column(
        "source_uri",
        "Source URI",
        None,
        "Where the run was taken from.",
        lambda r: r.source.get("uri"),
    ),
    _column(
        "source_locator",
        "Source locator",
        None,
        "Section, page or character range.",
        lambda r: r.source.get("locator"),
    ),
)
DEFAULT_COLUMNS = tuple(column.info.name for column in COLUMNS)
_BY_NAME = {column.info.name: column for column in COLUMNS}


def _select_columns(names: Sequence[str] | None) -> list[_Column]:
    chosen = list(names) if names else list(DEFAULT_COLUMNS)
    unknown = [name for name in chosen if name not in _BY_NAME]
    if unknown:
        raise ValidationError(f"Unknown columns {unknown}", {"known": list(DEFAULT_COLUMNS)})
    return [_BY_NAME[name] for name in chosen]


def build_table(runs: Sequence[RunRecord], columns: Sequence[str] | None = None) -> Table:
    """Rows of the chosen columns (default: all) for the given runs."""
    chosen = _select_columns(columns)
    rows = [[column.value(run) for column in chosen] for run in runs]
    return Table(columns=[column.info for column in chosen], rows=rows, total=len(rows))


def _csv_cell(value: JsonValue) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def render_csv(table: Table, header: dict[str, str]) -> str:
    """Commented provenance header block followed by the CSV table."""
    buffer = io.StringIO()
    for key, value in header.items():
        buffer.write(f"{COMMENT_PREFIX}{key}: {value}\n")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([column.name for column in table.columns])
    for row in table.rows:
        writer.writerow([_csv_cell(cell) for cell in row])
    return buffer.getvalue()


def render_json(table: Table, header: dict[str, str]) -> str:
    names = [column.name for column in table.columns]
    document = {
        "meta": header,
        "columns": [column.model_dump() for column in table.columns],
        "rows": [dict(zip(names, row, strict=True)) for row in table.rows],
    }
    return json.dumps(document, indent=2)


class ExtractService:
    """Preview, export and describe run tables; deterministic, no LLM."""

    def __init__(self, runs: RunRepo, rubric: Rubric) -> None:
        self._runs = runs
        self._rubric = rubric

    def preview(self, query: ExtractRequest) -> Table:
        runs = self._select_runs(query.filters)
        table = build_table(runs[: query.limit], query.columns)
        return table.model_copy(update={"total": len(runs)})

    def export(self, query: ExportRequest, format: ExportFormat) -> ExportFile:  # noqa: A002 - name fixed by doc 03
        """Every matching run (the preview `limit` does not apply to exports)."""
        table = build_table(self._select_runs(query.filters), query.columns)
        exported_at = datetime.now(UTC)
        header = {
            "exported_at": exported_at.isoformat(timespec="seconds"),
            "filters": query.filters.model_dump_json(exclude_defaults=True),
            "rubric_version": self._rubric.rubric_version,
        }
        stamp = exported_at.strftime("%Y%m%dT%H%M%SZ")
        if format == "json":
            return ExportFile(
                render_json(table, header).encode(),
                JSON_MEDIA_TYPE,
                f"flamescope-extract-{stamp}.json",
            )
        return ExportFile(
            render_csv(table, header).encode(), CSV_MEDIA_TYPE, f"flamescope-extract-{stamp}.csv"
        )

    def dictionary(self) -> DictionaryResponse:
        return DictionaryResponse(columns=[column.info for column in COLUMNS])

    def _select_runs(self, filters: ExtractFilters) -> list[RunRecord]:
        runs = self._runs.query(filters)
        if filters.scenario_id is None:
            return runs
        scenario = scenario_from_id(filters.scenario_id)
        return matching_runs(scenario, runs, self._runs.condition_ranges())
