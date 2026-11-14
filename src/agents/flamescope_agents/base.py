"""`Agent`: prompt file loading and rendering, the ADK `LlmAgent`, output validation and retry."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, NamedTuple

import structlog
import yaml
from google.adk.agents import LlmAgent
from google.genai import types
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from flamescope_common.errors import LLMError, ValidationError
from flamescope_common.llm.gateway import LLMGateway, ModelCallbacks

logger = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
MAX_SCHEMA_RETRIES = 2
MAX_FEEDBACK_CHARS = 1000
INPUT_JSON_VARIABLE = "input_json"
FEEDBACK_VARIABLE = "validation_feedback"
TEXT_OUTPUT_SCHEMA = "text"
FRONT_MATTER_DELIMITER = "---"
FRONT_MATTER_PARTS = 3

_INCLUDE = re.compile(r"\{\{>\s*([\w./-]+)\s*\}\}")
_VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_SECTION_HEADING = re.compile(r"^## (System|User)[ \t]*$", re.MULTILINE)
_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

Execute = Callable[[LlmAgent, str], Awaitable[str]]


class RenderedPrompt(NamedTuple):
    """The `## System` and `## User` sections with every variable substituted."""

    system: str
    user: str


@dataclass(frozen=True)
class PromptFile:
    """A runtime prompt file after front matter parsing and include resolution."""

    name: str
    version: int
    output_schema: str
    temperature: float
    max_tokens: int
    system: str
    user: str

    @property
    def version_key(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def variables(self) -> set[str]:
        return set(_VARIABLE.findall(self.system)) | set(_VARIABLE.findall(self.user))

    def render(self, values: Mapping[str, str]) -> RenderedPrompt:
        return RenderedPrompt(_substitute(self.system, values), _substitute(self.user, values))


@dataclass(frozen=True)
class AgentRun:
    """A validated agent answer and the number of schema retries it needed."""

    output: BaseModel | str
    retries: int


def _substitute(template: str, values: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise ValueError(f"prompt variable {name!r} has no value")
        return values[name]

    return _VARIABLE.sub(replace, template)


def _resolve_includes(text: str, prompts_dir: Path) -> str:
    def include(match: re.Match[str]) -> str:
        return (prompts_dir / match.group(1)).read_text(encoding="utf-8").strip()

    return _INCLUDE.sub(include, text)


def _split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    parts = raw.split(FRONT_MATTER_DELIMITER, maxsplit=2)
    if len(parts) != FRONT_MATTER_PARTS or parts[0].strip():
        raise ValueError("prompt file must start with a YAML front matter block")
    meta = yaml.safe_load(parts[1])
    if not isinstance(meta, dict):
        raise ValueError("prompt front matter must be a mapping")
    return meta, parts[2]


def _split_sections(body: str) -> dict[str, str]:
    pieces = _SECTION_HEADING.split(body)
    sections = dict(zip(pieces[1::2], (piece.strip() for piece in pieces[2::2]), strict=True))
    if set(sections) != {"System", "User"}:
        raise ValueError("prompt file needs exactly one '## System' and one '## User' section")
    return sections


def load_prompt(name: str, prompts_dir: Path = PROMPTS_DIR) -> PromptFile:
    """Read `<prompts_dir>/<name>.md`, split it and resolve `{{> include}}` directives."""
    raw = (prompts_dir / f"{name}.md").read_text(encoding="utf-8")
    meta, body = _split_front_matter(raw)
    sections = _split_sections(body)
    return PromptFile(
        name=str(meta["name"]),
        version=int(meta["version"]),
        output_schema=str(meta["output_schema"]),
        temperature=float(meta["temperature"]),
        max_tokens=int(meta["max_tokens"]),
        system=_resolve_includes(sections["System"], prompts_dir),
        user=_resolve_includes(sections["User"], prompts_dir),
    )


def _scalar_fields(payload: BaseModel) -> dict[str, str]:
    dumped = payload.model_dump(mode="json")
    return {
        key: str(value)
        for key, value in dumped.items()
        if isinstance(value, str | int | float) and not isinstance(value, bool)
    }


def _strip_code_fence(text: str) -> str:
    return _CODE_FENCE.sub("", text.strip())


class Agent:
    """One runtime agent: a prompt file, an input model, an output model, an ADK `LlmAgent`."""

    name: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]
    output_model: ClassVar[type[BaseModel] | None] = None

    def __init__(self, gateway: LLMGateway, prompts_dir: Path = PROMPTS_DIR) -> None:
        self._gateway = gateway
        self.prompt = load_prompt(self.name, prompts_dir)
        self._check_prompt_matches_contract()

    @property
    def version_key(self) -> str:
        return self.prompt.version_key

    def validate_input(self, payload: BaseModel | Mapping[str, Any]) -> BaseModel:
        """The payload as this agent's input model; invalid input is a `ValidationError`."""
        try:
            return self.input_model.model_validate(payload)
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Invalid input for agent {self.name!r}", json.loads(exc.json())
            ) from exc

    def render(self, payload: BaseModel, validation_feedback: str = "") -> RenderedPrompt:
        values = {
            **_scalar_fields(payload),
            INPUT_JSON_VARIABLE: json.dumps(
                payload.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
            ),
            FEEDBACK_VARIABLE: validation_feedback,
        }
        return self.prompt.render(values)

    def build_llm_agent(self, rendered: RenderedPrompt, callbacks: ModelCallbacks) -> LlmAgent:
        """The ADK agent for one call; a callable `instruction` skips ADK state templating."""
        system = rendered.system
        return LlmAgent(
            name=self.name,
            model=self._gateway.model(),
            instruction=lambda _context: system,
            output_schema=self.output_model,
            tools=[],
            generate_content_config=types.GenerateContentConfig(
                temperature=self.prompt.temperature,
                max_output_tokens=self.prompt.max_tokens,
            ),
            before_model_callback=callbacks.before_model,
            after_model_callback=callbacks.after_model,
        )

    def parse_output(self, text: str) -> BaseModel | str:
        """Validate the model's final text; raises `ValueError` (JSON or schema) on failure."""
        if self.output_model is None:
            return self._plain_text(text)
        return self.output_model.model_validate_json(_strip_code_fence(text))

    async def run_validated(
        self, payload: BaseModel, execute: Execute, callbacks: ModelCallbacks
    ) -> AgentRun:
        """Run until the output validates, retrying with the validation error appended."""
        feedback = ""
        for attempt in range(MAX_SCHEMA_RETRIES + 1):
            rendered = self.render(payload, feedback)
            text = await execute(self.build_llm_agent(rendered, callbacks), rendered.user)
            try:
                return AgentRun(self.parse_output(text), retries=attempt)
            except ValueError as exc:
                feedback = str(exc)[:MAX_FEEDBACK_CHARS]
                logger.warning("agent_output_invalid", agent=self.name, attempt=attempt)
        raise LLMError(
            f"Agent {self.name!r} returned invalid output after {MAX_SCHEMA_RETRIES} retries",
            {"validation_error": feedback},
        )

    def _plain_text(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            raise ValueError("the model returned an empty answer")
        return stripped

    def _check_prompt_matches_contract(self) -> None:
        expected_schema = self.output_model.__name__ if self.output_model else TEXT_OUTPUT_SCHEMA
        if self.prompt.name != self.name or self.prompt.output_schema != expected_schema:
            raise ValueError(
                f"prompt {self.prompt.name}@{self.prompt.version} does not match agent "
                f"{self.name!r} (output {expected_schema})"
            )
        unknown = self.prompt.variables - self.allowed_variables()
        if unknown:
            raise ValueError(f"prompt {self.name!r} uses undeclared variables {sorted(unknown)}")

    @classmethod
    def allowed_variables(cls) -> set[str]:
        """Input model fields plus the two framework variables."""
        return set(cls.input_model.model_fields) | {INPUT_JSON_VARIABLE, FEEDBACK_VARIABLE}
