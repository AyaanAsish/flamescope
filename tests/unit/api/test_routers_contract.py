"""Routers contract: every endpoint of document 05 section 11 with fake services (doc 12 s1).

Requirements: FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09, FR-10, FR-11,
FR-12, FR-13, FR-14. Services are replaced through FastAPI dependency overrides; no database.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flamescope_api import deps
from flamescope_api.services.compare import CompareService
from flamescope_api.services.extract import ExportFile
from flamescope_api.services.meta import Readiness
from flamescope_api.sse import sse_event
from flamescope_common.schemas.api import (
    AskDone,
    ColumnInfo,
    CompareResponse,
    ComponentStatus,
    DictionaryResponse,
    EarthApplicationsResponse,
    FacetsResponse,
    GapItem,
    GapsResponse,
    GravityBounding,
    InvestigationDetail,
    InvestigationSummary,
    LineageGraph,
    Narrative,
    Page,
    ProjectOut,
    PublicationOut,
    RankItem,
    RankResponse,
    ReadyResponse,
    ResolvedScenario,
    RunItem,
    SafetyTechResponse,
    ScenarioResponse,
    SharedFacts,
    StatsResponse,
    StatusResponse,
    Table,
    VariablesResponse,
    WeightsUsed,
)
from flamescope_common.schemas.card import InvestigationCard

pytestmark = pytest.mark.unit

API = "/api/v1"
# Document 05 section 11, the 24 endpoints.
ENDPOINT_INVENTORY = {
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/meta/stats"),
    ("GET", "/meta/status"),
    ("GET", "/meta/rubric"),
    ("GET", "/meta/presets"),
    ("GET", "/investigations"),
    ("GET", "/investigations/{id}"),
    ("GET", "/investigations/{id}/runs"),
    ("GET", "/investigations/{id}/variables"),
    ("GET", "/investigations/{id}/publications"),
    ("GET", "/facets"),
    ("GET", "/hardware"),
    ("GET", "/projects"),
    ("POST", "/rank"),
    ("POST", "/compare"),
    ("POST", "/scenario"),
    ("POST", "/extract/preview"),
    ("POST", "/extract/export"),
    ("GET", "/extract/dictionary"),
    ("GET", "/insights/safety-tech"),
    ("GET", "/insights/gaps"),
    ("GET", "/earth-applications"),
    ("POST", "/ask"),
}
INVENTORY_SIZE = 24
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100
RANKED_ITEMS = 5
SUMMARY = InvestigationSummary(id=1, acronym="ALPHA", title="ALPHA title")


def _summary_fields() -> dict[str, Any]:
    return SUMMARY.model_dump()


class FakeCatalog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def list(self, filters: Any, page: Any) -> Page[InvestigationSummary]:
        self.calls.append(("list", (filters, page)))
        return Page(items=[SUMMARY], page=page.page, page_size=page.page_size, total=1)

    def get(self, investigation_id: str) -> InvestigationDetail:
        self.calls.append(("get", investigation_id))
        card = InvestigationCard(acronym="ALPHA", title="ALPHA title")
        return InvestigationDetail(**_summary_fields(), card=card)

    def runs(self, investigation_id: str, page: Any) -> Page[RunItem]:
        self.calls.append(("runs", page))
        run = RunItem(id=1, label="run 1")
        return Page(items=[run], page=page.page, page_size=page.page_size, total=1)

    def variables(self, investigation_id: str) -> VariablesResponse:
        return VariablesResponse(run_count=1)

    def publications(self, investigation_id: str) -> builtins.list[PublicationOut]:
        return [PublicationOut(title="Publication")]

    def facets(self) -> FacetsResponse:
        return FacetsResponse()

    def hardware_lineage(self) -> LineageGraph:
        return LineageGraph()

    def projects(self) -> builtins.list[ProjectOut]:
        return [ProjectOut(name="PROJECT", investigations=["ALPHA"])]


class FakeMeta:
    def __init__(self, is_ready: bool = True) -> None:
        self._is_ready = is_ready

    def stats(self) -> StatsResponse:
        return StatsResponse(
            investigations=1,
            test_runs=1,
            publications=0,
            findings=0,
            chunks=0,
            hardware=0,
            fuel_phase_counts={"solid": 1},
            o2_range=(None, None),
            pressure_range_kpa=(None, None),
            rubric_version="2026.11-1",
        )

    def status(self) -> StatusResponse:
        return StatusResponse(components=[ComponentStatus(id="C-API", status="up")])

    def ready(self) -> Readiness:
        count = 1 if self._is_ready else 0
        report = ReadyResponse(db=self._is_ready, migrations=None, investigations=count)
        return Readiness(report=report, is_ready=self._is_ready)


class FakeRanking:
    def rank(self, lens: Any, weights: Any, preset: Any, filters: Any) -> RankResponse:
        items = [
            RankItem(
                rank=n, acronym=f"INV{n}", title="t", score=None, confidence=0, lens_scores={}
            )
            for n in range(1, RANKED_ITEMS + 1)
        ]
        used = WeightsUsed(lens_weights={}, criterion_weights={})
        return RankResponse(lens=lens, rubric_version="2026.11-1", weights_used=used, items=items)


class FakeCompare:
    async def compare(self, ids: Any, narrative: bool) -> CompareResponse:
        return CompareResponse(
            investigations=[SUMMARY],
            matrix=[],
            shared=SharedFacts(),
            narrative=Narrative(status="ok" if narrative else "skipped"),
        )


class FakeScenario:
    async def match(self, scenario: Any, explain: bool) -> ScenarioResponse:
        return ScenarioResponse(
            scenario=ResolvedScenario(o2_fraction=scenario.o2_fraction),
            coverage={},
            matches=[],
            gravity_bounding=GravityBounding(partial_gravity_data=False),
            explanation=Narrative(status="skipped"),
            scenario_id="e30",
        )


class FakeExtract:
    def preview(self, query: Any) -> Table:
        return Table(
            columns=[ColumnInfo(name="investigation", label="Investigation")],
            rows=[["A"]],
            total=1,
        )

    def export(self, query: Any, format: Any) -> ExportFile:  # noqa: A002 - name fixed by doc 03
        media_type = "application/json" if format == "json" else "text/csv"
        return ExportFile(b"# header\ninvestigation\nA\n", media_type, f"extract.{format}")

    def dictionary(self) -> DictionaryResponse:
        return DictionaryResponse(
            columns=[ColumnInfo(name="investigation", label="Investigation")]
        )


class FakeSafetyTech:
    def grouped(self) -> SafetyTechResponse:
        return SafetyTechResponse(groups=[])

    def gaps(self) -> GapsResponse:
        return GapsResponse(gaps=[GapItem(id="partial_gravity", title="t", detail="d")])


class FakeEarth:
    def __init__(self) -> None:
        self.sectors: builtins.list[str | None] = []

    def list(self, sector: str | None = None) -> EarthApplicationsResponse:
        self.sectors.append(sector)
        return EarthApplicationsResponse(items=[])


class FakeInsight:
    async def ask(self, question: str, filters: Any, top_k: int) -> AsyncIterator[str]:
        yield sse_event("done", AskDone())


def _returning(fake: Any) -> Callable[[], Any]:
    # A parameterless provider: FastAPI would treat (and copy) any parameter as a query field.
    return lambda: fake


@pytest.fixture
def fakes(app: FastAPI) -> dict[str, Any]:
    """Install one fake per service and return them by name."""
    services: dict[str, Any] = {
        "catalog": FakeCatalog(),
        "meta": FakeMeta(),
        "earth": FakeEarth(),
    }
    overrides: dict[Callable[..., Any], Any] = {
        deps.get_catalog_service: services["catalog"],
        deps.get_meta_service: services["meta"],
        deps.get_ranking_service: FakeRanking(),
        deps.get_compare_service: FakeCompare(),
        deps.get_scenario_service: FakeScenario(),
        deps.get_extract_service: FakeExtract(),
        deps.get_safety_tech_service: FakeSafetyTech(),
        deps.get_earth_service: services["earth"],
        deps.get_insight_service: FakeInsight(),
    }
    for provider, fake in overrides.items():
        app.dependency_overrides[provider] = _returning(fake)
    return services


def _registered_endpoints(app: FastAPI) -> set[tuple[str, str]]:
    paths = app.openapi()["paths"]
    return {
        (method.upper(), path.removeprefix(API))
        for path, operations in paths.items()
        for method in operations
    }


def test_fr01_registered_routes_equal_the_inventory(app: FastAPI) -> None:
    """Doc 05 s11: exactly the 24 endpoints under `/api/v1`; nothing extra."""
    registered = _registered_endpoints(app)
    assert len(registered) == INVENTORY_SIZE
    assert registered == ENDPOINT_INVENTORY


GET_CASES = [
    ("/health", {"status"}),
    ("/meta/stats", {"investigations", "test_runs", "fuel_phase_counts", "rubric_version"}),
    ("/meta/status", {"components"}),
    ("/meta/rubric", {"rubric_version", "lens_weights", "lenses"}),
    ("/meta/presets", {"ranking", "scenario", "texts"}),
    ("/investigations", {"items", "page", "page_size", "total"}),
    ("/investigations/ALPHA", {"acronym", "card", "score_breakdown", "run_count", "data"}),
    ("/investigations/ALPHA/runs", {"items", "page", "page_size", "total"}),
    ("/investigations/ALPHA/variables", {"varied", "fixed", "run_count"}),
    ("/facets", {"fuel_phase", "hardware", "project", "tag", "platform", "gravity_level"}),
    ("/hardware", {"nodes", "edges"}),
    ("/extract/dictionary", {"columns"}),
    ("/insights/safety-tech", {"groups"}),
    ("/insights/gaps", {"gaps"}),
    ("/earth-applications", {"items"}),
]


@pytest.mark.usefixtures("fakes")
@pytest.mark.parametrize(("path", "fields"), GET_CASES)
def test_fr01_get_endpoints_return_documented_fields(
    client: TestClient, path: str, fields: set[str]
) -> None:
    """FR-01, FR-02, FR-06, FR-08 to FR-14: 200 with the response-model fields."""
    response = client.get(f"{API}{path}")
    assert response.status_code == 200, response.text
    assert fields <= set(response.json())


@pytest.mark.usefixtures("fakes")
@pytest.mark.parametrize("path", ["/investigations/ALPHA/publications", "/projects"])
def test_fr01_list_endpoints_return_arrays(client: TestClient, path: str) -> None:
    """FR-01, FR-12: publications and projects are JSON arrays."""
    response = client.get(f"{API}{path}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


POST_CASES = [
    (
        "/rank",
        {"lens": "habitat"},
        {"lens", "rubric_version", "weights_used", "items", "disclaimer"},
    ),
    (
        "/compare",
        {"investigations": ["ALPHA", "BRAVO"]},
        {"investigations", "matrix", "shared", "narrative"},
    ),
    (
        "/scenario",
        {"preset": "lunar_habitat"},
        {"scenario", "coverage", "matches", "gravity_bounding", "explanation", "scenario_id"},
    ),
    ("/extract/preview", {}, {"columns", "rows", "total"}),
]


@pytest.mark.usefixtures("fakes")
@pytest.mark.parametrize(("path", "body", "fields"), POST_CASES)
def test_fr03_post_endpoints_return_documented_fields(
    client: TestClient, path: str, body: dict[str, Any], fields: set[str]
) -> None:
    """FR-03, FR-05, FR-07, FR-08: 200 with the response-model fields."""
    response = client.post(f"{API}{path}", json=body)
    assert response.status_code == 200, response.text
    assert fields <= set(response.json())


@pytest.mark.usefixtures("fakes")
def test_fr13_ready_and_health(client: TestClient) -> None:
    """FR-13: `/health` is ok; `/ready` reports db, migrations and investigations."""
    assert client.get(f"{API}/health").json() == {"status": "ok"}
    ready = client.get(f"{API}/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_fr13_not_ready_is_503_without_envelope(app: FastAPI, client: TestClient) -> None:
    """FR-13: 503 with the readiness fields and `status: not_ready`, not the error envelope."""
    app.dependency_overrides[deps.get_meta_service] = lambda: FakeMeta(is_ready=False)
    response = client.get(f"{API}/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "db": False,
        "migrations": None,
        "investigations": 0,
    }


@pytest.mark.usefixtures("fakes")
def test_fr03_meta_rubric_and_presets_come_from_the_data_files(client: TestClient) -> None:
    """FR-03, FR-04: rubric version 2026.11-1, default lens weights, lunar preset."""
    rubric = client.get(f"{API}/meta/rubric").json()
    assert rubric["rubric_version"] == "2026.11-1"
    assert rubric["lens_weights"] == {"habitat": 0.4, "modeling": 0.3, "controls": 0.3}
    presets = client.get(f"{API}/meta/presets").json()
    assert presets["ranking"]["lunar_habitat"]["lens_weights"]["habitat"] == 0.6
    assert presets["scenario"]["lunar_habitat"]["gravity_g"] == 0.166


class TestPagination:
    def test_fr02_default_pagination(self, client: TestClient, fakes: dict[str, Any]) -> None:
        """FR-02: page 1 and page_size 24 by default; sort `acronym`."""
        body = client.get(f"{API}/investigations").json()
        assert (body["page"], body["page_size"]) == (1, DEFAULT_PAGE_SIZE)
        _, (_, page) = fakes["catalog"].calls[-1]
        assert page.sort == "acronym"

    @pytest.mark.usefixtures("fakes")
    @pytest.mark.parametrize("path", ["/investigations", "/investigations/ALPHA/runs"])
    def test_fr02_page_size_100_is_the_maximum(self, client: TestClient, path: str) -> None:
        """FR-02, FR-06: page_size at most 100."""
        assert client.get(f"{API}{path}", params={"page_size": MAX_PAGE_SIZE}).status_code == 200
        too_big = client.get(f"{API}{path}", params={"page_size": MAX_PAGE_SIZE + 1})
        assert too_big.status_code == 422
        assert too_big.json()["error"]["code"] == "validation_error"

    @pytest.mark.usefixtures("fakes")
    @pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page": "x"}])
    def test_fr02_invalid_page_is_422(self, client: TestClient, params: dict[str, Any]) -> None:
        """FR-02: page >= 1 and page_size >= 1."""
        assert client.get(f"{API}/investigations", params=params).status_code == 422

    def test_fr02_repeatable_filters(self, client: TestClient, fakes: dict[str, Any]) -> None:
        """FR-02: `fuel_phase` and `tag` are repeatable; `sort` accepts score keys."""
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("fuel_phase", "solid"),
            ("fuel_phase", "gas"),
            ("tag", "extinction"),
            ("sort", "overall"),
        ]
        assert client.get(f"{API}/investigations", params=params).status_code == 200
        _, (filters, page) = fakes["catalog"].calls[-1]
        assert filters.fuel_phase == ["solid", "gas"]
        assert filters.tag == ["extinction"]
        assert page.sort == "overall"


VALIDATION_CASES = [
    ("GET", "/investigations", {"params": {"sort": "title"}}),
    ("GET", "/investigations", {"params": {"fuel_phase": "plasma"}}),
    ("GET", "/investigations", {"params": {"o2_min": 1.5}}),
    ("GET", "/earth-applications", {"params": {"sector": "space"}}),
    ("POST", "/rank", {"json": {}}),
    ("POST", "/rank", {"json": {"lens": "safety"}}),
    ("POST", "/rank", {"json": {"lens": "habitat", "limit": 0}}),
    ("POST", "/rank", {"json": {"lens": "habitat", "unknown": 1}}),
    ("POST", "/compare", {"json": {}}),
    ("POST", "/scenario", {"json": {"o2_fraction": 1.5}}),
    ("POST", "/scenario", {"json": {"pressure_kpa": -1}}),
    ("POST", "/extract/preview", {"json": {"limit": 5001}}),
    ("POST", "/extract/export", {"json": {"format": "xml"}}),
    ("POST", "/ask", {"json": {"question": ""}}),
    ("POST", "/ask", {"json": {"question": "q", "top_k": 0}}),
]


@pytest.mark.usefixtures("fakes")
@pytest.mark.parametrize(("method", "path", "request_args"), VALIDATION_CASES)
def test_fr02_request_validation_errors(
    client: TestClient, method: str, path: str, request_args: dict[str, Any]
) -> None:
    """FR-02 and every endpoint: schema violations are 422 `validation_error` with details."""
    response = client.request(method, f"{API}{path}", **request_args)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]


class TestRequestId:
    @pytest.mark.usefixtures("fakes")
    @pytest.mark.parametrize("path", ["/health", "/investigations", "/no-such-route"])
    def test_nfr11_request_id_is_echoed(self, client: TestClient, path: str) -> None:
        """NFR-11, doc 05 s1: every response carries the caller's `X-Request-ID`."""
        response = client.get(f"{API}{path}", headers={"X-Request-ID": "trace-123"})
        assert response.headers["X-Request-ID"] == "trace-123"

    @pytest.mark.usefixtures("fakes")
    def test_nfr11_request_id_is_generated(self, client: TestClient) -> None:
        """NFR-11, doc 05 s1: a request without an ID still gets one."""
        assert client.get(f"{API}/health").headers["X-Request-ID"]

    @pytest.mark.usefixtures("fakes")
    def test_nfr11_validation_error_carries_request_id(self, client: TestClient) -> None:
        """NFR-11, doc 05 s2: the envelope `request_id` equals the header."""
        response = client.post(f"{API}/rank", json={}, headers={"X-Request-ID": "trace-422"})
        assert response.json()["error"]["request_id"] == "trace-422"


class TestCompareBounds:
    @pytest.mark.parametrize("count", [1, 5])
    def test_fr05_compare_with_1_or_5_ids_is_400(
        self, app: FastAPI, client: TestClient, count: int
    ) -> None:
        """FR-05: 2 to 4 IDs; 1 and 5 are HTTP 400 `bad_request` from `CompareService`."""
        service = CompareService(None, None, None, None)  # type: ignore[arg-type]
        app.dependency_overrides[deps.get_compare_service] = lambda: service
        ids = [f"INV{n}" for n in range(count)]
        response = client.post(f"{API}/compare", json={"investigations": ids})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "bad_request"


class TestEndpointSpecifics:
    @pytest.mark.usefixtures("fakes")
    def test_fr03_rank_limit_truncates_after_ranking(self, client: TestClient) -> None:
        """FR-03: `limit` truncates the list; ranks stay those of the full ordering."""
        items = client.post(f"{API}/rank", json={"lens": "overall", "limit": 2}).json()["items"]
        assert [item["rank"] for item in items] == [1, 2]

    @pytest.mark.usefixtures("fakes")
    @pytest.mark.parametrize(
        ("export_format", "media_type"), [("csv", "text/csv"), ("json", "application/json")]
    )
    def test_fr08_export_is_a_file_download(
        self, client: TestClient, export_format: str, media_type: str
    ) -> None:
        """FR-08: export returns `text/csv` or `application/json` with `Content-Disposition`."""
        response = client.post(f"{API}/extract/export", json={"format": export_format})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(media_type)
        assert response.headers["content-disposition"].startswith("attachment;")
        assert f'extract.{export_format}"' in response.headers["content-disposition"]

    def test_fr10_earth_sector_filter(self, client: TestClient, fakes: dict[str, Any]) -> None:
        """FR-10: `sector` query reaches the service."""
        assert (
            client.get(f"{API}/earth-applications", params={"sector": "wildfire"}).status_code
            == 200
        )
        assert fakes["earth"].sectors == ["wildfire"]

    @pytest.mark.usefixtures("fakes")
    def test_fr11_ask_is_an_event_stream(self, client: TestClient) -> None:
        """FR-11: `POST /ask` responds with `text/event-stream`."""
        response = client.post(f"{API}/ask", json={"question": "Which fuels?"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    @pytest.mark.usefixtures("fakes")
    def test_fr05_compare_narrative_flag(self, client: TestClient) -> None:
        """FR-05: `narrative=false` gives `skipped`."""
        body = {"investigations": ["ALPHA", "BRAVO"], "narrative": False}
        assert client.post(f"{API}/compare", json=body).json()["narrative"]["status"] == "skipped"


def test_fr01_path_id_reaches_the_service(client: TestClient, fakes: dict[str, Any]) -> None:
    """FR-01: the `{id}` path parameter (URL-encoded acronym) reaches `CatalogService.get`."""
    assert client.get(f"{API}/investigations/E-FIELD%20Flames").status_code == 200
    assert fakes["catalog"].calls[-1] == ("get", "E-FIELD Flames")
