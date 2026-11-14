"""FR-01, FR-02, FR-06, FR-12: `CatalogService` over fake repositories (doc 05 s4).

Summaries, score sorting and pagination, detail assembly, run pages, the varied / fixed
variables derivation, facets, the hardware lineage graph with project edges, and projects.
Acronyms are placeholders; no scientific fact is implied.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from flamescope_api.repositories.runs import RunRecord
from flamescope_api.services.catalog import CatalogService, derive_variables
from flamescope_common.schemas.api import (
    InvestigationFilters,
    LineageEdge,
    LineageNode,
    PageRequest,
    ScoreSet,
)
from flamescope_common.schemas.card import CardVariables

pytestmark = pytest.mark.unit

RunFactory = Callable[..., RunRecord]
RowFactory = Callable[..., SimpleNamespace]
SOURCE = {"kind": "psi_page", "uri": "https://psi.nasa.gov/test", "locator": "page 1"}
SCORES = {
    1: ScoreSet(overall=40.0),
    2: ScoreSet(overall=80.0),
    3: ScoreSet(overall=None),
    4: ScoreSet(overall=80.0),
}


class FakeInvestigationRepo:
    """`InvestigationRepo` stand-in holding fixed rows and related records."""

    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.search_pages: list[PageRequest | None] = []

    def search(self, filters: InvestigationFilters, page: PageRequest | None) -> Any:
        self.search_pages.append(page)
        window = (
            self.rows if page is None else self.rows[page.offset : page.offset + page.page_size]
        )
        return SimpleNamespace(rows=window, total=len(self.rows))

    def get(self, id_or_acronym: str) -> SimpleNamespace:
        return next(row for row in self.rows if row.investigation.acronym == id_or_acronym)

    def findings(self, categories: Any, acronyms: list[str] | None) -> list[SimpleNamespace]:
        finding = SimpleNamespace(
            id=11, statement="A stated finding.", category="fundamental", source=SOURCE,
            confidence=0.8,
        )  # fmt: skip
        return [SimpleNamespace(finding=finding, acronym=acronyms[0] if acronyms else "ALPHA")]

    def publications(self, investigation_id: int) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                doi="10.0000/test", title="Paper", authors=["A. Author"], year=2020,
                venue="Journal", url="https://doi.org/10.0000/test", key_findings=None,
            )
        ]  # fmt: skip

    def measurements(self, investigation_id: int) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                instrument="camera", quantity="flame length", units="mm", file_pattern=None,
                notes="", source=SOURCE,
            )
        ]  # fmt: skip

    def facet_counts(self) -> dict[str, list[tuple[str, int]]]:
        return {"fuel_phase": [("solid", 2), ("gas", 1)], "tag": [("flame_spread", 3)]}

    def hardware_links(self) -> SimpleNamespace:
        hardware = [
            SimpleNamespace(id=1, name="CIR", kind="facility", parent_id=None),
            SimpleNamespace(id=2, name="MDCA", kind="insert", parent_id=1),
        ]
        return SimpleNamespace(
            hardware=hardware,
            links=[("FLEX", "MDCA", "apparatus")],
            projects={"FLEX": "ACME", "SOLO": None},
        )

    def projects(self) -> list[tuple[SimpleNamespace, list[str]]]:
        return [(SimpleNamespace(name="ACME", description="Project."), ["FLEX", "SOLO"])]


class FakeRunRepo:
    def __init__(self, runs: list[RunRecord]) -> None:
        self._runs = runs

    def for_investigation(self, investigation_id: int) -> list[RunRecord]:
        return [run for run in self._runs if run.investigation_id == investigation_id]


class FakeRanking:
    def score_sets(self, investigation_ids: list[int]) -> dict[int, ScoreSet]:
        return {key: SCORES[key] for key in investigation_ids if key in SCORES}

    def breakdown(self, investigation_id: int) -> dict[str, Any]:
        return {}


@pytest.fixture
def rows(make_investigation_row: RowFactory) -> list[SimpleNamespace]:
    built = [
        make_investigation_row(acronym, identifier)
        for identifier, acronym in enumerate(("ALPHA", "BRAVO", "CHARLIE", "DELTA"), 1)
    ]
    first = built[0].investigation
    first.o2_min, first.o2_max = 0.14, 0.21
    first.pressure_min_kpa = 101.3
    return built


@pytest.fixture
def runs(make_run: RunFactory) -> list[RunRecord]:
    return [
        make_run(investigation_id=1, label="R1", o2_fraction=0.21, pressure_kpa=101.3),
        make_run(investigation_id=1, label="R2", o2_fraction=0.14, pressure_kpa=101.3),
        make_run(investigation_id=1, label="R3", o2_fraction=0.17, pressure_kpa=101.3),
    ]


@pytest.fixture
def repo(rows: list[SimpleNamespace]) -> FakeInvestigationRepo:
    return FakeInvestigationRepo(rows)


@pytest.fixture
def service(repo: FakeInvestigationRepo, runs: list[RunRecord]) -> CatalogService:
    return CatalogService(repo, FakeRunRepo(runs), FakeRanking())  # type: ignore[arg-type]


class TestList:
    def test_fr02_acronym_sort_pages_in_the_repository(
        self, service: CatalogService, repo: FakeInvestigationRepo
    ) -> None:
        """FR-02: the default sort is delegated to the repository with the page."""
        page = PageRequest(page=1, page_size=2)
        result = service.list(InvestigationFilters(), page)
        observed = ([item.acronym for item in result.items], result.total, repo.search_pages)
        assert observed == (["ALPHA", "BRAVO"], 4, [page])

    def test_fr02_summary_ranges_keep_open_ends(self, service: CatalogService) -> None:
        """FR-02, doc 05 s4: `[min, max]`; a null end stays null (open); no data is null."""
        first = service.list(InvestigationFilters(), PageRequest()).items[0]
        observed = (
            first.o2_range,
            first.pressure_range_kpa,
            first.flow_range_cm_s,
            first.scores.overall,
        )
        assert observed == ((0.14, 0.21), (101.3, None), None, 40.0)

    def test_fr02_score_sort_is_descending_nulls_last_then_acronym(
        self, service: CatalogService
    ) -> None:
        """FR-02: score sorts are descending with nulls last; ties fall back to acronym."""
        result = service.list(InvestigationFilters(), PageRequest(sort="overall"))
        assert [item.acronym for item in result.items] == ["BRAVO", "DELTA", "ALPHA", "CHARLIE"]

    def test_fr02_score_sort_paginates_after_sorting(self, service: CatalogService) -> None:
        """FR-02: page 2 of size 2 holds the third and fourth ranked investigations."""
        result = service.list(
            InvestigationFilters(), PageRequest(sort="overall", page=2, page_size=2)
        )
        assert ([item.acronym for item in result.items], result.total) == (["ALPHA", "CHARLIE"], 4)


class TestDetail:
    def test_fr01_detail_combines_card_runs_and_related_records(
        self, service: CatalogService
    ) -> None:
        """FR-01: detail = summary + card, publications, measurements, findings, run count."""
        detail = service.get("ALPHA")
        observed = (
            detail.card.acronym,
            detail.run_count,
            [entry.id for entry in detail.findings],
            [entry.doi for entry in detail.publications],
            [entry.quantity for entry in detail.measurements],
        )
        assert observed == ("ALPHA", 3, [11], ["10.0000/test"], ["flame length"])

    def test_fr06_runs_are_paginated(self, service: CatalogService) -> None:
        """FR-06: `/runs` pages over the investigation's runs."""
        result = service.runs("ALPHA", PageRequest(page=2, page_size=1))
        assert ([item.label for item in result.items], result.total) == (["R2"], 3)

    def test_fr01_publications(self, service: CatalogService) -> None:
        assert [entry.title for entry in service.publications("ALPHA")] == ["Paper"]


class TestVariables:
    def test_fr06_varied_and_fixed_parameters(self, service: CatalogService) -> None:
        """FR-06: several distinct values are varied (sorted), one value is fixed."""
        result = service.variables("ALPHA")
        varied = {entry.name: (entry.values, entry.unit) for entry in result.varied}
        fixed = {entry.name: (entry.value, entry.unit) for entry in result.fixed}
        assert (varied, fixed, result.run_count) == (
            {"o2_fraction": ([0.14, 0.17, 0.21], "fraction")},
            {"pressure_kpa": (101.3, "kPa")},
            3,
        )

    def test_fr06_declared_parameters_without_runs_are_listed_without_values(self) -> None:
        """FR-06: card-declared parameters not seen in runs appear with no values."""
        declared = CardVariables(varied=["e_field_kv"], fixed=["gravity_g"])
        result = derive_variables([], declared)
        observed = (
            [(entry.name, entry.values) for entry in result.varied],
            [(entry.name, entry.value) for entry in result.fixed],
            result.run_count,
        )
        assert observed == ([("e_field_kv", [])], [("gravity_g", None)], 0)

    def test_fr06_stated_lists_count_as_distinct_values(self, make_run: RunFactory) -> None:
        """FR-06: list-valued `varied_parameters` contribute each element once."""
        run = make_run(varied_parameters={"sample_width_mm": [10, 10.0, 20]})
        result = derive_variables([run], CardVariables())
        assert [(entry.name, entry.values) for entry in result.varied] == [
            ("sample_width_mm", [10, 20])
        ]


class TestFacetsLineageProjects:
    def test_fr02_facets_carry_value_counts(self, service: CatalogService) -> None:
        facets = service.facets()
        observed = (
            [(entry.value, entry.count) for entry in facets.fuel_phase],
            [(entry.value, entry.count) for entry in facets.tag],
            facets.hardware,
        )
        assert observed == ([("solid", 2), ("gas", 1)], [("flame_spread", 3)], [])

    def test_fr12_lineage_nodes(self, service: CatalogService) -> None:
        """FR-12: `hw:`, `inv:` and `proj:` nodes as in document 05 section 4."""
        assert service.hardware_lineage().nodes == [
            LineageNode(id="hw:CIR", type="hardware", label="CIR", kind="facility"),
            LineageNode(id="hw:MDCA", type="hardware", label="MDCA", kind="insert"),
            LineageNode(id="inv:FLEX", type="investigation", label="FLEX"),
            LineageNode(id="inv:SOLO", type="investigation", label="SOLO"),
            LineageNode(id="proj:ACME", type="project", label="ACME"),
        ]

    def test_fr12_lineage_edges_include_hosting_and_project_membership(
        self, service: CatalogService
    ) -> None:
        """FR-12: apparatus, `hosted_in` and `member_of` edges; no edge for a null project."""
        assert service.hardware_lineage().edges == [
            LineageEdge(source="inv:FLEX", target="hw:MDCA", role="apparatus"),
            LineageEdge(source="hw:MDCA", target="hw:CIR", role="hosted_in"),
            LineageEdge(source="inv:FLEX", target="proj:ACME", role="member_of"),
        ]

    def test_fr12_projects_list_members(self, service: CatalogService) -> None:
        project = service.projects()[0]
        assert (project.name, project.investigations) == ("ACME", ["FLEX", "SOLO"])
