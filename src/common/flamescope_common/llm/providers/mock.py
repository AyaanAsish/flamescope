"""Deterministic mock provider: no network, schema-valid output for every agent."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from typing import Any

from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from flamescope_common.llm.providers import response_json_schema, system_text, user_text
from flamescope_common.llm.providers.mock_agents import SYNTHESIZERS
from flamescope_common.schemas.agents import (
    INSUFFICIENT_INFORMATION_SENTENCE,
    ComparatorInput,
    EarthAppsInput,
    ExtractorInput,
    InsightQAInput,
    ScenarioInterpreterInput,
    ScorerInput,
)

MOCK_MODEL_NAME = "mock"
FIXTURE_KEY_LENGTH = 16

_TOKEN = re.compile(r"[a-z0-9]+")
# Function words every English text shares; hashing them would make unrelated texts similar
# (document 07 section 6: content words only).
# fmt: off
STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and", "any", "are", "as",
    "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "out", "over", "own", "same", "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "theirs", "them", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours",
})
# fmt: on
_STREAM_TOKEN = re.compile(r"\S+\s*")

INPUT_MODELS: dict[str, type[BaseModel]] = {
    "extractor": ExtractorInput,
    "scorer": ScorerInput,
    "comparator": ComparatorInput,
    "scenario_interpreter": ScenarioInterpreterInput,
    "insight_qa": InsightQAInput,
    "earth_apps": EarthAppsInput,
}


# --- embeddings ----------------------------------------------------------------------------


def _content_words(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(text.lower()) if token not in STOP_WORDS]


def hashed_embedding(text: str, dim: int) -> list[float]:
    """Hashed bag-of-words of content words, length `dim`, L2-normalized (doc 07 s6)."""
    vector = [0.0] * dim
    for token in _content_words(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        vector[0] = 1.0
        return vector
    return [value / norm for value in vector]


# --- request parsing -----------------------------------------------------------------------


def _json_objects(text: str) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    position = text.find("{")
    while position != -1:
        try:
            decoded, end = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            position = text.find("{", position + 1)
            continue
        if isinstance(decoded, dict):
            yield decoded
        position = text.find("{", end)


def _identify_input(*texts: str) -> tuple[str, BaseModel] | None:
    for text in texts:
        for candidate in _json_objects(text):
            for name, model in INPUT_MODELS.items():
                try:
                    return name, model.model_validate(candidate)
                except PydanticValidationError:
                    continue
    return None


# --- generic schema-valid fallback ---------------------------------------------------------


def _minimal_instance(node: dict[str, Any], definitions: dict[str, Any]) -> Any:
    if "$ref" in node:
        return _minimal_instance(definitions[node["$ref"].rsplit("/", 1)[-1]], definitions)
    if "const" in node:
        return node["const"]
    if "enum" in node:
        return node["enum"][0]
    if "anyOf" in node:
        options = [option for option in node["anyOf"] if option.get("type") != "null"]
        return _minimal_instance(options[0], definitions) if options else None
    return _minimal_of_type(node, definitions)


def _minimal_of_type(node: dict[str, Any], definitions: dict[str, Any]) -> Any:
    kind = node.get("type")
    if kind == "object":
        properties = node.get("properties", {})
        return {
            key: _minimal_instance(properties[key], definitions)
            for key in node.get("required", [])
        }
    if kind == "array":
        item = _minimal_instance(node.get("items", {}), definitions) if node.get("items") else None
        return [item] * node.get("minItems", 0)
    if kind == "string":
        return ""
    if kind in ("integer", "number"):
        return node.get("minimum", 0)
    return False if kind == "boolean" else None


def _schema_fallback(schema: dict[str, Any] | None) -> str:
    if schema is None:
        return INSUFFICIENT_INFORMATION_SENTENCE
    return json.dumps(_minimal_instance(schema, schema.get("$defs", {})), sort_keys=True)


# --- model and provider --------------------------------------------------------------------


def default_fixtures_dir() -> Path | None:
    """`fixtures/` of the `flamescope_agents` package, located without importing it."""
    spec = importlib.util.find_spec("flamescope_agents")
    locations = list(spec.submodule_search_locations or []) if spec else []
    return Path(locations[0]) / "fixtures" if locations else None


def fixture_key(user_text: str) -> str:
    """Fixture file stem for a rendered user prompt."""
    return hashlib.sha256(user_text.encode("utf-8")).hexdigest()[:FIXTURE_KEY_LENGTH]


class MockLlm(BaseLlm):
    """Deterministic ADK model: fixture if present, otherwise synthesized from the request."""

    model: str = MOCK_MODEL_NAME
    fixtures_dir: Path | None = None

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        text = self._complete(llm_request)
        if stream:
            for token in _STREAM_TOKEN.findall(text):
                yield _response(token, partial=True)
        yield _response(text, partial=False, prompt=user_text(llm_request))

    def _complete(self, llm_request: LlmRequest) -> str:
        prompt = user_text(llm_request)
        identified = _identify_input(prompt, system_text(llm_request))
        if identified is None:
            return _schema_fallback(response_json_schema(llm_request))
        agent_name, payload = identified
        fixture = self._read_fixture(agent_name, prompt)
        return fixture if fixture is not None else SYNTHESIZERS[agent_name](payload)

    def _read_fixture(self, agent_name: str, user_text: str) -> str | None:
        if self.fixtures_dir is None:
            return None
        path = self.fixtures_dir / agent_name / f"{fixture_key(user_text)}.json"
        return path.read_text(encoding="utf-8") if path.is_file() else None


def _response(text: str, *, partial: bool, prompt: str = "") -> LlmResponse:
    content = types.Content(role="model", parts=[types.Part(text=text)])
    if partial:
        return LlmResponse(content=content, partial=True)
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=len(prompt.split()), candidates_token_count=len(text.split())
    )
    return LlmResponse(content=content, partial=False, usage_metadata=usage)


class MockProvider:
    """`LLMProvider` for `LLM_PROVIDER=mock` / `EMBED_PROVIDER=mock`."""

    name = "mock"

    def __init__(self, embed_dim: int, fixtures_dir: Path | None = None) -> None:
        self._embed_dim = embed_dim
        self._fixtures_dir = fixtures_dir if fixtures_dir is not None else default_fixtures_dir()

    def model(self) -> BaseLlm:
        return MockLlm(fixtures_dir=self._fixtures_dir)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [hashed_embedding(text, self._embed_dim) for text in texts]
