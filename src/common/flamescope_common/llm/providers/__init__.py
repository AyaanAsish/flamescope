"""Provider adapters behind one protocol, plus the request helpers they share (doc 07 s6)."""

from __future__ import annotations

from typing import Any, Protocol

from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from pydantic import BaseModel


class LLMProvider(Protocol):
    """A model backend: supplies the ADK model agents run on, and embeddings."""

    name: str

    def model(self) -> BaseLlm: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def text_of(content: object) -> str:
    """Plain text of a string or an ADK/genai `Content`."""
    if isinstance(content, str):
        return content
    parts = getattr(content, "parts", None) or []
    return "\n".join(part.text for part in parts if getattr(part, "text", None))


def user_text(llm_request: LlmRequest) -> str:
    """Text of the last user turn: the rendered `## User` prompt section."""
    user_turns = [item for item in llm_request.contents if item.role == "user"]
    return text_of(user_turns[-1]) if user_turns else ""


def system_text(llm_request: LlmRequest) -> str:
    """Text of the system instruction: the rendered `## System` prompt section."""
    config = llm_request.config
    return text_of(config.system_instruction) if config and config.system_instruction else ""


def response_json_schema(llm_request: LlmRequest) -> dict[str, Any] | None:
    """The JSON schema an agent's `output_schema` put on the request, if any."""
    config = llm_request.config
    if config is None:
        return None
    schema = config.response_json_schema or config.response_schema
    if isinstance(schema, dict):
        return schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema.model_json_schema()
    return None
