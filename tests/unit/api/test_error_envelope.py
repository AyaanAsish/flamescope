"""FR-01, FR-03, FR-05: the error envelope for 400, 404, 422, 500 and 502 (doc 05 s2)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flamescope_api import deps
from flamescope_api.services.compare import CompareService
from flamescope_common.errors import LLMError, NotFoundError, ValidationError

pytestmark = pytest.mark.unit

ENVELOPE_KEYS = {"code", "message", "details", "request_id"}
REQUEST_ID = "req-envelope-1"
LEAKY_DETAIL = "secret stack detail"


class RaisingCatalog:
    """Catalog service whose detail lookup raises the configured error."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def get(self, investigation_id: str) -> Any:
        raise self._error


def _get_detail(app: FastAPI, client: TestClient, error: Exception) -> Any:
    app.dependency_overrides[deps.get_catalog_service] = lambda: RaisingCatalog(error)
    return client.get("/api/v1/investigations/XYZ", headers={"X-Request-ID": REQUEST_ID})


def _assert_envelope(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == ENVELOPE_KEYS
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    error: dict[str, Any] = body["error"]
    return error


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (NotFoundError("Investigation 'XYZ' not found"), 404, "not_found"),
        (ValidationError("Unknown preset"), 400, "bad_request"),
        (LLMError("provider failed after retries"), 502, "llm_unavailable"),
    ],
)
def test_fr01_domain_errors_map_to_envelope(
    app: FastAPI, client: TestClient, error: Exception, status: int, code: str
) -> None:
    """FR-01: domain errors become the envelope with the documented HTTP status and code."""
    body = _assert_envelope(_get_detail(app, client, error), status, code)
    assert body["message"] == str(error)
    assert body["request_id"] == REQUEST_ID


def test_fr01_unexpected_error_is_internal_error(app: FastAPI, client: TestClient) -> None:
    """FR-01: anything else is 500 `internal_error` without leaking the exception text."""
    body = _assert_envelope(
        _get_detail(app, client, RuntimeError(LEAKY_DETAIL)), 500, "internal_error"
    )
    assert LEAKY_DETAIL not in body["message"]


def test_fr03_request_validation_is_422_with_field_details(client: TestClient) -> None:
    """FR-03: schema failures are 422 `validation_error`; `details` lists the fields."""
    body = _assert_envelope(client.post("/api/v1/rank", json={}), 422, "validation_error")
    assert isinstance(body["details"], list)
    assert any("lens" in detail["loc"] for detail in body["details"])


def test_fr05_compare_with_one_id_is_400(app: FastAPI, client: TestClient) -> None:
    """FR-05: fewer than 2 IDs is `bad_request` raised by `CompareService`."""
    service = CompareService(None, None, None, None)  # type: ignore[arg-type]
    app.dependency_overrides[deps.get_compare_service] = lambda: service
    response = client.post("/api/v1/compare", json={"investigations": ["ALPHA"]})
    _assert_envelope(response, 400, "bad_request")


def test_fr01_unknown_route_is_not_found_envelope(client: TestClient) -> None:
    """FR-01: an unknown resource path is 404 `not_found` in the envelope."""
    _assert_envelope(client.get("/api/v1/no-such-endpoint"), 404, "not_found")
