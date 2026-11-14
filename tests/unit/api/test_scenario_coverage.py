"""FR-07: catalog ranges, coverage states and caveats (document 08 sections 4.2 to 4.4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from flamescope_api.repositories.runs import RunRecord, ranges_from_records
from flamescope_api.services.scenario import ScenarioService, coverage, coverage_caveats
from flamescope_common.errors import LLMError
from flamescope_common.rubric import Presets
from flamescope_common.schemas.agents import ScenarioInterpreterOutput, SentenceWithFacts
from flamescope_common.schemas.api import (
    CoverageEntry,
    RangePair,
    ResolvedScenario,
    ScenarioRequest,
)

pytestmark = pytest.mark.unit

RunFactory = Callable[..., RunRecord]
ServiceFactory = Callable[..., ScenarioService]
RANGES: dict[str, RangePair] = {
    "o2_fraction": (0.10, 0.85),
    "pressure_kpa": (50.0, 101.3),
    "flow_speed_cm_s": (0.0, 60.0),
}
CATALOG_GRAVITY = (0.0, 1.0)
STATEMENT = "The scenario gravity is 0.166 g. Fixed statement."


class TestCatalogRanges:
    def test_fr07_ranges_span_all_condition_values(self, make_run: RunFactory) -> None:
        """FR-07: R_d = [min_d, max_d] over every run with a value."""
        runs = [
            make_run(o2_fraction=0.21, pressure_kpa=101.3),
            make_run(o2_fraction=0.35, pressure_kpa=None, flow_speed_cm_s=5),
        ]
        assert ranges_from_records(runs) == {
            "o2_fraction": (0.21, 0.35),
            "pressure_kpa": (101.3, 101.3),
            "flow_speed_cm_s": (5.0, 5.0),
        }

    def test_fr07_ranges_widened_by_aggregate_runs(self, make_run: RunFactory) -> None:
        """FR-07: stated ranges of aggregate runs widen the catalog range."""
        runs = [
            make_run(o2_fraction=0.21),
            make_run(
                is_aggregate=True,
                o2_fraction=0.30,
                varied_parameters={"o2_fraction": {"min": 0.15, "max": 0.45}},
            ),
        ]
        assert ranges_from_records(runs)["o2_fraction"] == (0.15, 0.45)

    def test_fr07_half_open_range_widens_only_by_its_known_endpoint(
        self, make_run: RunFactory
    ) -> None:
        """FR-07: a null endpoint does not widen the catalog range (doc 08 s4.2)."""
        runs = [
            make_run(o2_fraction=0.21),
            make_run(
                is_aggregate=True,
                varied_parameters={"o2_fraction": {"min": None, "max": 0.85}},
            ),
            make_run(
                is_aggregate=True,
                varied_parameters={"pressure_kpa": {"min": 50.0, "max": None}},
            ),
        ]
        assert ranges_from_records(runs) == {
            "o2_fraction": (0.21, 0.85),
            "pressure_kpa": (50.0, 50.0),
        }

    def test_fr07_dimension_without_values_has_no_range(self, make_run: RunFactory) -> None:
        """FR-07: a dimension with no catalog value has no range (coverage `no_data`)."""
        assert "flow_speed_cm_s" not in ranges_from_records([make_run(o2_fraction=0.21)])


class TestCoverageStates:
    @pytest.mark.parametrize(
        ("o2_fraction", "state"),
        [
            (0.10, "covered"),
            (0.34, "covered"),
            (0.85, "covered"),
            (0.9, "extrapolated"),
            (0.05, "extrapolated"),
        ],
    )
    def test_fr07_numeric_covered_or_extrapolated(self, o2_fraction: float, state: str) -> None:
        """FR-07: covered when min <= s <= max, extrapolated outside."""
        states = coverage(ResolvedScenario(o2_fraction=o2_fraction), RANGES)
        assert states == {"o2_fraction": state}

    def test_fr07_numeric_no_data_without_catalog_values(self) -> None:
        """FR-07: no_data when the catalog has no values for the dimension."""
        states = coverage(ResolvedScenario(flow_speed_cm_s=10), {"o2_fraction": (0.1, 0.85)})
        assert states == {"flow_speed_cm_s": "no_data"}

    def test_fr07_unset_dimensions_are_not_reported(self) -> None:
        """FR-07: coverage covers only the dimensions the scenario sets."""
        assert coverage(ResolvedScenario(pressure_kpa=56.5), RANGES) == {"pressure_kpa": "covered"}

    @pytest.mark.parametrize(
        ("gravity", "values", "state"),
        [
            (0.0, CATALOG_GRAVITY, "covered"),
            (1.0, CATALOG_GRAVITY, "covered"),
            (0.166, CATALOG_GRAVITY, "no_data"),
            (0.38, CATALOG_GRAVITY, "no_data"),
            (0.166, (0.0, 0.15), "covered"),
            (0.166, (0.0, 0.14), "no_data"),
            (0.166, (), "no_data"),
        ],
    )
    def test_fr07_gravity_covered_only_within_0_02(
        self, gravity: float, values: tuple[float, ...], state: str
    ) -> None:
        """FR-07: gravity is covered only with a run within 0.02 g, otherwise no_data."""
        states = coverage(ResolvedScenario(gravity_g=gravity), RANGES, values)
        assert states == {"gravity_g": state}

    def test_fr07_lunar_preset_coverage(self) -> None:
        """FR-07: lunar values in the worked ranges: numeric covered, gravity no_data."""
        scenario = ResolvedScenario(
            o2_fraction=0.34, pressure_kpa=56.5, gravity_g=0.166, flow_speed_cm_s=10
        )
        assert coverage(scenario, RANGES, CATALOG_GRAVITY) == {
            "o2_fraction": "covered",
            "pressure_kpa": "covered",
            "flow_speed_cm_s": "covered",
            "gravity_g": "no_data",
        }


class TestCoverageCaveats:
    def test_fr07_caveat_per_uncovered_dimension_then_statement(self) -> None:
        """FR-07: one uncited caveat per extrapolated / no_data dimension, then the statement."""
        scenario = ResolvedScenario(o2_fraction=0.95, pressure_kpa=56.5, gravity_g=0.166)
        entries = {
            "o2_fraction": CoverageEntry(state="extrapolated", catalog_range=(0.1, 0.85)),
            "pressure_kpa": CoverageEntry(state="covered", catalog_range=(50, 101.3)),
            "gravity_g": CoverageEntry(state="no_data", catalog_values=[0.0, 1.0]),
        }
        caveats = coverage_caveats(scenario, entries, STATEMENT)
        assert len(caveats) == 3
        assert caveats[0].endswith("0.95 lies outside the catalog range (extrapolated).")
        assert caveats[1].endswith("0.166 has no catalog data (no_data).")
        assert caveats[2] == STATEMENT

    def test_fr07_no_caveats_when_everything_is_covered(self) -> None:
        """FR-07: fully covered scenarios without gravity statement add no caveat."""
        entries = {"o2_fraction": CoverageEntry(state="covered", catalog_range=(0.1, 0.85))}
        assert coverage_caveats(ResolvedScenario(o2_fraction=0.3), entries, None) == []


class FixedInterpreter:
    """Orchestrator stand-in returning one interpreter output (or raising an error)."""

    def __init__(self, output: ScenarioInterpreterOutput | Exception) -> None:
        self._output = output

    async def run(self, name: str, payload: Any, *, stream: bool = False) -> Any:
        if isinstance(self._output, Exception):
            raise self._output
        return self._output


def _interpreter(text: str, fact_ids: list[str]) -> FixedInterpreter:
    sentence = SentenceWithFacts(text=text, fact_ids=fact_ids)
    return FixedInterpreter(ScenarioInterpreterOutput(sentences=[sentence], caveats=["hidden"]))


@pytest.fixture
def lunar_runs(make_run: RunFactory) -> list[RunRecord]:
    """One 0 g run inside the worked ranges; the run label names its fact text."""
    return [make_run(investigation="ALPHA", label="S1", o2_fraction=0.30, gravity_g=0.0)]


LUNAR_REQUEST = ScenarioRequest(preset="lunar_habitat")
SUPPORTED_SENTENCE = "ALPHA run S1 used oxygen fraction 0.3."


class TestExplanation:
    async def test_fr07_verified_sentences_then_deterministic_caveats(
        self, make_scenario_service: ServiceFactory, lunar_runs: list[RunRecord], presets: Presets
    ) -> None:
        """FR-07: cited agent sentences, then uncited caveats and the gravity statement."""
        service = make_scenario_service(
            lunar_runs, RANGES, _interpreter(SUPPORTED_SENTENCE, ["R1"])
        )
        explanation = (await service.match(LUNAR_REQUEST, True)).explanation
        assert explanation.status == "ok"
        first, *caveats = explanation.sentences
        assert first.text == SUPPORTED_SENTENCE
        assert first.citations
        assert all(not caveat.citations for caveat in caveats)
        assert caveats[-1].text == presets.gravity_bounding_statement(0.166)
        assert any(caveat.text.endswith("(no_data).") for caveat in caveats)
        assert "hidden" not in explanation.text, "the agent's own caveats are not shown"

    async def test_fr07_no_surviving_sentence_is_unavailable(
        self, make_scenario_service: ServiceFactory, lunar_runs: list[RunRecord]
    ) -> None:
        """FR-07: if no agent sentence survives verification the status is `unavailable`."""
        service = make_scenario_service(
            lunar_runs, RANGES, _interpreter("Unsupported claim.", ["R9"])
        )
        assert (await service.match(LUNAR_REQUEST, True)).explanation.status == "unavailable"

    async def test_fr07_llm_failure_is_unavailable(
        self, make_scenario_service: ServiceFactory, lunar_runs: list[RunRecord]
    ) -> None:
        """FR-07: an LLM failure keeps the deterministic response; explanation `unavailable`."""
        service = make_scenario_service(lunar_runs, RANGES, FixedInterpreter(LLMError("down")))
        response = await service.match(LUNAR_REQUEST, True)
        assert response.explanation.status == "unavailable"
        assert [match.acronym for match in response.matches] == ["ALPHA"]

    async def test_fr07_explain_false_is_skipped(
        self, make_scenario_service: ServiceFactory, lunar_runs: list[RunRecord]
    ) -> None:
        """FR-07: the explanation is requested only when `explain` is true."""
        service = make_scenario_service(lunar_runs, RANGES, FixedInterpreter(LLMError("unused")))
        assert (await service.match(LUNAR_REQUEST, False)).explanation.status == "skipped"

    async def test_fr07_coverage_entries_carry_ranges_and_values(
        self, make_scenario_service: ServiceFactory, lunar_runs: list[RunRecord]
    ) -> None:
        """FR-07: numeric entries carry `catalog_range`, gravity carries `catalog_values`."""
        coverage_entries = (
            await make_scenario_service(lunar_runs, RANGES).match(LUNAR_REQUEST, False)
        ).coverage
        assert coverage_entries["o2_fraction"] == CoverageEntry(
            state="covered", catalog_range=(0.10, 0.85)
        )
        assert coverage_entries["gravity_g"] == CoverageEntry(
            state="no_data", catalog_values=[0.0]
        )
