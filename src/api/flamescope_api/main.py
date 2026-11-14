"""App factory `create_app()`, request-ID middleware, CORS and router registration."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from flamescope_api.errors import REQUEST_ID_HEADER, register_exception_handlers
from flamescope_api.routers import (
    ask,
    catalog,
    compare,
    earth,
    extract,
    health,
    insights,
    investigations,
    meta,
    rank,
    scenario,
)
from flamescope_common.config import get_settings
from flamescope_common.logging import configure_logging, request_id_var

API_PREFIX = "/api/v1"
API_TITLE = "FlameScope API"
API_VERSION = "0.1.0"
REQUEST_ID_HEADER_BYTES = REQUEST_ID_HEADER.lower().encode()

logger = structlog.get_logger(__name__)


class RequestIdMiddleware:
    """Take `X-Request-ID` from the request or mint one; bind it to logs; echo it back."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[Any] = list(message.get("headers", []))
                if not any(name.lower() == REQUEST_ID_HEADER_BYTES for name, _ in headers):
                    headers.append((REQUEST_ID_HEADER_BYTES, request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name == REQUEST_ID_HEADER_BYTES:
            return str(value.decode()).strip() or None
    return None


def create_app() -> FastAPI:
    """Build the FastAPI application with all 24 endpoints under `/api/v1`."""
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    for module in (
        health,
        meta,
        investigations,
        catalog,
        rank,
        compare,
        scenario,
        extract,
        insights,
        earth,
        ask,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
    return app
