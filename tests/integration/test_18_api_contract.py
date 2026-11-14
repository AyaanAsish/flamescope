"""API contract (document 12 section 2; document 05 sections 1, 2 and 11; document 02 s6).

Requirements: NFR-08 (every endpoint tested), NFR-11 (`X-Request-ID` on every response),
FR-15 (`SourceRef` shape). Call flows: all API flows CF-04 to CF-12 share this contract.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(18)]

DOC_05 = "05-api-specification.md"
API_PREFIX = "/api/v1"
INVENTORY_SIZE = 24
ENDPOINT = re.compile(r"`(GET|POST) (/[^`]*)`")
OTHER_ORIGIN = "http://not-allowed.example"
SUPPLIED_REQUEST_ID = "it-contract-0018"
GENERATED_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
SAMPLE_PATHS = ("/health", "/meta/stats", "/investigations", "/facets", "/no-such-route")
SUMMARY = (
    "id", "acronym", "title", "project", "platform", "gravity_level", "fuel_phases", "hardware",
    "summary", "fire_safety_tags", "o2_range", "pressure_range_kpa", "flow_range_cm_s",
    "scores", "reviewed", "psi_url",
)  # fmt: skip
SOURCE_REF = ("kind", "uri", "title", "locator", "quote", "chunk_id")
COMPONENT = ("id", "status", "detail", "provider", "model", "last_run")
PUBLICATION = ("doi", "title", "authors", "year", "venue", "url", "key_findings")
# Documented response fields (document 05 sections 3 to 9) by endpoint; `a[]` is an array item.
DOCUMENTED_FIELDS: dict[tuple[str, str], tuple[str, ...]] = {
    ("get", "/health"): ("status",),
    ("get", "/ready"): ("status", "db", "migrations", "investigations"),
    ("get", "/meta/stats"): (
        "investigations", "test_runs", "publications", "findings", "chunks", "hardware",
        "fuel_phase_counts", "o2_range", "pressure_range_kpa", "rubric_version", "last_ingest",
        "ingest_mode",
    ),
    ("get", "/meta/status"): tuple(f"components[].{name}" for name in COMPONENT),
    ("get", "/meta/rubric"): ("rubric_version", "lens_weights", "lenses"),
    ("get", "/meta/presets"): ("rubric_version", "ranking", "scenario", "texts"),
    ("get", "/investigations"): ("page", "page_size", "total", *(f"items[].{f}" for f in SUMMARY)),
    ("get", "/investigations/{id}"): (
        *SUMMARY, "card", "publications", "measurements", "findings", "score_breakdown",
        "run_count", "data",
    ),
    ("get", "/investigations/{id}/runs"): tuple(
        f"items[].{name}" for name in (
            "id", "label", "fuel", "geometry", "condition", "outcome", "is_aggregate", "source",
            "confidence",
        )
    ),
    ("get", "/investigations/{id}/variables"): ("varied", "fixed", "run_count"),
    ("get", "/investigations/{id}/publications"): tuple(f"[].{name}" for name in PUBLICATION),
    ("get", "/facets"): ("fuel_phase", "hardware", "project", "tag", "platform", "gravity_level"),
    ("get", "/hardware"): (
        "nodes[].id", "nodes[].type", "nodes[].label", "nodes[].kind",
        "edges[].source", "edges[].target", "edges[].role",
    ),
    ("get", "/projects"): ("[].name", "[].description", "[].investigations"),
    ("post", "/rank"): (
        "lens", "rubric_version", "weights_used", "disclaimer", "items[].rank", "items[].acronym",
        "items[].title", "items[].score", "items[].confidence", "items[].lens_scores",
        *(f"items[].breakdown[].{name}" for name in (
            "criterion", "label", "value", "weight", "contribution", "rationale", "origin",
        )),
        *(f"items[].breakdown[].evidence[].{name}" for name in SOURCE_REF),
    ),
    ("post", "/compare"): (
        "investigations", "matrix[].attribute", "matrix[].label", "matrix[].group",
        "matrix[].values", "matrix[].same", "shared.hardware", "shared.tags",
        "shared.instruments", "narrative.text", "narrative.sentences[].text",
        "narrative.sentences[].citations", "narrative.status",
    ),
    ("post", "/scenario"): (
        "scenario", "coverage", "matches[].acronym", "matches[].similarity", "matches[].best_run",
        "matches[].median_similarity", "matches[].per_dimension", "matches[].matching_runs",
        "gravity_bounding.partial_gravity_data", "gravity_bounding.lower_bound",
        "gravity_bounding.upper_bound", "gravity_bounding.analogue", "gravity_bounding.statement",
        "explanation.text", "explanation.sentences", "explanation.status", "scenario_id",
    ),
    ("post", "/extract/preview"): (
        "columns[].name", "columns[].label", "columns[].unit", "columns[].description", "rows",
        "total",
    ),
    ("get", "/extract/dictionary"): (
        "columns[].name", "columns[].label", "columns[].unit", "columns[].description",
    ),
    ("get", "/insights/safety-tech"): (
        "groups[].category", "groups[].label", "groups[].investigations",
        *(f"groups[].findings[].{name}" for name in (
            "id", "statement", "investigation", "source", "confidence",
        )),
    ),
    ("get", "/insights/gaps"): tuple(
        f"gaps[].{name}" for name in ("id", "title", "detail", "related", "future")
    ),
    ("get", "/earth-applications"): tuple(
        f"items[].{name}" for name in (
            "id", "title", "sector", "description", "maturity", "investigations", "findings",
            "references",
        )
    ),
}  # fmt: skip


@pytest.fixture(scope="module")
def openapi(stack: str) -> dict[str, Any]:
    response = httpx.get(f"{stack}/openapi.json", timeout=30)
    assert response.status_code == httpx.codes.OK
    return dict(response.json())


@pytest.fixture(scope="module")
def inventory(doc_section: Callable[[str, str], str]) -> set[tuple[str, str]]:
    """Document 05 section 11: the documented method-path pairs."""
    section = doc_section(DOC_05, "## 11. Endpoint inventory")
    return {(method.lower(), path) for method, path in ENDPOINT.findall(section)}


def _resolve(openapi: Mapping[str, Any], schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Follow `$ref` and pick the non-null branch of `anyOf` (nullable fields)."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[1]
        return _resolve(openapi, openapi["components"]["schemas"][name])
    branches = [branch for branch in schema.get("anyOf", []) if branch.get("type") != "null"]
    return _resolve(openapi, branches[0]) if branches else schema


def _step(
    openapi: Mapping[str, Any], schema: Mapping[str, Any], part: str
) -> Mapping[str, Any] | None:
    name, is_array = part.removesuffix("[]"), part.endswith("[]")
    current = _resolve(openapi, schema)
    if name:
        properties = current.get("properties", {})
        if name not in properties:
            return None
        current = _resolve(openapi, properties[name])
    return _resolve(openapi, current["items"]) if is_array else current


def _has_field(openapi: Mapping[str, Any], schema: Mapping[str, Any], path: str) -> bool:
    current: Mapping[str, Any] | None = schema
    for part in path.split("."):
        current = _step(openapi, current, part) if current is not None else None
    return current is not None


def _response_schema(openapi: Mapping[str, Any], method: str, path: str) -> Mapping[str, Any]:
    content = openapi["paths"][f"{API_PREFIX}{path}"][method]["responses"]["200"]["content"]
    return dict(content["application/json"]["schema"])


def test_nfr08_openapi_lists_exactly_the_documented_endpoints(
    openapi: dict[str, Any], inventory: set[tuple[str, str]]
) -> None:
    """NFR-08, doc 05 s11: exactly 24 method-path pairs under /api/v1, nothing extra."""
    served = {
        (method, path.removeprefix(API_PREFIX))
        for path, item in openapi["paths"].items()
        for method in item
    }
    assert len(inventory) == INVENTORY_SIZE
    assert all(path.startswith(API_PREFIX) for path in openapi["paths"])
    assert served == inventory


def test_nfr08_documented_response_fields_in_schemas(openapi: dict[str, Any]) -> None:
    """NFR-08, doc 05 s3 to s9: every documented response field exists in the schemas."""
    missing = [
        f"{method.upper()} {path}: {field}"
        for (method, path), fields in DOCUMENTED_FIELDS.items()
        for field in fields
        if not _has_field(openapi, _response_schema(openapi, method, path), field)
    ]
    assert missing == []


def test_fr15_source_ref_schema(openapi: dict[str, Any]) -> None:
    """FR-15, doc 04 s3: `SourceRef` carries kind, uri, title, locator, quote and chunk_id."""
    properties = openapi["components"]["schemas"]["SourceRef"]["properties"]
    assert set(SOURCE_REF) <= set(properties)


def test_nfr08_not_found_and_validation_envelopes(
    stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """NFR-08, doc 05 s2: 404 `not_found` and 422 `validation_error` envelopes."""
    assert_error_envelope(api.get("/investigations/NO-SUCH-INVESTIGATION"), 404, "not_found")
    invalid = assert_error_envelope(
        api.post("/rank", json={"lens": "no_such_lens"}), 422, "validation_error"
    )
    assert invalid["details"]


@pytest.mark.parametrize("path", SAMPLE_PATHS)
def test_nfr11_request_id_generated_when_absent(path: str, stack: str, api: httpx.Client) -> None:
    """NFR-11: every response (success or error) carries a generated `X-Request-ID`."""
    assert GENERATED_REQUEST_ID.match(api.get(path).headers["x-request-id"])


@pytest.mark.parametrize("path", SAMPLE_PATHS)
def test_nfr11_request_id_echoed_when_supplied(path: str, stack: str, api: httpx.Client) -> None:
    """NFR-11: a supplied `X-Request-ID` is echoed back."""
    response = api.get(path, headers={"X-Request-ID": SUPPLIED_REQUEST_ID})
    assert response.headers["x-request-id"] == SUPPLIED_REQUEST_ID


def test_nfr11_request_id_on_post_and_errors(stack: str, api: httpx.Client) -> None:
    """NFR-11: POST responses and error envelopes echo the same ID."""
    response = api.post(
        "/compare", json={"investigations": []}, headers={"X-Request-ID": SUPPLIED_REQUEST_ID}
    )
    assert response.headers["x-request-id"] == SUPPLIED_REQUEST_ID
    assert response.json()["error"]["request_id"] == SUPPLIED_REQUEST_ID


def test_cors_header_for_configured_origin_only(
    stack: str, api: httpx.Client, setting: Callable[[str], str]
) -> None:
    """Doc 11 s3 `CORS_ORIGINS`: the configured origin is allowed; another origin is not."""
    allowed = setting("CORS_ORIGINS").split(",")[0].strip()
    granted = api.get("/health", headers={"Origin": allowed}).headers.get(
        "access-control-allow-origin"
    )
    refused = api.get("/health", headers={"Origin": OTHER_ORIGIN}).headers.get(
        "access-control-allow-origin"
    )
    assert (granted, refused) == (allowed, None)
