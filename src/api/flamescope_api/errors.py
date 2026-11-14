"""Exception handlers producing the error envelope (document 05 section 2)."""

from __future__ import annotations

from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from flamescope_common.errors import FlameScopeError, LLMError, NotFoundError, ValidationError
from flamescope_common.logging import get_request_id
from flamescope_common.schemas.api import ErrorBody, ErrorEnvelope

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
STATUS_BY_ERROR: dict[type[FlameScopeError], int] = {
    NotFoundError: 404,
    ValidationError: 400,
    LLMError: 502,
}
CODE_BY_STATUS = {400: "bad_request", 404: "not_found", 422: "validation_error"}
INTERNAL_ERROR_MESSAGE = "An internal error occurred."


def _request_id(request: Request) -> str | None:
    state = request.scope.get("state") or {}
    request_id: str | None = state.get("request_id") or get_request_id()
    return request_id


def envelope(
    request: Request, status: int, code: str, message: str, details: Any | None = None
) -> JSONResponse:
    body = ErrorEnvelope(
        error=ErrorBody(
            code=code, message=message, details=details, request_id=_request_id(request)
        )
    )
    headers = {REQUEST_ID_HEADER: request_id} if (request_id := _request_id(request)) else None
    return JSONResponse(body.model_dump(mode="json"), status_code=status, headers=headers)


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(FlameScopeError, exc)
    status = next((s for kind, s in STATUS_BY_ERROR.items() if isinstance(error, kind)), 500)
    return envelope(request, status, error.code, error.message, error.details)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    invalid = cast(RequestValidationError, exc)
    details = [
        {"loc": [str(part) for part in error["loc"]], "msg": error["msg"], "type": error["type"]}
        for error in invalid.errors()
    ]
    return envelope(request, 422, "validation_error", "Request validation failed", details)


async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    http_error = cast(StarletteHTTPException, exc)
    code = CODE_BY_STATUS.get(http_error.status_code, "internal_error")
    return envelope(request, http_error.status_code, code, str(http_error.detail))


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error", path=request.url.path, exc_info=exc)
    return envelope(request, 500, "internal_error", INTERNAL_ERROR_MESSAGE)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(FlameScopeError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
