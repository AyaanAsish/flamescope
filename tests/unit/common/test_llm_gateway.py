"""`LLMGateway`: provider selection, batching, retry, timeout and provider isolation.

Document 07 section 6; document 02 section 2 import rules; NFR-07.
"""

from __future__ import annotations

import ast
from pathlib import Path

import httpx
import pytest
import respx
from google.adk.models import BaseLlm
from google.adk.models.lite_llm import LiteLlm

from flamescope_common.config import Settings
from flamescope_common.errors import LLMError
from flamescope_common.llm.gateway import LLMGateway, ModelCallbacks
from flamescope_common.llm.providers import ollama as ollama_module
from flamescope_common.llm.providers.mock import MockLlm

pytestmark = pytest.mark.unit

OLLAMA_URL = "http://ollama.test:11434"
EMBED_URL = f"{OLLAMA_URL}/api/embed"
EMBED_DIM = 8
BATCH_SIZE = 64
TRANSIENT_RETRIES = 3
SRC = Path(__file__).resolve().parents[3] / "src"
PYTHON_PACKAGES = ("common", "agents", "api", "ingest")
PROVIDERS_PACKAGE = SRC / "common" / "flamescope_common" / "llm" / "providers"
LLM_PACKAGE = SRC / "common" / "flamescope_common" / "llm"
AGENTS_PACKAGE = SRC / "agents" / "flamescope_agents"
PROVIDER_SDK_MODULES = ("litellm", "google.adk.models.lite_llm", "ollama")
ADK_MODEL_MODULES = ("google.adk.models",)
ADK_AGENT_MODULES = ("google.adk.agents", "google.adk.runners", "google.adk.sessions")


class RecordingProvider:
    """A fake `LLMProvider` that records the batch sizes it was asked to embed."""

    name = "mock"

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def model(self) -> BaseLlm:
        return MockLlm()

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[1.0] + [0.0] * (EMBED_DIM - 1) for _ in texts]


def gateway_for(llm_cache: object, **overrides: object) -> LLMGateway:
    values: dict[str, object] = {
        "llm_provider": "mock",
        "ollama_base_url": OLLAMA_URL,
        "embed_dim": EMBED_DIM,
    }
    settings = Settings(_env_file=None, **(values | overrides))  # type: ignore[call-arg]
    return LLMGateway(settings=settings, cache=llm_cache)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_module.time, "sleep", lambda _seconds: None)


def embed_response(count: int) -> httpx.Response:
    return httpx.Response(200, json={"embeddings": [[0.5] * EMBED_DIM for _ in range(count)]})


def test_mock_setting_selects_mock_llm(llm_cache: object) -> None:
    """NFR-02: `LLM_PROVIDER=mock` gives the deterministic ADK `MockLlm`."""
    assert isinstance(gateway_for(llm_cache).model(), MockLlm)


def test_ollama_setting_selects_lite_llm(llm_cache: object) -> None:
    """NFR-07: `LLM_PROVIDER=ollama` gives ADK `LiteLlm` for Ollama."""
    model = gateway_for(llm_cache, llm_provider="ollama").model()

    assert isinstance(model, LiteLlm)
    assert model.model.startswith("ollama_chat/")


@respx.mock
def test_embed_provider_is_independent_of_llm_provider(llm_cache: object) -> None:
    """NFR-07: `EMBED_PROVIDER=mock` with `LLM_PROVIDER=ollama` embeds without network."""
    route = respx.post(EMBED_URL)
    gateway = gateway_for(llm_cache, llm_provider="ollama", embed_provider="mock")

    vectors = gateway.embed(["flame"])

    assert len(vectors[0]) == EMBED_DIM
    assert route.call_count == 0


def test_embed_requests_batches_of_64(llm_cache: object) -> None:
    """NFR-07: embeddings are requested in batches of 64 (document 07 section 6)."""
    provider = RecordingProvider()
    gateway = LLMGateway(
        settings=Settings(_env_file=None, embed_dim=EMBED_DIM),  # type: ignore[call-arg]
        cache=llm_cache,  # type: ignore[arg-type]
        providers={"mock": provider},
    )

    vectors = gateway.embed([f"text {index}" for index in range(2 * BATCH_SIZE + 2)])

    assert provider.batch_sizes == [BATCH_SIZE, BATCH_SIZE, 2]
    assert len(vectors) == 2 * BATCH_SIZE + 2


def test_callbacks_are_adk_before_and_after_model_callbacks(llm_cache: object) -> None:
    """NFR-07: `callbacks()` returns the ADK model callback pair."""
    callbacks = gateway_for(llm_cache).callbacks()

    assert isinstance(callbacks, ModelCallbacks)
    assert callable(callbacks.before_model)
    assert callable(callbacks.after_model)


@respx.mock
def test_transient_errors_are_retried(llm_cache: object) -> None:
    """NFR-07: retry with backoff on transient errors (3 attempts)."""
    route = respx.post(EMBED_URL).mock(
        side_effect=[httpx.Response(503), httpx.ReadTimeout("slow"), embed_response(1)]
    )

    vectors = gateway_for(llm_cache, embed_provider="ollama").embed(["flame"])

    assert route.call_count == TRANSIENT_RETRIES
    assert len(vectors) == 1


@respx.mock
def test_persistent_failure_raises_llm_error_after_three_attempts(llm_cache: object) -> None:
    """NFR-07: callers get `LLMError` once retries are exhausted."""
    route = respx.post(EMBED_URL).mock(return_value=httpx.Response(503))

    with pytest.raises(LLMError):
        gateway_for(llm_cache, embed_provider="ollama").embed(["flame"])
    assert route.call_count == TRANSIENT_RETRIES


@respx.mock
def test_client_errors_are_not_retried(llm_cache: object) -> None:
    """NFR-07: only transient errors are retried."""
    route = respx.post(EMBED_URL).mock(return_value=httpx.Response(404))

    with pytest.raises(LLMError):
        gateway_for(llm_cache, embed_provider="ollama").embed(["flame"])
    assert route.call_count == 1


@respx.mock
def test_requests_use_llm_timeout(llm_cache: object) -> None:
    """NFR-07: `LLM_TIMEOUT_S` is the request timeout."""
    route = respx.post(EMBED_URL).mock(return_value=embed_response(1))

    gateway_for(llm_cache, embed_provider="ollama", llm_timeout_s=9.0).embed(["flame"])

    assert route.calls.last.request.extensions["timeout"]["read"] == 9.0


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def files_importing(prefixes: tuple[str, ...]) -> set[Path]:
    python_files = [path for package in PYTHON_PACKAGES for path in (SRC / package).rglob("*.py")]
    return {
        path
        for path in python_files
        if any(m == p or m.startswith(f"{p}.") for m in imported_modules(path) for p in prefixes)
    }


def test_provider_sdks_are_imported_only_in_the_providers_package() -> None:
    """NFR-07: LiteLLM and Ollama clients only in `llm/providers/` (document 07 section 6)."""
    offenders = {
        p for p in files_importing(PROVIDER_SDK_MODULES) if PROVIDERS_PACKAGE not in p.parents
    }

    assert offenders == set()


def test_adk_model_classes_are_imported_only_in_the_llm_package() -> None:
    """NFR-07: ADK model classes only in `flamescope_common/llm/` (document 07 section 6)."""
    offenders = {p for p in files_importing(ADK_MODEL_MODULES) if LLM_PACKAGE not in p.parents}

    assert offenders == set()


def test_adk_agent_classes_are_imported_only_in_the_agents_package() -> None:
    """NFR-07: `LlmAgent`, `Runner`, sessions only in `flamescope_agents` (document 07 s6)."""
    offenders = {p for p in files_importing(ADK_AGENT_MODULES) if AGENTS_PACKAGE not in p.parents}

    assert offenders == set()
