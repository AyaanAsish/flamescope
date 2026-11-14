"""FR-07, FR-16: gravity bounding for 0, 1, 0.166 and 0.38 g (document 08 section 4.4)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from flamescope_api.repositories.runs import RunRecord
from flamescope_api.services.scenario import ScenarioService, gravity_bounding
from flamescope_api.services.scenario_math import score_runs
from flamescope_common.rubric import Presets
from flamescope_common.schemas.api import (
    GravityAnalogue,
    RangePair,
    ResolvedScenario,
    ScenarioRequest,
)

pytestmark = pytest.mark.unit

RunFactory = Callable[..., RunRecord]
RANGES: dict[str, RangePair] = {"o2_fraction": (0.10, 0.85)}
ANALOGUE = GravityAnalogue(acronym="ANALOGUE", note="Analogue note.")
STATEMENT = "Fixed gravity statement."
LUNAR_G = 0.166
MARS_G = 0.38


@pytest.fixture
def bounded_runs(make_run: RunFactory) -> list[RunRecord]:
    """Runs at 0 g (one within tolerance) and at 1 g, with no partial-gravity data."""
    return [
        make_run(investigation="ZERO", gravity_g=0.0, o2_fraction=0.21),
        make_run(investigation="NEARZERO", gravity_g=0.015, o2_fraction=0.21),
        make_run(investigation="ONE", gravity_g=1.0, o2_fraction=0.21),
        make_run(investigation="NOGRAV", gravity_g=None, o2_fraction=0.21),
    ]


class TestCatalogGravity:
    @pytest.mark.parametrize("gravity", [0.0, 1.0])
    def test_fr16_catalog_gravity_is_not_partial(
        self, bounded_runs: list[RunRecord], gravity: float
    ) -> None:
        """FR-16: g in catalog values -> partial_gravity_data = (0 < g < 1) = false."""
        result = gravity_bounding(ResolvedScenario(gravity_g=gravity), bounded_runs)
        assert result.partial_gravity_data is False
        assert result.lower_bound is None
        assert result.upper_bound is None

    @pytest.mark.parametrize("gravity", [0.0, 0.015, 0.99, 1.0, 1.01])
    def test_fr16_reference_gravity_has_no_gap_statement_without_catalog_runs(
        self, make_run: RunFactory, gravity: float
    ) -> None:
        """FR-16: within 0.02 g of 0 or 1 is not partial gravity, even with no gravity runs."""
        runs = [make_run(gravity_g=None, o2_fraction=0.21)]
        result = gravity_bounding(
            ResolvedScenario(gravity_g=gravity), runs, analogue=ANALOGUE, statement=STATEMENT
        )
        expected = (False, None, None, None, None)
        actual = (
            result.partial_gravity_data,
            result.lower_bound,
            result.upper_bound,
            result.analogue,
            result.statement,
        )
        assert actual == expected

    @pytest.mark.parametrize("gravity", [0.03, 0.97])
    def test_fr16_just_outside_reference_tolerance_is_bounded(
        self, make_run: RunFactory, gravity: float
    ) -> None:
        """FR-16: beyond 0.02 g of 0 and 1 the gap statement applies (doc 08 s4.4)."""
        runs = [make_run(gravity_g=None, o2_fraction=0.21)]
        result = gravity_bounding(ResolvedScenario(gravity_g=gravity), runs, statement=STATEMENT)
        assert (result.partial_gravity_data, result.statement) == (False, STATEMENT)

    def test_fr16_partial_gravity_run_within_tolerance(self, make_run: RunFactory) -> None:
        """FR-16: a run within 0.02 g of the scenario gravity is partial-gravity data."""
        runs = [make_run(gravity_g=0.17)]
        result = gravity_bounding(ResolvedScenario(gravity_g=LUNAR_G), runs)
        assert result.partial_gravity_data is True

    def test_fr16_scenario_without_gravity(self, bounded_runs: list[RunRecord]) -> None:
        """FR-16: no scenario gravity, nothing to bound."""
        result = gravity_bounding(ResolvedScenario(o2_fraction=0.3), bounded_runs)
        assert result.partial_gravity_data is False
        assert result.statement is None


class TestBounds:
    @pytest.mark.parametrize("gravity", [LUNAR_G, MARS_G])
    def test_fr16_partial_gravity_is_bounded_by_0_and_1_g(
        self, bounded_runs: list[RunRecord], gravity: float
    ) -> None:
        """FR-16: 0 g and 1 g investigations (tolerance 0.02 g) bound the behaviour."""
        result = gravity_bounding(
            ResolvedScenario(gravity_g=gravity),
            bounded_runs,
            analogue=ANALOGUE,
            statement=STATEMENT,
        )
        assert result.partial_gravity_data is False
        assert result.lower_bound is not None
        assert result.upper_bound is not None
        assert result.lower_bound.gravity_g == 0
        assert result.lower_bound.investigations == ["NEARZERO", "ZERO"]
        assert result.upper_bound.gravity_g == 1
        assert result.upper_bound.investigations == ["ONE"]
        assert result.analogue == ANALOGUE
        assert result.statement == STATEMENT

    def test_fr16_bounds_only_name_top_matches(self, bounded_runs: list[RunRecord]) -> None:
        """FR-16: bounds list investigations among the top matches only."""
        result = gravity_bounding(
            ResolvedScenario(gravity_g=LUNAR_G), bounded_runs, top_acronyms={"ZERO"}
        )
        assert result.lower_bound is not None
        assert result.upper_bound is not None
        assert result.lower_bound.investigations == ["ZERO"]
        assert result.upper_bound.investigations == []


class TestStatement:
    @pytest.mark.parametrize(("gravity", "text"), [(LUNAR_G, "0.166"), (MARS_G, "0.38")])
    def test_fr16_statement_names_scenario_gravity(
        self, presets: Presets, gravity: float, text: str
    ) -> None:
        """FR-16: template placeholder `{gravity_g}` formatted with `:g`; names LUCI and FM2."""
        statement = presets.gravity_bounding_statement(gravity)
        assert statement.startswith(f"The scenario gravity is {text} g.")
        assert "LUCI" in statement
        assert "FM2" in statement
        assert "{gravity_g}" not in statement


class TestGravityAndSimilarity:
    @pytest.mark.parametrize("gravity", [0.0, 1.0, LUNAR_G, MARS_G])
    def test_fr07_gravity_never_changes_similarity(
        self, bounded_runs: list[RunRecord], gravity: float
    ) -> None:
        """FR-07, ADR-08: run similarities are identical with or without scenario gravity."""
        with_gravity = score_runs(
            ResolvedScenario(o2_fraction=0.3, gravity_g=gravity), bounded_runs, RANGES
        )
        without = score_runs(ResolvedScenario(o2_fraction=0.3), bounded_runs, RANGES)
        assert [entry[1] for entry in with_gravity] == [entry[1] for entry in without]


class TestScenarioService:
    async def test_fr16_lunar_preset_states_the_gap(
        self,
        presets: Presets,
        bounded_runs: list[RunRecord],
        make_scenario_service: Callable[..., ScenarioService],
    ) -> None:
        """FR-16: lunar gravity -> no_data coverage, bounds, analogue and fixed statement."""
        service = make_scenario_service(bounded_runs, RANGES)
        response = await service.match(
            ScenarioRequest(preset="lunar_habitat", explain=False), False
        )
        assert response.coverage["gravity_g"].state == "no_data"
        assert response.coverage["gravity_g"].catalog_values == [0.0, 0.015, 1.0]
        bounding = response.gravity_bounding
        assert bounding.partial_gravity_data is False
        assert bounding.statement == presets.gravity_bounding_statement(LUNAR_G)
        assert bounding.analogue == GravityAnalogue(acronym="ANALOGUE", note="Analogue objective.")
        assert response.explanation.status == "skipped"
        assert response.scenario.assumed_default is True

    async def test_fr07_gravity_only_scenario_has_no_matches(
        self,
        bounded_runs: list[RunRecord],
        make_scenario_service: Callable[..., ScenarioService],
    ) -> None:
        """FR-07: a scenario that sets only gravity_g has an empty `matches` list."""
        service = make_scenario_service(bounded_runs, RANGES)
        response = await service.match(ScenarioRequest(gravity_g=MARS_G), True)
        assert response.matches == []
        assert response.explanation.status == "skipped"
