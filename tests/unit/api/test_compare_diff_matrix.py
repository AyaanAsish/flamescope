"""FR-05: compare matrix order, `same` flags, shared facts and narrative states (doc 05 s6)."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from flamescope_agents.citation_verifier import CitationVerifier
from flamescope_api.services.compare import CompareService, diff_matrix, shared_facts
from flamescope_common.errors import LLMError, NotFoundError, ValidationError
from flamescope_common.schemas.agents import ComparatorOutput, SentenceWithFacts
from flamescope_common.schemas.api import ScoreSet
from flamescope_common.schemas.card import InvestigationCard

pytestmark = pytest.mark.unit

RowFactory = Callable[..., SimpleNamespace]
SOURCE = {"kind": "psi_page", "uri": "https://psi.nasa.gov/test"}
# Document 05 section 6, in order.
MATRIX_ATTRIBUTES = [
    "project",
    "platform",
    "gravity_level",
    "hardware",
    "fuel_phase",
    "fuel_materials",
    "geometry",
    "o2_range",
    "pressure_range_kpa",
    "flow_range_cm_s",
    "flow_direction",
    "varied_parameters",
    "measurements",
    "phenomena",
    "data_volume",
]


def _card(acronym: str, **fields: Any) -> dict[str, Any]:
    return {"acronym": acronym, "title": f"{acronym} title", **fields}


def _fuel(name: str, phase: str) -> dict[str, Any]:
    return {"name": name, "phase": phase, "source": SOURCE}


ALPHA = _card(
    "ALPHA",
    platform="ISS",
    hardware=[{"name": "RACK", "role": "host"}, {"name": "DUCT", "role": "apparatus"}],
    fuels=[_fuel("fuel-a", "solid")],
    conditions={"o2_fraction": {"min": 0.15, "max": 0.21, "source": SOURCE}},
    measurements=[{"instrument": "camera", "quantity": "spread rate", "source": SOURCE}],
    fire_safety_tags=["extinction", "flame_spread"],
)
BRAVO = _card(
    "BRAVO",
    platform="ISS",
    hardware=[{"name": "RACK", "role": "host"}],
    fuels=[_fuel("fuel-b", "liquid")],
    conditions={"o2_fraction": {"min": 0.15, "max": 0.21, "source": SOURCE}},
    measurements=[{"instrument": "camera", "quantity": "burn rate", "source": SOURCE}],
    fire_safety_tags=["extinction"],
)


def _cards(*raw: dict[str, Any]) -> list[InvestigationCard]:
    return [InvestigationCard.model_validate(card) for card in raw]


def _row(matrix: list[Any], attribute: str) -> Any:
    return next(row for row in matrix if row.attribute == attribute)


class TestDiffMatrix:
    def test_fr05_attribute_order_equals_document(self) -> None:
        """FR-05: matrix attributes in the order of document 05 section 6."""
        matrix = diff_matrix(_cards(ALPHA, BRAVO))
        assert [row.attribute for row in matrix] == MATRIX_ATTRIBUTES

    def test_fr05_values_are_keyed_by_acronym(self) -> None:
        """FR-05: `values` maps each acronym to its attribute value."""
        row = _row(diff_matrix(_cards(ALPHA, BRAVO)), "fuel_phase")
        assert row.values == {"ALPHA": ["solid"], "BRAVO": ["liquid"]}
        assert row.group == "fuel"
        assert row.label == "Fuel phase"

    @pytest.mark.parametrize(
        ("attribute", "same"),
        [
            ("platform", True),
            ("project", True),
            ("o2_range", True),
            ("fuel_phase", False),
            ("hardware", False),
            ("phenomena", False),
        ],
    )
    def test_fr05_same_flags(self, attribute: str, same: bool) -> None:
        """FR-05: `same` is true only when every investigation has the same value."""
        assert _row(diff_matrix(_cards(ALPHA, BRAVO)), attribute).same is same

    def test_fr05_three_cards_any_difference_is_not_same(self) -> None:
        """FR-05: one differing card among three makes the row differ."""
        charlie = _card("CHARLIE", platform="drop_tower")
        assert _row(diff_matrix(_cards(ALPHA, BRAVO, charlie)), "platform").same is False

    def test_fr05_ranges_are_pairs(self) -> None:
        """FR-05: range attributes are `[min, max]` or null."""
        matrix = diff_matrix(_cards(ALPHA, _card("CHARLIE")))
        assert _row(matrix, "o2_range").values == {"ALPHA": [0.15, 0.21], "CHARLIE": None}

    def test_fr05_half_open_range_keeps_its_null_end(self) -> None:
        """FR-05, doc 04 s2: a stated `{min: null, max}` is `[null, max]`, never a point."""
        delta = _card("DELTA", conditions={"o2_fraction": {"max": 0.85, "source": SOURCE}})
        matrix = diff_matrix(_cards(ALPHA, delta))
        assert _row(matrix, "o2_range").values == {"ALPHA": [0.15, 0.21], "DELTA": [None, 0.85]}


class TestSharedFacts:
    def test_fr12_shared_hardware_tags_and_instruments(self) -> None:
        """FR-05, FR-12: hardware, tags and instruments present in every investigation."""
        shared = shared_facts(_cards(ALPHA, BRAVO))
        assert shared.hardware == ["RACK"]
        assert shared.tags == ["extinction"]
        assert shared.instruments == ["camera"]

    def test_fr12_nothing_shared(self) -> None:
        """FR-05: disjoint cards share nothing."""
        shared = shared_facts(_cards(ALPHA, _card("CHARLIE")))
        assert (shared.hardware, shared.tags, shared.instruments) == ([], [], [])


class FakeInvestigationRepo:
    def __init__(self, rows: dict[str, SimpleNamespace]) -> None:
        self._rows = rows

    def get(self, id_or_acronym: str) -> SimpleNamespace:
        row = self._rows.get(id_or_acronym.upper())
        if row is None:
            raise NotFoundError(f"Investigation {id_or_acronym!r} not found")
        return row


class FakeRanking:
    def score_sets(self, investigation_ids: Any = None) -> dict[int, ScoreSet]:
        return {}


class FixedComparator:
    """Orchestrator stand-in returning one comparator output, or raising `LLMError`."""

    def __init__(self, output: ComparatorOutput | None = None) -> None:
        self._output = output
        self.payloads: list[Any] = []

    async def run(self, name: str, payload: Any, *, stream: bool = False) -> Any:
        self.payloads.append(payload)
        if self._output is None:
            raise LLMError("provider down")
        return self._output


SUPPORTED = "ALPHA burns fuel-a as a solid fuel."
UNSUPPORTED = [
    SentenceWithFacts(text="BRAVO burns 42 kinds of plasma.", fact_ids=["F1"]),
    SentenceWithFacts(text="Uncited claim without facts."),
    SentenceWithFacts(text="Claim citing an unknown fact.", fact_ids=["F99"]),
    SentenceWithFacts(text="Another claim citing an unknown fact.", fact_ids=["F98"]),
]
COMPARATOR_SENTENCES = 4  # the comparator contract asks for at least four (document 07)


def _comparator_output(supported: list[SentenceWithFacts]) -> ComparatorOutput:
    padding = UNSUPPORTED[: COMPARATOR_SENTENCES - len(supported)]
    return ComparatorOutput(sentences=[*supported, *padding])


def _build_service(rows: dict[str, SimpleNamespace], orchestrator: Any) -> CompareService:
    return CompareService(
        FakeInvestigationRepo(rows),  # type: ignore[arg-type]
        FakeRanking(),  # type: ignore[arg-type]
        orchestrator,
        CitationVerifier(),
    )


@pytest.fixture
def compare_rows(make_investigation_row: RowFactory) -> dict[str, SimpleNamespace]:
    return {
        "ALPHA": make_investigation_row("ALPHA", 1, ALPHA),
        "BRAVO": make_investigation_row("BRAVO", 2, BRAVO),
    }


@pytest.fixture
def compare_service(compare_rows: dict[str, SimpleNamespace]) -> CompareService:
    return _build_service(compare_rows, FixedComparator())


class TestCompareService:
    @pytest.mark.parametrize("ids", [["ALPHA"], ["A", "B", "C", "D", "E"], []])
    async def test_fr05_fewer_than_2_or_more_than_4_ids_is_bad_request(
        self, compare_service: CompareService, ids: list[str]
    ) -> None:
        """FR-05: compare accepts 2 to 4 IDs; otherwise HTTP 400 `bad_request`."""
        with pytest.raises(ValidationError):
            await compare_service.compare(ids, False)

    async def test_fr05_narrative_false_is_skipped(self, compare_service: CompareService) -> None:
        """FR-05: `narrative=false` gives status `skipped` with the matrix."""
        response = await compare_service.compare(["ALPHA", "BRAVO"], False)
        assert response.narrative.status == "skipped"
        assert [summary.acronym for summary in response.investigations] == ["ALPHA", "BRAVO"]
        assert [row.attribute for row in response.matrix] == MATRIX_ATTRIBUTES
        assert response.shared.hardware == ["RACK"]

    async def test_fr05_llm_failure_is_unavailable_not_an_error(
        self, compare_service: CompareService
    ) -> None:
        """FR-05: when the LLM fails the response is still complete, narrative `unavailable`."""
        response = await compare_service.compare(["ALPHA", "BRAVO"], True)
        assert response.narrative.status == "unavailable"
        assert len(response.matrix) == len(MATRIX_ATTRIBUTES)

    async def test_fr05_unknown_investigation_is_not_found(
        self, compare_service: CompareService
    ) -> None:
        """FR-05: an unknown ID is `NotFoundError` (HTTP 404)."""
        with pytest.raises(NotFoundError):
            await compare_service.compare(["ALPHA", "ZULU"], False)

    async def test_fr05_narrative_keeps_only_verified_cited_sentences(
        self, compare_rows: dict[str, SimpleNamespace]
    ) -> None:
        """FR-05: narrative sentences are verified against card facts and carry citations."""
        output = _comparator_output([SentenceWithFacts(text=SUPPORTED, fact_ids=["F1"])])
        service = _build_service(compare_rows, FixedComparator(output))
        narrative = (await service.compare(["ALPHA", "BRAVO"], True)).narrative
        assert narrative.status == "ok"
        assert [sentence.text for sentence in narrative.sentences] == [SUPPORTED]
        assert narrative.sentences[0].citations[0].uri == SOURCE["uri"]
        assert narrative.text == SUPPORTED

    async def test_fr05_narrative_without_supported_sentence_is_unavailable(
        self, compare_rows: dict[str, SimpleNamespace]
    ) -> None:
        """FR-05: when no sentence survives verification the narrative is `unavailable`."""
        service = _build_service(compare_rows, FixedComparator(_comparator_output([])))
        assert (await service.compare(["ALPHA", "BRAVO"], True)).narrative.status == "unavailable"
