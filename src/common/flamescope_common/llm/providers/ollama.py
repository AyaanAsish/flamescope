"""Ollama provider: ADK `LiteLlm` for chat, `POST /api/embed` for embeddings."""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from google.adk.models import BaseLlm
from google.adk.models.lite_llm import LiteLlm

from flamescope_common.config import Settings
from flamescope_common.errors import LLMError

logger = structlog.get_logger(__name__)

TRANSIENT_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5
HTTP_SERVER_ERROR_MIN = 500
EMBED_PATH = "/api/embed"
# Reasoning models would spend the prompt `max_tokens` on hidden thinking (doc 07 s6.1);
# models without the capability ignore the flag.
THINKING_ENABLED = False


class OllamaProvider:
    """`LLMProvider` for `LLM_PROVIDER=ollama` / `EMBED_PROVIDER=ollama`."""

    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._chat_model = settings.llm_model
        self._embed_model = settings.embed_model
        self._embed_dim = settings.embed_dim
        self._timeout_s = settings.llm_timeout_s

    def model(self) -> BaseLlm:
        return LiteLlm(
            model=f"ollama_chat/{self._chat_model}",
            api_base=self._base_url,
            timeout=self._timeout_s,
            num_retries=TRANSIENT_RETRIES,
            think=THINKING_ENABLED,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = self._post_with_retry(EMBED_PATH, {"model": self._embed_model, "input": texts})
        return self._validated_embeddings(body, expected=len(texts))

    def _validated_embeddings(self, body: dict[str, Any], expected: int) -> list[list[float]]:
        embeddings = body.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != expected:
            raise LLMError("Ollama returned an unexpected number of embeddings")
        for vector in embeddings:
            if len(vector) != self._embed_dim:
                raise LLMError(
                    f"Embedding model {self._embed_model!r} returned {len(vector)} dimensions, "
                    f"expected EMBED_DIM={self._embed_dim}"
                )
        return embeddings

    def _post_with_retry(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(TRANSIENT_RETRIES):
            try:
                return self._post(path, payload)
            except (httpx.TransportError, _TransientStatusError) as error:
                last_error = error
                logger.warning("ollama_retry", attempt=attempt + 1, error=str(error))
                if attempt < TRANSIENT_RETRIES - 1:
                    time.sleep(BACKOFF_BASE_SECONDS * 2**attempt)
        raise LLMError(f"Ollama unreachable at {self._base_url}: {last_error}") from last_error

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(f"{self._base_url}{path}", json=payload, timeout=self._timeout_s)
        if response.status_code >= HTTP_SERVER_ERROR_MIN:
            raise _TransientStatusError(f"HTTP {response.status_code}")
        if response.is_error:
            raise LLMError(f"Ollama rejected the request: HTTP {response.status_code}")
        decoded: dict[str, Any] = response.json()
        return decoded


class _TransientStatusError(Exception):
    """Server-side failure worth retrying."""
