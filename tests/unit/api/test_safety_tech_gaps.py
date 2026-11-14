"""FR-09, FR-14, FR-16: `SafetyTechService` groups and gaps (doc 05 s9, doc 08 s5).

Expected regions are derived by hand from the grid rules: oxygen bins of 0.05 from 0.10 to
1.00 (18 bins), pressure bins of 10 kPa from 20 to 110 (9 bins), half-open bins with the last
bin closed, 4-connected regions, envelope regions first, then larger, then the lowest cell.
Acronyms are placeholders; no scientific fact is implied.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from flamescope_api.repositories.runs import RunRecord
from flamescope_api.services.safety_tech import SafetyTechService, parameter_gaps
from flamescope_common.schemas.api import GapItem

pytestmark = pytest.mark.unit

RunFactory = Callable[..., RunRecord]
SOURCE = {"kind": "psi_page", "uri": "https://psi.nasa.gov/test", "locator": "page 1"}
CATEGORY_ORDER = [
    "detection",
    "suppression",
    "material_screening",
    "post_fire",
    "atmosphere_design",
    "fundamental",
]
REGION_TITLE = "Untested oxygen and pressure region"
ENVELOPE_NOTE = (
    " The region intersects the lunar-habitat envelope "
    "(oxygen at or above 0.30, pressure at or below 70.3 kPa)."
)
FULL_O2 = {"min": 0.10, "max": 1.00}
FULL_PRESSURE = {"min": 20.0, "max": 110.0}


def _detail(o2: str, pressure: str, cells: int, *, in_envelope: bool) -> str:
    text = f"No run covers oxygen fraction {o2} at {pressure} kPa ({cells} grid cells)."
    return text + ENVELOPE_NOTE if in_envelope else text


def _summary(gaps: list[GapItem]) -> list[tuple[str, str]]:
    return [(gap.id, gap.detail) for gap in gaps]


@pytest.fixture
def spanning(make_run: RunFactory) -> Callable[..., RunRecord]:
    """An aggregate run whose stated o2 and pressure ranges are the given spans."""

    def build(o2: dict[str, Any], pressure: dict[str, Any], **overrides: Any) -> RunRecord:
        stated = {"o2_fraction": o2, "pressure_kpa": pressure}
        return make_run(is_aggregate=True, varied_parameters=stated, **overrides)

    return build


class FakeInvestigationRepo:
    def __init__(self, finding_rows: list[SimpleNamespace]) -> None:
        self._finding_rows = finding_rows
        self.searched_tags: list[list[str]] = []

    def findings(self, categories: Any, acronyms: Any) -> list[SimpleNamespace]:
        return self._finding_rows

    def search(self, filters: Any, page: Any) -> SimpleNamespace:
        self.searched_tags.append(list(filters.tag))
        row = SimpleNamespace(investigation=SimpleNamespace(acronym="ANALOGUE"))
        return SimpleNamespace(rows=[row], total=1)


class FakeRunRepo:
    def __init__(self, runs: list[RunRecord]) -> None:
        self._runs = runs

    def query(self, filters: Any) -> list[RunRecord]:
        return list(self._runs)


def _finding_row(identifier: int, category: str, acronym: str) -> SimpleNamespace:
    finding = SimpleNamespace(
        id=identifier,
        statement=f"Finding {identifier}.",
        category=category,
        source=SOURCE,
        confidence=0.8,
    )
    return SimpleNamespace(finding=finding, acronym=acronym)


def _service(runs: list[RunRecord], finding_rows: list[SimpleNamespace] | None = None) -> Any:
    repo = FakeInvestigationRepo(finding_rows or [])
    return SafetyTechService(repo, FakeRunRepo(runs)), repo  # type: ignore[arg-type]


class TestSafetyTechGroups:
    def test_fr09_all_six_categories_in_document_order(self) -> None:
        """FR-09: always six groups, in document 05 section 9 order, empty ones included."""
        service, _ = _service([], [_finding_row(1, "suppression", "BRAVO")])
        groups = service.grouped().groups
        observed = (
            [group.category for group in groups],
            [len(group.findings) for group in groups],
            groups[0].label,
        )
        assert observed == (CATEGORY_ORDER, [0, 1, 0, 0, 0, 0], "Detection")

    def test_fr09_group_lists_findings_and_distinct_sorted_investigations(self) -> None:
        """FR-09: findings keep their attribution; investigations are distinct and sorted."""
        rows = [
            _finding_row(1, "detection", "SAME-R"),
            _finding_row(2, "detection", "SAME"),
            _finding_row(3, "detection", "SAME"),
        ]
        service, _ = _service([], rows)
        detection = service.grouped().groups[0]
        observed = (
            [(item.id, item.investigation, item.confidence) for item in detection.findings],
            detection.investigations,
        )
        assert observed == (
            [(1, "SAME-R", 0.8), (2, "SAME", 0.8), (3, "SAME", 0.8)],
            ["SAME", "SAME-R"],
        )


class TestPartialGravityGap:
    def test_fr16_gap_first_with_analogues_and_future_data(self) -> None:
        """FR-16: without partial-gravity runs `partial_gravity` leads the list."""
        service, repo = _service([])
        first = service.gaps().gaps[0]
        observed = (first.id, first.title, first.related, first.future, repo.searched_tags)
        assert observed == (
            "partial_gravity",
            "No partial-gravity data",
            ["ANALOGUE"],
            ["LUCI", "FM2"],
            [["partial_gravity_analogue"]],
        )

    @pytest.mark.parametrize(
        ("gravity_g", "has_gap"),
        [(None, True), (0.0, True), (0.02, True), (0.98, True), (1.0, True), (0.166, False)],
    )
    def test_fr16_gap_present_only_without_gravity_strictly_between(
        self, make_run: RunFactory, gravity_g: float | None, has_gap: bool
    ) -> None:
        """FR-16: a run more than 0.02 g from both 0 g and 1 g removes the gap."""
        service, _ = _service([make_run(gravity_g=gravity_g)])
        ids = [gap.id for gap in service.gaps().gaps]
        assert ("partial_gravity" in ids) is has_gap

    def test_fr14_parameter_gaps_follow_the_partial_gravity_gap(
        self, make_run: RunFactory
    ) -> None:
        """FR-14: parameter-space gaps come after `partial_gravity`, empty related/future."""
        service, _ = _service([make_run(gravity_g=0.0)])
        gaps = service.gaps().gaps
        observed = [(gap.id, gap.title, gap.related, gap.future) for gap in gaps]
        assert observed == [
            ("partial_gravity", "No partial-gravity data", ["ANALOGUE"], ["LUCI", "FM2"]),
            ("param_gap_1", REGION_TITLE, [], []),
        ]


class TestParameterGapRegions:
    def test_fr14_no_runs_leave_one_region_of_the_whole_grid(self) -> None:
        """FR-14: 18 x 9 = 162 uncovered cells in one envelope region."""
        assert _summary(parameter_gaps([])) == [
            ("param_gap_1", _detail("0.1 to 1", "20 to 110", 162, in_envelope=True))
        ]

    def test_fr14_runs_missing_a_value_cover_nothing(self, make_run: RunFactory) -> None:
        """FR-14: a run without a pressure value covers no cell."""
        gaps = parameter_gaps([make_run(o2_fraction=0.21)])
        assert _summary(gaps) == [
            ("param_gap_1", _detail("0.1 to 1", "20 to 110", 162, in_envelope=True))
        ]

    def test_fr14_last_bin_is_closed(self, spanning: Callable[..., RunRecord]) -> None:
        """FR-14: oxygen 1.00 covers only the closed last bin [0.95, 1.00]."""
        run = spanning({"min": 1.0, "max": 1.0}, FULL_PRESSURE)
        assert _summary(parameter_gaps([run])) == [
            ("param_gap_1", _detail("0.1 to 0.95", "20 to 110", 153, in_envelope=True))
        ]

    def test_fr14_envelope_regions_come_before_larger_regions(
        self, spanning: Callable[..., RunRecord]
    ) -> None:
        """FR-14: 13 envelope cells (0.35-1, 20-30 kPa) precede 36 cells (0.1-0.3) outside."""
        runs = [
            spanning({"min": 0.30, "max": 0.30}, FULL_PRESSURE),
            spanning({"min": 0.35, "max": 1.0}, {"min": 30.0, "max": 110.0}),
        ]
        assert _summary(parameter_gaps(runs)) == [
            ("param_gap_1", _detail("0.35 to 1", "20 to 30", 13, in_envelope=True)),
            ("param_gap_2", _detail("0.1 to 0.3", "20 to 110", 36, in_envelope=False)),
        ]

    def test_fr14_larger_region_first_among_envelope_regions(
        self, spanning: Callable[..., RunRecord]
    ) -> None:
        """FR-14: pressure 50 kPa splits the grid into 90 cells above and 54 below."""
        run = spanning(FULL_O2, {"min": 50.0, "max": 50.0})
        assert _summary(parameter_gaps([run])) == [
            ("param_gap_1", _detail("0.1 to 1", "60 to 110", 90, in_envelope=True)),
            ("param_gap_2", _detail("0.1 to 1", "20 to 50", 54, in_envelope=True)),
        ]

    def test_fr14_equal_regions_ordered_by_lowest_cell(
        self, spanning: Callable[..., RunRecord]
    ) -> None:
        """FR-14: pressure 60 kPa leaves two 72-cell regions; the lower one comes first."""
        run = spanning(FULL_O2, {"min": 60.0, "max": 60.0})
        assert _summary(parameter_gaps([run])) == [
            ("param_gap_1", _detail("0.1 to 1", "20 to 60", 72, in_envelope=True)),
            ("param_gap_2", _detail("0.1 to 1", "70 to 110", 72, in_envelope=True)),
        ]

    def test_fr14_diagonal_cells_are_separate_regions(
        self, spanning: Callable[..., RunRecord]
    ) -> None:
        """FR-14: 4-connectivity: cells (0, 0) and (1, 1) touch only at a corner."""
        runs = [
            spanning({"min": 0.15, "max": 1.0}, {"min": 20.0, "max": 20.0}),
            spanning({"min": 0.10, "max": 0.10}, {"min": 30.0, "max": 110.0}),
            spanning({"min": 0.20, "max": 1.0}, {"min": 30.0, "max": 30.0}),
            spanning({"min": 0.15, "max": 1.0}, {"min": 40.0, "max": 110.0}),
        ]
        assert _summary(parameter_gaps(runs)) == [
            ("param_gap_1", _detail("0.1 to 0.15", "20 to 30", 1, in_envelope=False)),
            ("param_gap_2", _detail("0.15 to 0.2", "30 to 40", 1, in_envelope=False)),
        ]

    def test_fr14_half_open_range_covers_its_open_side(
        self, spanning: Callable[..., RunRecord]
    ) -> None:
        """FR-14: `{min: null, max: 0.85}` covers every oxygen bin up to [0.85, 0.90)."""
        run = spanning({"min": None, "max": 0.85}, FULL_PRESSURE)
        assert _summary(parameter_gaps([run])) == [
            ("param_gap_1", _detail("0.9 to 1", "20 to 110", 18, in_envelope=True))
        ]

    def test_fr14_point_runs_cover_their_cell(self, make_run: RunFactory) -> None:
        """FR-14: a point run at (0.21, 101.3) covers cell [0.20, 0.25) x [100, 110]."""
        gaps = parameter_gaps([make_run(o2_fraction=0.21, pressure_kpa=101.3)])
        assert [(gap.id, gap.detail) for gap in gaps] == [
            ("param_gap_1", _detail("0.1 to 1", "20 to 110", 161, in_envelope=True))
        ]
