"""Fixtures for the `flamescope_common` unit tests: an in-memory LLM cache and ADK helpers."""

from __future__ import annotations

from typing import Any

import pytest
from google.adk.models.llm_request import LlmRequest
from google.genai import types


class InMemoryLLMCache:
    """Stands in for the database-backed `llm_cache` table (document 04 section 2)."""

    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        self.writes: list[tuple[str, str, str]] = []

    def get(self, key: str) -> dict[str, Any] | None:
        return self.entries.get(key)

    def put(self, key: str, provider: str, model: str, response: dict[str, Any]) -> None:
        self.writes.append((key, provider, model))
        self.entries[key] = response


@pytest.fixture
def llm_cache() -> InMemoryLLMCache:
    return InMemoryLLMCache()


def llm_request(user: str, system: str = "", schema: type | None = None) -> LlmRequest:
    """An ADK request whose last user turn is `user` and system instruction is `system`."""
    config = types.GenerateContentConfig(system_instruction=system or None, response_schema=schema)
    content = types.Content(role="user", parts=[types.Part(text=user)])
    return LlmRequest(contents=[content], config=config)


@pytest.fixture
def make_llm_request() -> Any:
    return llm_request
