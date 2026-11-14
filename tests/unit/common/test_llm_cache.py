"""Response cache through ADK model callbacks (document 07 section 6; document 03 section 2)."""

from __future__ import annotations

import json
from typing import Any, ClassVar

import pytest
from google.adk.agents import LlmAgent, RunConfig
from google.adk.agents.run_config import StreamingMode  # type: ignore[attr-defined]
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from flamescope_common.config import Settings
from flamescope_common.llm.cache import cache_key
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.llm.providers.mock import MockLlm

pytestmark = pytest.mark.unit

SHA256_HEX_LENGTH = 64
QA_INPUT = {
    "question": "What burned?",
    "chunks": [{"chunk_id": 1, "acronym": "A", "doc_title": "Doc", "text": "A test burned."}],
}


class CountingMockLlm(MockLlm):
    """`MockLlm` that counts how often the provider is actually called."""

    calls: ClassVar[list[int]] = []

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> Any:
        CountingMockLlm.calls.append(1)
        async for response in super().generate_content_async(llm_request, stream=stream):
            yield response


class Verdict(BaseModel):
    """A stand-in agent output model for the schema-validation cache rule."""

    verdict: str


class ScriptedLlm(BaseLlm):
    """Model that always answers `reply` and counts its calls."""

    model: str = "mock"
    reply: ClassVar[str] = ""
    calls: ClassVar[list[int]] = []

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> Any:
        ScriptedLlm.calls.append(1)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=ScriptedLlm.reply)])
        )


class ScriptedProvider:
    name = "mock"

    def model(self) -> BaseLlm:
        return ScriptedLlm()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


class CountingProvider:
    name = "mock"

    def model(self) -> BaseLlm:
        return CountingMockLlm()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


@pytest.fixture
def counting_gateway(llm_cache: object) -> LLMGateway:
    CountingMockLlm.calls.clear()
    return LLMGateway(
        settings=Settings(_env_file=None),  # type: ignore[call-arg]
        cache=llm_cache,  # type: ignore[arg-type]
        providers={"mock": CountingProvider()},
    )


@pytest.fixture
def scripted_gateway(llm_cache: object) -> LLMGateway:
    ScriptedLlm.calls.clear()
    return LLMGateway(
        settings=Settings(_env_file=None),  # type: ignore[call-arg]
        cache=llm_cache,  # type: ignore[arg-type]
        providers={"mock": ScriptedProvider()},
    )


async def run_once(
    gateway: LLMGateway, run_config: RunConfig, output_schema: type[BaseModel] | None = None
) -> str:
    callbacks = gateway.callbacks()
    agent = LlmAgent(
        name="insight_qa",
        model=gateway.model(),
        instruction=lambda _context: "Answer with citations.",
        output_schema=output_schema,
        before_model_callback=callbacks.before_model,
        after_model_callback=callbacks.after_model,
    )
    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name="flamescope", user_id="test")
    runner = Runner(app_name="flamescope", agent=agent, session_service=sessions)
    message = types.Content(role="user", parts=[types.Part(text=json.dumps(QA_INPUT))])
    texts = [
        event.content.parts[0].text
        async for event in runner.run_async(
            user_id="test", session_id=session.id, new_message=message, run_config=run_config
        )
        if event.is_final_response() and event.content and event.content.parts
    ]
    return texts[-1]


def test_cache_key_is_sha256_of_its_inputs() -> None:
    """NFR-07: keyed by SHA-256 of provider, model, prompt and parameters."""
    key = cache_key("mock", "mock", "prompt", {"temperature": 0.0})

    assert len(key) == SHA256_HEX_LENGTH
    assert key == cache_key("mock", "mock", "prompt", {"temperature": 0.0})


@pytest.mark.parametrize(
    "changed",
    [
        ("ollama", "mock", "prompt", {"temperature": 0.0}),
        ("mock", "qwen2.5:0.5b", "prompt", {"temperature": 0.0}),
        ("mock", "mock", "other prompt", {"temperature": 0.0}),
        ("mock", "mock", "prompt", {"temperature": 0.1}),
    ],
)
def test_cache_key_changes_with_each_input(changed: tuple[str, str, str, dict[str, Any]]) -> None:
    """NFR-07: provider, model, prompt and parameters all contribute to the key."""
    assert cache_key(*changed) != cache_key("mock", "mock", "prompt", {"temperature": 0.0})


async def test_cache_hit_avoids_a_second_provider_call(
    counting_gateway: LLMGateway, llm_cache: Any
) -> None:
    """NFR-07: an identical request is answered from `llm_cache`."""
    first = await run_once(counting_gateway, RunConfig())
    second = await run_once(counting_gateway, RunConfig())

    assert first == second
    assert len(CountingMockLlm.calls) == 1
    assert [(provider, model) for _key, provider, model in llm_cache.writes] == [("mock", "mock")]


async def test_streaming_bypasses_the_cache(counting_gateway: LLMGateway, llm_cache: Any) -> None:
    """NFR-07: the cache is disabled for streaming (`StreamingMode.SSE`)."""
    streaming = RunConfig(streaming_mode=StreamingMode.SSE)

    await run_once(counting_gateway, streaming)
    await run_once(counting_gateway, streaming)

    assert len(CountingMockLlm.calls) == 2
    assert llm_cache.writes == []


@pytest.mark.parametrize(
    ("reply", "output_schema"),
    [('{"answer": "no verdict field"}', Verdict), ("not json", Verdict), ("   ", None)],
)
async def test_invalid_reply_is_not_cached_so_a_retry_reaches_the_model(
    scripted_gateway: LLMGateway,
    llm_cache: Any,
    reply: str,
    output_schema: type[BaseModel] | None,
) -> None:
    """NFR-07: only replies valid for the request's `output_schema` are cached (doc 07 s6)."""
    ScriptedLlm.reply = reply

    await run_once(scripted_gateway, RunConfig(), output_schema)
    await run_once(scripted_gateway, RunConfig(), output_schema)

    assert (len(ScriptedLlm.calls), llm_cache.writes) == (2, [])


@pytest.mark.parametrize(
    ("reply", "output_schema"),
    [('{"verdict": "ok"}', Verdict), ('```json\n{"verdict": "ok"}\n```', Verdict), ("Ok.", None)],
)
async def test_valid_reply_is_cached(
    scripted_gateway: LLMGateway,
    llm_cache: Any,
    reply: str,
    output_schema: type[BaseModel] | None,
) -> None:
    """NFR-07: a schema-valid (or non-empty plain-text) reply is served from the cache."""
    ScriptedLlm.reply = reply

    await run_once(scripted_gateway, RunConfig(), output_schema)
    await run_once(scripted_gateway, RunConfig(), output_schema)

    assert (len(ScriptedLlm.calls), len(llm_cache.writes)) == (1, 1)
