"""Domain errors. The API maps each class to the error envelope of document 05 section 2."""

from __future__ import annotations

from typing import Any


class FlameScopeError(Exception):
    """Base class of every domain error; `code` is the envelope code."""

    code = "internal_error"

    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(FlameScopeError):
    """An investigation or other resource does not exist (HTTP 404)."""

    code = "not_found"


class ValidationError(FlameScopeError):
    """Semantically invalid input that passed schema validation (HTTP 400 `bad_request`)."""

    code = "bad_request"


class LLMError(FlameScopeError):
    """The LLM provider failed after retries (HTTP 502)."""

    code = "llm_unavailable"


class IngestError(FlameScopeError):
    """An ingestion stage failed."""

    code = "ingest_error"
