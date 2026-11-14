"""LLM gateway: the ADK model, embeddings and ADK model callbacks (document 07 section 6)."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, Protocol

import structlog
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from flamescope_common.config import ProviderName, Settings, get_settings
from flamescope_common.errors import LLMError
from flamescope_common.llm.cache import LLMCache, cache_key
from flamescope_common.llm.providers import (
    LLMProvider,
    response_json_schema,
    system_text,
    text_of,
)
from flamescope_common.llm.providers.mock import MOCK_MODEL_NAME, MockProvider
from flamescope_common.llm.providers.ollama import OllamaProvider

logger = structlog.get_logger(__name__)

EMBED_BATCH_SIZE = 64
STREAMING_MODE_SSE = "sse"
MILLIS_PER_SECOND = 1000.0
_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class CallbackContext(Protocol):
    """The slice of the ADK callback context the gateway reads."""

    @property
    def invocation_id(self) -> str: ...

    @property
    def run_config(self) -> Any: ...


BeforeModelCallback = Callable[[CallbackContext, LlmRequest], LlmResponse | None]
AfterModelCallback = Callable[[CallbackContext, LlmResponse], LlmResponse | None]
ReplyCheck = Callable[[str], bool]


@dataclass(frozen=True)
class ModelCallbacks:
    """ADK `before_model_callback` / `after_model_callback` pair for cache and logging."""

    before_model: BeforeModelCallback
    after_model: AfterModelCallback


@dataclass
class _PendingCall:
    started: float
    cache_key: str | None
    is_valid_reply: ReplyCheck


def _is_streaming(context: CallbackContext) -> bool:
    mode = getattr(context.run_config, "streaming_mode", None)
    return getattr(mode, "value", mode) == STREAMING_MODE_SSE


def _request_prompt(llm_request: LlmRequest) -> str:
    contents = [item.model_dump(mode="json", exclude_none=True) for item in llm_request.contents]
    payload = {"system": system_text(llm_request), "contents": contents}
    return json.dumps(payload, sort_keys=True, default=str)


def _request_parameters(llm_request: LlmRequest) -> dict[str, Any]:
    config = llm_request.config
    if config is None:
        return {}
    return {
        "temperature": config.temperature,
        "max_output_tokens": config.max_output_tokens,
        "top_p": config.top_p,
        "response_schema": response_json_schema(llm_request),
    }


def _is_non_empty(text: str) -> bool:
    return bool(text.strip())


def _matches_output_model(output_model: type[BaseModel], text: str) -> bool:
    try:
        output_model.model_validate_json(_CODE_FENCE.sub("", text.strip()))
    except PydanticValidationError:
        return False
    return True


def _is_unverifiable(_text: str) -> bool:
    return False


def _reply_check(llm_request: LlmRequest) -> ReplyCheck:
    """How a reply to this request is judged valid before it may be cached (doc 07 s6)."""
    config = llm_request.config
    schema = (config.response_schema or config.response_json_schema) if config else None
    if schema is None:
        return _is_non_empty
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return partial(_matches_output_model, schema)
    return _is_unverifiable


def _is_cacheable(response: LlmResponse, is_valid_reply: ReplyCheck) -> bool:
    if response.partial or response.error_code is not None or response.content is None:
        return False
    return is_valid_reply(text_of(response.content))


class LLMGateway:
    """The only entry point to models and embeddings; providers are chosen by configuration."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache: LLMCache | None = None,
        providers: dict[ProviderName, LLMProvider] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._cache = cache or LLMCache()
        self._providers: dict[ProviderName, LLMProvider] = dict(providers or {})
        self._pending: dict[str, _PendingCall] = {}

    def model(self) -> BaseLlm:
        """The Google ADK model for `LLM_PROVIDER`."""
        return self._provider(self._settings.llm_provider).model()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embeddings from `EMBED_PROVIDER`, requested in batches of 64."""
        provider = self._provider(self._settings.embed_provider_name)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            vectors.extend(provider.embed(texts[start : start + EMBED_BATCH_SIZE]))
        return vectors

    def callbacks(self) -> ModelCallbacks:
        """ADK callbacks: response cache (disabled when streaming), logging, request ID."""
        return ModelCallbacks(before_model=self._before_model, after_model=self._after_model)

    def _provider(self, name: ProviderName) -> LLMProvider:
        if name not in self._providers:
            self._providers[name] = self._build_provider(name)
        return self._providers[name]

    def _build_provider(self, name: ProviderName) -> LLMProvider:
        if name == "mock":
            return MockProvider(embed_dim=self._settings.embed_dim)
        if name == "ollama":
            return OllamaProvider(self._settings)
        raise LLMError(f"Unknown LLM provider {name!r}")

    def _before_model(
        self, context: CallbackContext, llm_request: LlmRequest
    ) -> LlmResponse | None:
        started = time.monotonic()
        key = None if _is_streaming(context) else self._key_for(llm_request)
        cached = self._cache.get(key) if key else None
        if cached is not None:
            self._log_call(started, cache_hit=True, response=None)
            return LlmResponse.model_validate(cached)
        self._pending[context.invocation_id] = _PendingCall(
            started, key, _reply_check(llm_request)
        )
        return None

    def _after_model(
        self, context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        pending = self._pending.get(context.invocation_id)
        if pending is None or llm_response.partial:
            return None
        del self._pending[context.invocation_id]
        self._log_call(pending.started, cache_hit=False, response=llm_response)
        if pending.cache_key and _is_cacheable(llm_response, pending.is_valid_reply):
            provider = self._provider(self._settings.llm_provider)
            self._cache.put(
                pending.cache_key,
                provider.name,
                self._model_name(),
                llm_response.model_dump(mode="json", exclude_none=True),
            )
        return None

    def _model_name(self) -> str:
        if self._settings.llm_provider == "mock":
            return MOCK_MODEL_NAME
        return self._settings.llm_model

    def _key_for(self, llm_request: LlmRequest) -> str:
        provider = self._provider(self._settings.llm_provider)
        return cache_key(
            provider.name,
            self._model_name(),
            _request_prompt(llm_request),
            _request_parameters(llm_request),
        )

    def _log_call(self, started: float, *, cache_hit: bool, response: LlmResponse | None) -> None:
        usage = response.usage_metadata if response else None
        logger.info(
            "llm_call",
            provider=self._settings.llm_provider,
            model=self._model_name(),
            latency_ms=round((time.monotonic() - started) * MILLIS_PER_SECOND, 1),
            cache_hit=cache_hit,
            prompt_tokens=usage.prompt_token_count if usage else None,
            completion_tokens=usage.candidates_token_count if usage else None,
        )
