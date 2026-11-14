"""Ollama provider without a live server (document 07 section 6; document 12; NFR-07)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from google.adk.models.lite_llm import LiteLlm

from flamescope_common.config import Settings
from flamescope_common.errors import LLMError
from flamescope_common.llm.providers import ollama as ollama_module
from flamescope_common.llm.providers.ollama import OllamaProvider

pytestmark = pytest.mark.unit

OLLAMA_URL = "http://ollama.test:11434"
EMBED_URL = f"{OLLAMA_URL}/api/embed"
EMBED_DIM = 768


def ollama_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "llm_provider": "ollama",
        "ollama_base_url": OLLAMA_URL,
        "llm_model": "qwen2.5:0.5b",
        "embed_model": "nomic-embed-text",
        "embed_dim": EMBED_DIM,
    }
    return Settings(_env_file=None, **(values | overrides))  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries back off with `time.sleep`; tests must not wait on the wall clock."""
    monkeypatch.setattr(ollama_module.time, "sleep", lambda _seconds: None)


def embed_response(count: int, dim: int = EMBED_DIM) -> httpx.Response:
    return httpx.Response(200, json={"embeddings": [[0.0] * dim for _ in range(count)]})


def test_provider_name_is_ollama() -> None:
    """NFR-07: provider names are `mock` and `ollama`."""
    assert OllamaProvider(ollama_settings()).name == "ollama"


def test_model_is_lite_llm_for_ollama_chat() -> None:
    """NFR-07: ADK `LiteLlm(model="ollama_chat/<LLM_MODEL>", api_base=OLLAMA_BASE_URL)`."""
    model = OllamaProvider(ollama_settings()).model()

    assert isinstance(model, LiteLlm)
    assert model.model == "ollama_chat/qwen2.5:0.5b"
    assert model._additional_args["api_base"] == OLLAMA_URL


def test_model_follows_llm_model_setting() -> None:
    """NFR-07: any Ollama chat model without code change (document 07 section 6.1)."""
    model = OllamaProvider(ollama_settings(llm_model="qwen2.5:3b")).model()

    assert model.model == "ollama_chat/qwen2.5:3b"


def test_model_uses_llm_timeout() -> None:
    """NFR-07: `LLM_TIMEOUT_S` bounds every model call."""
    model = OllamaProvider(ollama_settings(llm_timeout_s=7.0)).model()

    assert model._additional_args["timeout"] == 7.0


def test_model_disables_thinking() -> None:
    """NFR-07, doc 07 s6.1: chat calls send Ollama `think: false` through `LiteLlm` args."""
    model = OllamaProvider(ollama_settings()).model()

    assert isinstance(model, LiteLlm)
    assert model._additional_args["think"] is False


@respx.mock
def test_embed_posts_to_api_embed() -> None:
    """NFR-07: `POST <OLLAMA_BASE_URL>/api/embed` with `EMBED_MODEL` and the texts."""
    route = respx.post(EMBED_URL).mock(return_value=embed_response(2))

    vectors = OllamaProvider(ollama_settings()).embed(["flame", "spread"])

    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == {
        "model": "nomic-embed-text",
        "input": ["flame", "spread"],
    }
    assert [len(vector) for vector in vectors] == [EMBED_DIM, EMBED_DIM]


@respx.mock
def test_embedding_dimension_must_equal_embed_dim() -> None:
    """NFR-07: the embedding dimension must equal `EMBED_DIM` (document 11 section 3)."""
    respx.post(EMBED_URL).mock(return_value=embed_response(1, dim=EMBED_DIM // 2))

    with pytest.raises(LLMError):
        OllamaProvider(ollama_settings()).embed(["flame"])


@respx.mock
def test_unreachable_server_raises_llm_error() -> None:
    """NFR-07: an unreachable Ollama server raises `LLMError`."""
    respx.post(EMBED_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    with pytest.raises(LLMError):
        OllamaProvider(ollama_settings()).embed(["flame"])


@respx.mock
def test_empty_input_makes_no_request() -> None:
    """NFR-07: nothing to embed, nothing to send."""
    route = respx.post(EMBED_URL).mock(return_value=embed_response(0))

    assert OllamaProvider(ollama_settings()).embed([]) == []
    assert route.call_count == 0
