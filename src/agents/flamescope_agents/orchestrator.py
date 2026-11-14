"""`AgentOrchestrator`: agent registry and ADK `Runner` execution (document 07 section 5)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Coroutine, Mapping
from dataclasses import dataclass
from typing import Any, Literal, overload

import structlog
from google.adk.agents import LlmAgent, RunConfig
from google.adk.agents.run_config import StreamingMode  # type: ignore[attr-defined]
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from flamescope_agents.base import Agent
from flamescope_agents.comparator import ComparatorAgent
from flamescope_agents.earth_apps import EarthAppsAgent
from flamescope_agents.extractor import ExtractorAgent
from flamescope_agents.insight_qa import InsightQAAgent
from flamescope_agents.scenario_interpreter import ScenarioInterpreterAgent
from flamescope_agents.scorer import ScorerAgent
from flamescope_common.config import Settings, get_settings
from flamescope_common.errors import FlameScopeError, LLMError, ValidationError
from flamescope_common.llm.gateway import LLMGateway, ModelCallbacks
from flamescope_common.logging import get_request_id

logger = structlog.get_logger(__name__)

APP_NAME = "flamescope"
ANONYMOUS_USER_ID = "flamescope"
MILLIS_PER_SECOND = 1000.0
AGENT_CLASSES: tuple[type[Agent], ...] = (
    ExtractorAgent,
    ScorerAgent,
    ComparatorAgent,
    ScenarioInterpreterAgent,
    InsightQAAgent,
    EarthAppsAgent,
)


@dataclass
class _CallTrace:
    """What one agent call reports to the log: cache use and the number of model attempts."""

    cache_hit: bool = False
    attempts: int = 0


def _traced(callbacks: ModelCallbacks, trace: _CallTrace) -> ModelCallbacks:
    def before_model(context: Any, llm_request: Any) -> Any:
        response = callbacks.before_model(context, llm_request)
        trace.cache_hit = trace.cache_hit or response is not None
        return response

    return ModelCallbacks(before_model=before_model, after_model=callbacks.after_model)


def _event_text(event: Event) -> str:
    parts = event.content.parts if event.content and event.content.parts else []
    return "".join(part.text for part in parts if part.text)


def _raise_on_error(event: Event) -> None:
    if event.error_code:
        raise LLMError(f"Model call failed: {event.error_message or event.error_code}")


def _wanted_text(event: Event, *, streaming: bool, streamed_any: bool) -> str | None:
    """Partial deltas while streaming; the final text only when nothing was streamed."""
    if streaming and event.partial:
        return _event_text(event)
    if event.is_final_response() and not (streaming and streamed_any):
        return _event_text(event)
    return None


class AgentOrchestrator:
    """Resolves agents by name and runs each through an ADK `Runner`, one session per call."""

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        settings: Settings | None = None,
        agents: Mapping[str, Agent] | None = None,
    ) -> None:
        self._gateway = gateway or LLMGateway(settings)
        self._settings = settings or get_settings()
        built = agents or {cls.name: cls(self._gateway) for cls in AGENT_CLASSES}
        self._agents: dict[str, Agent] = dict(built)

    @overload
    def run(
        self, name: str, payload: BaseModel | Mapping[str, Any], *, stream: Literal[False] = False
    ) -> Coroutine[Any, Any, BaseModel | str]: ...

    @overload
    def run(
        self, name: str, payload: BaseModel | Mapping[str, Any], *, stream: Literal[True]
    ) -> AsyncIterator[str]: ...

    def run(
        self, name: str, payload: BaseModel | Mapping[str, Any], *, stream: bool = False
    ) -> Coroutine[Any, Any, BaseModel | str] | AsyncIterator[str]:
        """`await run(name, payload)` gives the validated output model (or the full text for
        a plain-text agent); `async for delta in run(name, payload, stream=True)` streams text.
        """
        agent = self._resolve(name)
        validated = agent.validate_input(payload)
        if stream:
            return self._stream(agent, validated)
        return self._run_validated(agent, validated)

    def agent_names(self) -> list[str]:
        return sorted(self._agents)

    def prompt_version(self, name: str) -> str:
        """Version key such as `scorer@1`, stored with results."""
        return self._resolve(name).version_key

    def _resolve(self, name: str) -> Agent:
        agent = self._agents.get(name)
        if agent is None:
            raise ValidationError(f"Unknown agent {name!r}", {"known": self.agent_names()})
        return agent

    async def _run_validated(self, agent: Agent, payload: BaseModel) -> BaseModel | str:
        trace = _CallTrace()
        callbacks = _traced(self._gateway.callbacks(), trace)
        started = time.monotonic()

        async def counted_execute(llm_agent: LlmAgent, user_message: str) -> str:
            # Counting attempts here keeps `retries` right in the log when the run fails.
            trace.attempts += 1
            return await self._execute(llm_agent, user_message)

        try:
            run = await agent.run_validated(payload, counted_execute, callbacks)
            return run.output
        finally:
            self._log(agent, started, trace, retries=max(trace.attempts - 1, 0))

    async def _stream(self, agent: Agent, payload: BaseModel) -> AsyncIterator[str]:
        trace = _CallTrace()
        started = time.monotonic()
        rendered = agent.render(payload)
        llm_agent = agent.build_llm_agent(rendered, _traced(self._gateway.callbacks(), trace))
        try:
            async for delta in self._text_events(
                llm_agent, rendered.user, RunConfig(streaming_mode=StreamingMode.SSE)
            ):
                yield delta
        finally:
            self._log(agent, started, trace, retries=0)

    async def _execute(self, llm_agent: LlmAgent, user_message: str) -> str:
        text = ""
        async for chunk in self._text_events(llm_agent, user_message, RunConfig()):
            text += chunk
        return text

    async def _text_events(
        self, llm_agent: LlmAgent, user_message: str, run_config: RunConfig
    ) -> AsyncIterator[str]:
        """Text of the run: partial deltas when streaming, else the final response text."""
        streaming = run_config.streaming_mode == StreamingMode.SSE
        streamed_any = False
        try:
            async for event in self._events(llm_agent, user_message, run_config):
                _raise_on_error(event)
                text = _wanted_text(event, streaming=streaming, streamed_any=streamed_any)
                streamed_any = streamed_any or (streaming and bool(event.partial))
                if text is not None:
                    yield text
        except FlameScopeError:
            raise
        except Exception as exc:
            raise LLMError(f"Agent run failed: {exc}") from exc

    async def _events(
        self, llm_agent: LlmAgent, user_message: str, run_config: RunConfig
    ) -> AsyncIterator[Event]:
        sessions = InMemorySessionService()
        user_id = get_request_id() or ANONYMOUS_USER_ID
        session = await sessions.create_session(app_name=APP_NAME, user_id=user_id)
        runner = Runner(app_name=APP_NAME, agent=llm_agent, session_service=sessions)
        message = types.Content(role="user", parts=[types.Part(text=user_message)])
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=message,
            run_config=run_config,
        ):
            yield event

    def _log(self, agent: Agent, started: float, trace: _CallTrace, retries: int) -> None:
        logger.info(
            "agent_run",
            agent=agent.name,
            prompt_version=agent.version_key,
            provider=self._settings.llm_provider,
            model=self._model_name(),
            latency_ms=round((time.monotonic() - started) * MILLIS_PER_SECOND, 1),
            cache_hit=trace.cache_hit,
            retries=retries,
        )

    def _model_name(self) -> str:
        return "mock" if self._settings.llm_provider == "mock" else self._settings.llm_model
