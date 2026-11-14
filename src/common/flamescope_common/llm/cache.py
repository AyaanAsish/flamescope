"""Database-backed LLM response cache keyed by SHA-256 (document 03 section 2)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from flamescope_common.db import SessionLocal
from flamescope_common.models import LlmCacheEntry

logger = structlog.get_logger(__name__)


def cache_key(provider: str, model: str, prompt: str, parameters: dict[str, Any]) -> str:
    """SHA-256 over provider, model, prompt and generation parameters."""
    canonical = json.dumps(
        {"provider": provider, "model": model, "prompt": prompt, "parameters": parameters},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class LLMCache:
    """Best-effort cache: a database failure is logged and treated as a miss, never raised."""

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            with self._session_factory() as session:
                return session.scalar(
                    select(LlmCacheEntry.response).where(LlmCacheEntry.key == key)
                )
        except SQLAlchemyError as error:
            logger.warning("llm_cache_read_failed", error=str(error))
            return None

    def put(self, key: str, provider: str, model: str, response: dict[str, Any]) -> None:
        statement = (
            insert(LlmCacheEntry)
            .values(key=key, provider=provider, model=model, response=response)
            .on_conflict_do_nothing(index_elements=[LlmCacheEntry.key])
        )
        try:
            with self._session_factory() as session:
                session.execute(statement)
                session.commit()
        except SQLAlchemyError as error:
            logger.warning("llm_cache_write_failed", error=str(error))
