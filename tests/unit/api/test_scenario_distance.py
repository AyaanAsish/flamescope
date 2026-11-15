"""FR-07: scenario distance, fuel tiers, aggregate ranges and scenario identity (doc 08 s4.2)."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable

import pytest

from flamescope_api.repositories.runs import RunRecord
from flamescope_api.services.scenario import (
    distance,
    resolve_scenario,
    scenario_from_id,
    scenario_id_of,
)
from flamescope_api.services.scenario_math import dimension_distances, rank_matches, score_runs
from flamescope_common.errors import ValidationError
from flamescope_common.rubric import Presets
from flamescope_common.schemas.api import (
    RangePair,
    ResolvedScenario,
    ScenarioRequest,
    ScenarioWeights,
)

pytestmark = pytest.mark.unit

RunFactory = Callable[..., RunRecord]

# Document 08 section 6 scenario example.
WORKED_RANGES: dict[str, RangePair] = {
    "o2_fraction": (0.10, 0.85),
    "pressure_kpa": (50.0, 101.3),
    "flow_speed_cm_s": (0.0, 60.0),
}
WORKED_SIMILARITY = 0.696
WORKED_TOLERANCE = 0.001
NUM_O2 = 0.13 / 0.75
NUM_PRESSURE = 44.8 / 51.3
NUM_FLOW = 10 / 60
DEFAULT_WEIGHTS = ScenarioWeights()


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _worked_scenario(**overrides: object) -> ResolvedScenario:
    values: dict[str, object] = {
        "o2_fraction": 0.34,
        "pressure_kpa": 56.5,
        "flow_speed_cm_s": 10,
        "material": "PMMA",
    }
    return ResolvedScenario.model_validate({**values, **overrides})


@pytest.fixture
def worked_run(make_run: RunFactory) -> RunRecord:
    return make_run(
        o2_fraction=0.21,
        pressure_kpa=101.3,
        flow_speed_cm_s=20,
        fuel_name="PMMA",
        fuel_phase="solid",
        material_class="polymer",
    )


class TestWorkedExample:
    def test_fr07_worked_example_similarity_is_0_696(self, worked_run: RunRecord) -> None:
        """FR-07: document 08 section 6 gives similarity 0.696 (tolerance 0.001)."""
        result = distance(_worked_scenario(), worked_run, WORKED_RANGES, DEFAULT_WEIGHTS)
        assert 1 - result == pytest.approx(WORKED_SIMILARITY, abs=WORKED_TOLERANCE)

    def test_fr07_worked_example_per_dimension(self, worked_run: RunRecord) -> None:
        """FR-07: num_o2 0.1733, num_p 0.8733, num_flow 0.1667, fuel 0."""
        parts = dimension_distances(_worked_scenario(), worked_run, WORKED_RANGES)
        assert parts == pytest.approx(
            {"o2": NUM_O2, "pressure": NUM_PRESSURE, "flow": NUM_FLOW, "fuel": 0.0}
        )

    def test_fr07_default_weights(self) -> None:
        """FR-07: default weights o2 0.35, pressure 0.25, flow 0.15, fuel 0.25."""
        assert DEFAULT_WEIGHTS.model_dump() == {
            "o2": 0.35,
            "pressure": 0.25,
            "flow": 0.15,
            "fuel": 0.25,
        }


class TestNumericDimensions:
    def test_fr07_unset_dimensions_are_dropped(self, worked_run: RunRecord) -> None:
        """FR-07: unset dimensions leave numerator and denominator."""
        only_o2 = ResolvedScenario(o2_fraction=0.34)
        o2_pressure = ResolvedScenario(o2_fraction=0.34, pressure_kpa=56.5)
        assert distance(only_o2, worked_run, WORKED_RANGES, DEFAULT_WEIGHTS) == pytest.approx(
            NUM_O2
        )
        expected = (0.35 * NUM_O2 + 0.25 * NUM_PRESSURE) / 0.60
        assert distance(o2_pressure, worked_run, WORKED_RANGES, DEFAULT_WEIGHTS) == pytest.approx(
            expected
        )
        assert set(dimension_distances(only_o2, worked_run, WORKED_RANGES)) == {"o2"}

    def test_fr07_missing_condition_value_is_worst_case(self, make_run: RunFactory) -> None:
        """FR-07: num_d = 1 when the run has no value for the dimension."""
        run = make_run(o2_fraction=None)
        scenario = ResolvedScenario(o2_fraction=0.34)
        assert distance(scenario, run, WORKED_RANGES, DEFAULT_WEIGHTS) == pytest.approx(1.0)

    def test_fr07_numeric_distance_is_capped_at_one(self, make_run: RunFactory) -> None:
        """FR-07: num_d = min(1, |s - c| / range)."""
        run = make_run(pressure_kpa=10.0)
        narrow: dict[str, RangePair] = {"pressure_kpa": (10.0, 20.0)}
        scenario = ResolvedScenario(pressure_kpa=101.3)
        assert distance(scenario, run, narrow, DEFAULT_WEIGHTS) == pytest.approx(1.0)

    def test_fr07_zero_width_range_uses_epsilon(self, make_run: RunFactory) -> None:
        """FR-07: max(max - min, eps) avoids division by zero; equal values give 0."""
        run = make_run(pressure_kpa=101.3)
        point: dict[str, RangePair] = {"pressure_kpa": (101.3, 101.3)}
        assert distance(ResolvedScenario(pressure_kpa=101.3), run, point, DEFAULT_WEIGHTS) == 0.0
        assert distance(ResolvedScenario(pressure_kpa=90.0), run, point, DEFAULT_WEIGHTS) == 1.0

    def test_fr07_custom_weights_are_normalized(self, worked_run: RunRecord) -> None:
        """FR-07: distance divides by the sum of the weights of the set dimensions."""
        weights = ScenarioWeights(o2=1, pressure=1, flow=0, fuel=0)
        expected = (NUM_O2 + NUM_PRESSURE) / 2
        assert distance(_worked_scenario(), worked_run, WORKED_RANGES, weights) == pytest.approx(
            expected
        )


class TestAggregateRuns:
    def test_fr07_scenario_inside_aggregate_range_has_zero_distance(
        self, make_run: RunFactory
    ) -> None:
        """FR-07: for aggregate runs |s - c| is 0 inside the stated range."""
        run = make_run(
            is_aggregate=True,
            o2_fraction=0.275,
            varied_parameters={"o2_fraction": {"min": 0.15, "max": 0.40}},
        )
        assert (
            distance(ResolvedScenario(o2_fraction=0.34), run, WORKED_RANGES, DEFAULT_WEIGHTS)
            == 0.0
        )

    def test_fr07_scenario_outside_aggregate_range_uses_nearest_endpoint(
        self, make_run: RunFactory
    ) -> None:
        """FR-07: outside the range the gap is measured to the nearest endpoint."""
        run = make_run(
            is_aggregate=True,
            o2_fraction=0.275,
            varied_parameters={"o2_fraction": {"min": 0.15, "max": 0.40}},
        )
        result = distance(ResolvedScenario(o2_fraction=0.55), run, WORKED_RANGES, DEFAULT_WEIGHTS)
        assert result == pytest.approx(0.15 / 0.75)

    def test_fr07_range_is_read_only_for_aggregate_runs(self, make_run: RunFactory) -> None:
        """FR-07: a non-aggregate run uses its condition value as a point."""
        run = make_run(
            is_aggregate=False,
            o2_fraction=0.21,
            varied_parameters={"o2_fraction": {"min": 0.15, "max": 0.40}},
        )
        result = distance(ResolvedScenario(o2_fraction=0.34), run, WORKED_RANGES, DEFAULT_WEIGHTS)
        assert result == pytest.approx(NUM_O2)

    def test_fr07_aggregate_run_without_stated_range_uses_point(
        self, make_run: RunFactory
    ) -> None:
        """FR-07: an aggregate run without a stated range for the dimension is a point."""
        run = make_run(is_aggregate=True, o2_fraction=0.21)
        result = distance(ResolvedScenario(o2_fraction=0.34), run, WORKED_RANGES, DEFAULT_WEIGHTS)
        assert result == pytest.approx(NUM_O2)

    @pytest.mark.parametrize(
        ("o2_fraction", "expected"),
        [(0.10, 0.0), (0.85, 0.0), (0.95, 0.10 / 0.75)],
    )
    def test_fr07_half_open_range_is_open_on_the_missing_side(
        self, make_run: RunFactory, o2_fraction: float, expected: float
    ) -> None:
        """FR-07: `{min: null, max: 0.85}` is 0 at or below 0.85, else the gap to 0.85."""
        run = make_run(
            is_aggregate=True,
            varied_parameters={"o2_fraction": {"min": None, "max": 0.85}},
        )
        scenario = ResolvedScenario(o2_fraction=o2_fraction)
        result = distance(scenario, run, WORKED_RANGES, DEFAULT_WEIGHTS)
        assert result == pytest.approx(expected)

    def test_fr07_half_open_range_without_maximum(self, make_run: RunFactory) -> None:
        """FR-07: `{min: 0.30, max: null}` is 0 above 0.30 and 0.09 / 0.75 at 0.21."""
        run = make_run(
            is_aggregate=True,
            varied_parameters={"o2_fraction": {"min": 0.30, "max": None}},
        )
        distances = [
            distance(ResolvedScenario(o2_fraction=value), run, WORKED_RANGES, DEFAULT_WEIGHTS)
            for value in (1.0, 0.21)
        ]
        assert distances == pytest.approx([0.0, 0.09 / 0.75])


class TestFuelTiers:
    @pytest.mark.parametrize(
        ("fuel_name", "fuel_phase", "material_class", "expected"),
        [
            ("pmma", "solid", "polymer", 0.0),
            ("polyethylene", "solid", "polymer", 0.3),
            ("cotton", "solid", "fabric", 0.6),
            ("n-heptane", "liquid", "alkane", 1.0),
            (None, None, None, 1.0),
        ],
    )
    def test_fr07_fuel_distance_tiers(
        self,
        make_run: RunFactory,
        fuel_name: str | None,
        fuel_phase: str | None,
        material_class: str | None,
        expected: float,
    ) -> None:
        """FR-07: fuel 0 (material, case-insensitive), 0.3 (class), 0.6 (phase only), 1."""
        run = make_run(fuel_name=fuel_name, fuel_phase=fuel_phase, material_class=material_class)
        scenario = ResolvedScenario(material="PMMA", fuel_phase="solid")
        parts = dimension_distances(scenario, run, WORKED_RANGES, material_class="polymer")
        assert parts == {"fuel": pytest.approx(expected)}

    def test_fr07_no_scenario_fuel_drops_the_fuel_dimension(self, worked_run: RunRecord) -> None:
        """FR-07: fuel is 0 / unset when the scenario gives no fuel; it is not in the mean."""
        parts = dimension_distances(ResolvedScenario(o2_fraction=0.34), worked_run, WORKED_RANGES)
        assert "fuel" not in parts

    @pytest.mark.parametrize(("run_phase", "expected"), [("solid", 0.0), ("liquid", 1.0)])
    def test_fr07_phase_without_material(
        self, make_run: RunFactory, run_phase: str, expected: float
    ) -> None:
        """FR-07: a phase without a material scores 0 for the same phase, 1 otherwise."""
        run = make_run(fuel_name="any fuel", fuel_phase=run_phase)
        parts = dimension_distances(ResolvedScenario(fuel_phase="solid"), run, WORKED_RANGES)
        assert parts == {"fuel": expected}

    def test_fr07_catalog_fuel_supplies_class_and_phase(self, make_run: RunFactory) -> None:
        """FR-07: a named catalog material supplies its material_class and phase."""
        runs = [
            make_run(
                investigation="ALPHA",
                fuel_name="PMMA",
                fuel_phase="solid",
                material_class="polymer",
            ),
            make_run(
                investigation="BRAVO",
                fuel_name="polyethylene",
                fuel_phase="solid",
                material_class="polymer",
            ),
            make_run(
                investigation="CHARLIE",
                fuel_name="cotton",
                fuel_phase="solid",
                material_class="fabric",
            ),
        ]
        scored = score_runs(ResolvedScenario(material="pmma"), runs, WORKED_RANGES)
        fuel_similarity = {run.investigation: parts["fuel"] for run, _, parts in scored}
        assert fuel_similarity == pytest.approx({"ALPHA": 1.0, "BRAVO": 0.7, "CHARLIE": 0.4})


class TestGravityIsNotADistance:
    @pytest.mark.parametrize("gravity", [None, 0.0, 0.166, 0.38, 1.0])
    def test_fr07_gravity_never_changes_similarity(
        self, worked_run: RunRecord, gravity: float | None
    ) -> None:
        """FR-07, ADR-08: gravity is not part of the distance."""
        scenario = _worked_scenario(gravity_g=gravity)
        result = distance(scenario, worked_run, WORKED_RANGES, DEFAULT_WEIGHTS)
        assert 1 - result == pytest.approx(WORKED_SIMILARITY, abs=WORKED_TOLERANCE)


class TestInvestigationMatches:
    def test_fr07_investigation_level_aggregation_and_order(self, make_run: RunFactory) -> None:
        """FR-07: similarity = max, median over runs, matching_runs >= 0.6, sorted."""
        runs = [
            make_run(investigation="BRAVO", o2_fraction=0.34),
            make_run(investigation="BRAVO", o2_fraction=0.85),
            make_run(investigation="BRAVO", o2_fraction=0.10),
            make_run(investigation="ALPHA", o2_fraction=0.34),
            make_run(investigation="CHARLIE", o2_fraction=0.64),
        ]
        matches = rank_matches(ResolvedScenario(o2_fraction=0.34), runs, WORKED_RANGES)
        assert [match.acronym for match in matches] == ["ALPHA", "BRAVO", "CHARLIE"]
        bravo = matches[1]
        assert bravo.similarity == pytest.approx(1.0)
        assert bravo.median_similarity == pytest.approx(1 - 0.24 / 0.75)
        # Run similarities 1.0, 0.32 and 0.68: two reach the 0.6 threshold.
        assert bravo.matching_runs == 2
        assert bravo.per_dimension == pytest.approx({"o2": 1.0})
        assert matches[2].similarity == pytest.approx(1 - 0.30 / 0.75)

    def test_fr07_equal_matches_order_by_case_insensitive_acronym(
        self, make_run: RunFactory
    ) -> None:
        """FR-07, doc 08 s4.2: ties fall back to the doc 05 s4 acronym order."""
        names = ["SLICE", "s-Flame", "FLEX", "Flame-Design"]
        runs = [make_run(investigation=name, o2_fraction=0.34) for name in names]
        matches = rank_matches(ResolvedScenario(o2_fraction=0.34), runs, WORKED_RANGES)
        assert [match.acronym for match in matches] == ["Flame-Design", "FLEX", "s-Flame", "SLICE"]


class TestScenarioInputs:
    def test_fr07_preset_values_resolve(self, presets: Presets) -> None:
        """FR-07: `lunar_habitat` is O2 0.34, 56.5 kPa, 0.166 g, 10 cm/s, assumed default."""
        resolved = resolve_scenario(ScenarioRequest(preset="lunar_habitat"), presets)
        assert (resolved.o2_fraction, resolved.pressure_kpa) == (0.34, 56.5)
        assert (resolved.gravity_g, resolved.flow_speed_cm_s) == (0.166, 10)
        assert resolved.assumed_default is True

    def test_fr07_explicit_values_override_preset(self, presets: Presets) -> None:
        """FR-07: explicit values win; an edited preset is no longer an assumed default."""
        resolved = resolve_scenario(
            ScenarioRequest(preset="lunar_habitat", o2_fraction=0.4), presets
        )
        assert resolved.o2_fraction == 0.4
        assert resolved.pressure_kpa == 56.5
        assert resolved.assumed_default is False

    @pytest.mark.parametrize(
        ("preset", "assumed"),
        [
            ("lunar_habitat", True),
            ("mars_habitat", True),
            ("lunar_habitat_threshold", False),
            ("iss_cabin", False),
            ("spacesuit", False),
        ],
    )
    def test_fr07_assumed_default_flags(
        self, presets: Presets, preset: str, assumed: bool
    ) -> None:
        """FR-07: only lunar_habitat and mars_habitat are assumed defaults (doc 08 s4.1)."""
        assert resolve_scenario(ScenarioRequest(preset=preset), presets).assumed_default is assumed

    @pytest.mark.parametrize(
        "request_body", [ScenarioRequest(preset="moon_base"), ScenarioRequest()]
    )
    def test_fr07_unknown_or_empty_scenario_is_bad_request(
        self, presets: Presets, request_body: ScenarioRequest
    ) -> None:
        """FR-07: an unknown preset, or neither a preset nor a value, is HTTP 400."""
        with pytest.raises(ValidationError):
            resolve_scenario(request_body, presets)

    def test_fr07_scenario_id_is_unpadded_base64url_of_canonical_json(self) -> None:
        """FR-07: scenario_id = base64url_nopad(json(resolved, sort_keys, compact))."""
        scenario = _worked_scenario(gravity_g=0.166)
        canonical = json.dumps(
            scenario.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        expected = base64.urlsafe_b64encode(canonical.encode()).decode().rstrip("=")
        assert scenario_id_of(scenario) == expected
        assert "=" not in scenario_id_of(scenario)

    def test_fr07_scenario_id_round_trips(self) -> None:
        """FR-07: the id is stateless and invertible."""
        scenario = _worked_scenario(preset="lunar_habitat", assumed_default=False)
        assert scenario_from_id(scenario_id_of(scenario)) == scenario

    @pytest.mark.parametrize(
        "bad_id",
        [
            "not*base64",
            _encode(b"[1]"),
            _encode(b'{"o2_fraction": "high"}'),
            _encode(b'{"unknown_field": 1}'),
        ],
    )
    def test_fr08_invalid_scenario_id_is_bad_request(self, bad_id: str) -> None:
        """FR-08: an id that does not decode to a resolved scenario object is HTTP 400."""
        with pytest.raises(ValidationError):
            scenario_from_id(bad_id)
