"""`SafetyTechService`: findings by category and evidence gaps (document 08 section 5)."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from flamescope_api.repositories.investigations import InvestigationRepo
from flamescope_api.repositories.runs import RunRecord, RunRepo
from flamescope_api.services.scenario import ANALOGUE_TAG
from flamescope_api.services.scenario_math import GRAVITY_TOLERANCE
from flamescope_common.schemas.api import (
    GapItem,
    GapsResponse,
    InvestigationFilters,
    SafetyFinding,
    SafetyGroup,
    SafetyTechResponse,
)
from flamescope_common.schemas.card import FindingCategory
from flamescope_common.sources import SourceRef

CATEGORY_LABELS: dict[FindingCategory, str] = {
    "detection": "Detection",
    "suppression": "Suppression",
    "material_screening": "Material screening",
    "post_fire": "Post-fire hazards",
    "atmosphere_design": "Atmosphere design",
    "fundamental": "Fundamental combustion",
}
FUTURE_PARTIAL_GRAVITY_DATA = ["LUCI", "FM2"]
PARTIAL_GRAVITY_GAP_ID = "partial_gravity"
PARTIAL_GRAVITY_DETAIL = (
    "PSI holds no partial-gravity combustion data yet. Microgravity (0 g) and normal-gravity "
    "(1 g) results bound the behaviour at intermediate gravity."
)
O2_START, O2_STEP, O2_BINS = 0.10, 0.05, 18
PRESSURE_START_KPA, PRESSURE_STEP_KPA, PRESSURE_BINS = 20.0, 10.0, 9
ENVELOPE_MIN_O2 = 0.30
ENVELOPE_MAX_PRESSURE_KPA = 70.3
ROUND_DIGITS = 2
ENVELOPE_NOTE = (
    " The region intersects the lunar-habitat envelope "
    "(oxygen at or above 0.30, pressure at or below 70.3 kPa)."
)

Cell = tuple[int, int]


@dataclass(frozen=True)
class _Axis:
    start: float
    step: float
    bins: int

    def edges(self, index: int) -> tuple[float, float]:
        return (
            round(self.start + self.step * index, ROUND_DIGITS),
            round(self.start + self.step * (index + 1), ROUND_DIGITS),
        )

    def covers(self, index: int, span: tuple[float, float]) -> bool:
        low, high = self.edges(index)
        is_last = index == self.bins - 1
        below_upper_edge = span[0] <= high if is_last else span[0] < high
        return below_upper_edge and span[1] >= low


O2_AXIS = _Axis(O2_START, O2_STEP, O2_BINS)
PRESSURE_AXIS = _Axis(PRESSURE_START_KPA, PRESSURE_STEP_KPA, PRESSURE_BINS)


def _covered_cells(runs: Sequence[RunRecord]) -> set[Cell]:
    covered: set[Cell] = set()
    for run in runs:
        o2_span = run.span_of("o2_fraction")
        pressure_span = run.span_of("pressure_kpa")
        if o2_span is None or pressure_span is None:
            continue
        covered.update(
            (i, j)
            for i in range(O2_BINS)
            if O2_AXIS.covers(i, o2_span)
            for j in range(PRESSURE_BINS)
            if PRESSURE_AXIS.covers(j, pressure_span)
        )
    return covered


def _regions(uncovered: set[Cell]) -> list[list[Cell]]:
    """Connected components (4-neighbourhood) of uncovered grid cells."""
    remaining = set(uncovered)
    regions: list[list[Cell]] = []
    while remaining:
        queue = deque([min(remaining)])
        remaining.discard(queue[0])
        region: list[Cell] = []
        while queue:
            i, j = queue.popleft()
            region.append((i, j))
            for neighbour in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if neighbour in remaining:
                    remaining.discard(neighbour)
                    queue.append(neighbour)
        regions.append(sorted(region))
    return regions


def _in_envelope(cell: Cell) -> bool:
    return (
        O2_AXIS.edges(cell[0])[1] > ENVELOPE_MIN_O2
        and PRESSURE_AXIS.edges(cell[1])[0] <= ENVELOPE_MAX_PRESSURE_KPA
    )


def _region_item(number: int, region: Sequence[Cell], in_envelope: bool) -> GapItem:
    o2_low = O2_AXIS.edges(min(i for i, _ in region))[0]
    o2_high = O2_AXIS.edges(max(i for i, _ in region))[1]
    pressure_low = PRESSURE_AXIS.edges(min(j for _, j in region))[0]
    pressure_high = PRESSURE_AXIS.edges(max(j for _, j in region))[1]
    detail = (
        f"No run covers oxygen fraction {o2_low:g} to {o2_high:g} at {pressure_low:g} to "
        f"{pressure_high:g} kPa ({len(region)} grid cells)."
    )
    if in_envelope:
        detail += ENVELOPE_NOTE
    return GapItem(
        id=f"param_gap_{number}", title="Untested oxygen and pressure region", detail=detail
    )


def parameter_gaps(runs: Sequence[RunRecord]) -> list[GapItem]:
    """Contiguous uncovered oxygen/pressure regions; those in the lunar envelope come first."""
    covered = _covered_cells(runs)
    uncovered = {
        (i, j) for i in range(O2_BINS) for j in range(PRESSURE_BINS) if (i, j) not in covered
    }
    flagged = [
        (region, any(_in_envelope(cell) for cell in region)) for region in _regions(uncovered)
    ]
    flagged.sort(key=lambda entry: (not entry[1], -len(entry[0]), entry[0][0]))
    return [_region_item(number, region, flag) for number, (region, flag) in enumerate(flagged, 1)]


def has_partial_gravity_data(runs: Sequence[RunRecord]) -> bool:
    return any(
        run.gravity_g is not None and GRAVITY_TOLERANCE < run.gravity_g < 1 - GRAVITY_TOLERANCE
        for run in runs
    )


class SafetyTechService:
    """Safety-technology findings and gaps; deterministic, no LLM."""

    def __init__(self, investigations: InvestigationRepo, runs: RunRepo) -> None:
        self._investigations = investigations
        self._runs = runs

    def grouped(self) -> SafetyTechResponse:
        rows = self._investigations.findings(None, None)
        groups = []
        for category, label in CATEGORY_LABELS.items():
            members = [row for row in rows if row.finding.category == category]
            groups.append(
                SafetyGroup(
                    category=category,
                    label=label,
                    findings=[
                        SafetyFinding(
                            id=row.finding.id,
                            statement=row.finding.statement,
                            investigation=row.acronym,
                            source=SourceRef.model_validate(row.finding.source),
                            confidence=float(row.finding.confidence),
                        )
                        for row in members
                    ],
                    investigations=sorted({row.acronym for row in members}),
                )
            )
        return SafetyTechResponse(groups=groups)

    def gaps(self) -> GapsResponse:
        runs = self._runs.query(None)
        gaps: list[GapItem] = []
        if not has_partial_gravity_data(runs):
            analogues = self._investigations.search(InvestigationFilters(tag=[ANALOGUE_TAG]), None)
            gaps.append(
                GapItem(
                    id=PARTIAL_GRAVITY_GAP_ID,
                    title="No partial-gravity data",
                    detail=PARTIAL_GRAVITY_DETAIL,
                    related=[row.investigation.acronym for row in analogues.rows],
                    future=list(FUTURE_PARTIAL_GRAVITY_DATA),
                )
            )
        return GapsResponse(gaps=[*gaps, *parameter_gaps(runs)])
