"""FR-01, NFR-05: the `flamescope-ingest` CLI (document 06 section 4; document 03 section 7).

Command names and options are parsed from the document's CLI block and compared with the
Typer app; behaviour is exercised with a fake pipeline (no database, no network, no LLM).
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.core import TyperGroup
from typer.testing import CliRunner

from flamescope_ingest import cli
from flamescope_ingest.pipeline import (
    SEED_STAGES,
    STAGE_ORDER,
    STATUS_FAILED,
    InvestigationRun,
    PipelineResult,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_06 = REPO_ROOT / "docs" / "architecture" / "06-ingestion-pipeline.md"
CLI_LINE = re.compile(r"^flamescope-ingest (\S+)(.*)$")
OPTION = re.compile(r"--[a-z-]+")
STAGE_ROW = re.compile(r"^\| (\d) \| (\w+) \|", re.MULTILINE)
CODE_BLOCK = re.compile(r"```\n(.*?)```", re.DOTALL)


def _documented_commands() -> dict[str, set[str]]:
    """Command name to its options, from the code block of document 06 section 4."""
    text = DOC_06.read_text(encoding="utf-8")
    section = text[text.index("## 4. CLI") : text.index("## 5. Seed file format")]
    block = CODE_BLOCK.search(section)
    assert block is not None
    commands: dict[str, set[str]] = {}
    for line in block.group(1).splitlines():
        match = CLI_LINE.match(line.split("#")[0].strip())
        if match:
            commands[match.group(1)] = set(OPTION.findall(match.group(2)))
    return commands


def _documented_stages() -> list[str]:
    text = DOC_06.read_text(encoding="utf-8")
    return [name for _, name in STAGE_ROW.findall(text)]


def _click_group() -> TyperGroup:
    group = typer.main.get_command(cli.app)
    assert isinstance(group, TyperGroup)
    return group


def _options(command: Any) -> set[str]:
    return {opt for param in command.params for opt in param.opts if opt.startswith("--")}


class FakePipeline:
    """Records `run` calls and returns a fixed result."""

    def __init__(self, result: PipelineResult | None = None, error: Exception | None = None):
        self.calls: list[dict[str, Any]] = []
        self._result = result or PipelineResult()
        self._error = error

    def run(
        self, ids: Sequence[str], stages: Sequence[str], *, mode: str | None, force: bool = False
    ) -> PipelineResult:
        self.calls.append({"ids": list(ids), "stages": list(stages), "mode": mode, "force": force})
        if self._error is not None:
            raise self._error
        return self._result


@pytest.fixture
def fake_pipeline(monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakePipeline]:
    def install(**kwargs: Any) -> FakePipeline:
        pipeline = FakePipeline(**kwargs)
        monkeypatch.setattr(cli, "_pipeline", lambda: pipeline)
        return pipeline

    return install


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_documented_command_list_is_parsed() -> None:
    commands = _documented_commands()
    assert set(commands) == {
        "migrate",
        "seed",
        "discover",
        "harvest",
        "run",
        "score",
        "index",
        "review",
        "export-seed",
        "status",
    }


def test_app_registers_exactly_the_documented_commands() -> None:
    """Typer app `flamescope-ingest` with the commands of document 06 section 4, nothing extra."""
    assert set(_click_group().commands) == set(_documented_commands())


@pytest.mark.parametrize("name", sorted(_documented_commands()))
def test_command_options_equal_document(name: str) -> None:
    command = _click_group().commands[name]
    assert _options(command) == _documented_commands()[name]


def test_only_option_is_repeatable() -> None:
    """`--only ACR ...` takes several acronyms."""
    only = next(p for p in _click_group().commands["seed"].params if "--only" in p.opts)
    assert getattr(only, "multiple", False)


def test_console_script_name() -> None:
    """The console script is `flamescope-ingest` pointing at the Typer app (document 03 s7)."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"]["flamescope-ingest"] == "flamescope_ingest.cli:app"
    assert cli.app.info.name == "flamescope-ingest"


def test_stage_order_equals_document() -> None:
    """Stages 1 to 9 in the order of document 06 section 2."""
    assert list(STAGE_ORDER) == _documented_stages()
    assert len(STAGE_ORDER) == 9


def test_seed_stages_are_normalize_to_review() -> None:
    """`seed` runs stages normalize..review (document 06 section 4)."""
    stages = _documented_stages()
    assert list(SEED_STAGES) == stages[stages.index("normalize") :]


def test_seed_runs_seed_mode(
    runner: CliRunner, fake_pipeline: Callable[..., FakePipeline]
) -> None:
    pipeline = fake_pipeline()
    result = runner.invoke(cli.app, ["seed", "--only", "BASS", "--only", "FLEX"])
    assert result.exit_code == 0, result.output
    assert pipeline.calls == [
        {"ids": ["BASS", "FLEX"], "stages": list(SEED_STAGES), "mode": "seed", "force": False}
    ]


def test_harvest_needs_ollama(
    runner: CliRunner, fake_pipeline: Callable[..., FakePipeline]
) -> None:
    """`harvest` needs `LLM_PROVIDER=ollama` (document 06 section 4); tests force mock."""
    pipeline = fake_pipeline()
    result = runner.invoke(cli.app, ["harvest"])
    assert result.exit_code != 0
    assert "LLM_PROVIDER=ollama" in result.output
    assert pipeline.calls == []


@pytest.mark.parametrize("stages", ["extract", "parse,score"])
def test_run_with_llm_stage_needs_ollama(
    stages: str, runner: CliRunner, fake_pipeline: Callable[..., FakePipeline]
) -> None:
    pipeline = fake_pipeline()
    result = runner.invoke(cli.app, ["run", "--stages", stages])
    assert result.exit_code != 0
    assert pipeline.calls == []


def test_run_without_llm_stage_works_in_mock_mode(
    runner: CliRunner, fake_pipeline: Callable[..., FakePipeline]
) -> None:
    pipeline = fake_pipeline()
    result = runner.invoke(cli.app, ["run", "--stages", "parse, index", "--force"])
    assert result.exit_code == 0, result.output
    assert pipeline.calls == [
        {"ids": [], "stages": ["parse", "index"], "mode": "harvest", "force": True}
    ]


@pytest.mark.parametrize("command", ["score", "index"])
def test_single_stage_commands(
    command: str, runner: CliRunner, fake_pipeline: Callable[..., FakePipeline]
) -> None:
    pipeline = fake_pipeline()
    result = runner.invoke(cli.app, [command, "--only", "SPICE", "--force"])
    assert result.exit_code == 0, result.output
    assert pipeline.calls[0]["stages"] == [command]
    assert pipeline.calls[0]["force"] is True


def test_failed_pipeline_exits_non_zero(
    runner: CliRunner, fake_pipeline: Callable[..., FakePipeline]
) -> None:
    failed = PipelineResult()
    failed.add(
        InvestigationRun(acronym="X", mode="seed", stages=[], force=False, status=STATUS_FAILED)
    )
    fake_pipeline(result=failed)
    assert runner.invoke(cli.app, ["seed"]).exit_code != 0


def test_review_always_exits_zero(
    runner: CliRunner, fake_pipeline: Callable[..., FakePipeline]
) -> None:
    """Stage 9: exit code 0 always (document 06 section 3.9)."""
    from flamescope_common.errors import IngestError

    pipeline = fake_pipeline(error=IngestError("database unavailable"))
    result = runner.invoke(cli.app, ["review"])
    assert result.exit_code == 0
    assert pipeline.calls[0]["stages"] == ["review"]
