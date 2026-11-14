"""Structured JSON logging with a request-ID context variable (document 02 section 6)."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def _add_request_id(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    event_dict["request_id"] = request_id_var.get()
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Route stdlib and structlog output to stdout as JSON with ts, level, logger, request_id."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper(), force=True)
    processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        _add_request_id,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
