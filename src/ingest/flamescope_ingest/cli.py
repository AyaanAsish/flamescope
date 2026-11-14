"""Typer app `flamescope-ingest` (document 06 section 4)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer
from alembic import command
from alembic.config import Config

import flamescope_common
from flamescope_common.config import get_settings
from flamescope_common.errors import FlameScopeError, IngestError
from flamescope_common.logging import configure_logging
from flamescope_ingest.pipeline import (
    SEED_STAGES,
    STAGE_ORDER,
    STATUS_FAILED,
    Mode,
    Pipeline,
    PipelineResult,
    build_pipeline,
)
from flamescope_ingest.review import render_table
from flamescope_ingest.seed import SeedExporter

app = typer.Typer(
    name="flamescope-ingest", help="FlameScope ingestion pipeline.", no_args_is_help=True
)

OnlyOption = Annotated[
    list[str] | None, typer.Option("--only", help="Restrict to this acronym; repeatable.")
]
ForceOption = Annotated[bool, typer.Option("--force", help="Rerun stages whose key is unchanged.")]
StagesOption = Annotated[
    str | None, typer.Option("--stages", help="Comma-separated stages, for example parse,extract.")
]
EXIT_FAILURE = 1
STAGE_SEPARATOR = ","
LLM_STAGES = ("extract", "score")
ALEMBIC_INI = Path(flamescope_common.__file__).parent / "alembic.ini"


def _fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code=EXIT_FAILURE)


def _pipeline() -> Pipeline:
    return build_pipeline()


def _require_ollama(stages: Sequence[str]) -> None:
    provider = get_settings().llm_provider
    if provider != "ollama" and any(stage in LLM_STAGES for stage in stages):
        raise IngestError(
            "Harvest extraction needs a live model: set LLM_PROVIDER=ollama "
            f"(currently {provider!r}). Seed mode works offline."
        )


def _report(result: PipelineResult) -> None:
    for run in result.runs:
        typer.echo(f"{run.acronym:<20} {run.status:<8} llm_calls={run.llm_calls}")
        for error in run.errors:
            typer.echo(f"  error: {error}", err=True)
    typer.echo(f"pipeline status: {result.status}")


def _execute(
    only: list[str] | None, stages: Sequence[str], mode: Mode | None, force: bool
) -> None:
    try:
        result = _pipeline().run(only or [], stages, mode=mode, force=force)
    except FlameScopeError as error:
        raise _fail(error.message) from error
    _report(result)
    if result.status == STATUS_FAILED:
        raise typer.Exit(code=EXIT_FAILURE)


@app.callback()
def main() -> None:
    configure_logging(get_settings().log_level)


@app.command()
def migrate() -> None:
    """Apply the database schema (alembic upgrade head)."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    typer.echo("database is at head")


@app.command()
def seed(only: OnlyOption = None) -> None:
    """Stages normalize to review from the seed files; no network."""
    _execute(only, SEED_STAGES, "seed", force=False)


@app.command()
def discover() -> None:
    """List the public bucket and write manifests; downloads nothing."""
    try:
        acronyms = _pipeline().discover()
    except FlameScopeError as error:
        raise _fail(
            f"{error.message}. Seed mode needs no network: run `flamescope-ingest seed`."
        ) from error
    typer.echo(f"discovered {len(acronyms)} investigation folder(s): {', '.join(acronyms)}")


@app.command()
def harvest(only: OnlyOption = None) -> None:
    """Full harvest ingestion: discover, harvest, parse, extract, then normalize to review."""
    try:
        _require_ollama(STAGE_ORDER)
    except IngestError as error:
        raise _fail(error.message) from error
    _execute(only, STAGE_ORDER, "harvest", force=False)


@app.command()
def run(only: OnlyOption = None, stages: StagesOption = None, force: ForceOption = False) -> None:
    """Run chosen harvest-mode stages (default: all) for the chosen investigations."""
    chosen = [s.strip() for s in stages.split(STAGE_SEPARATOR)] if stages else list(STAGE_ORDER)
    try:
        _require_ollama(chosen)
    except IngestError as error:
        raise _fail(error.message) from error
    _execute(only, chosen, "harvest", force)


@app.command()
def score(only: OnlyOption = None, force: ForceOption = False) -> None:
    """Stage 7 only, for investigations already loaded."""
    _execute(only, ("score",), None, force)


@app.command()
def index(only: OnlyOption = None, force: ForceOption = False) -> None:
    """Stage 8 only, for investigations already loaded."""
    _execute(only, ("index",), None, force)


@app.command()
def review() -> None:
    """Stage 9 for every loaded investigation; the exit code is always 0."""
    try:
        result = _pipeline().run([], ("review",), mode=None)
    except FlameScopeError as error:
        typer.echo(error.message, err=True)
        return
    typer.echo(render_table(item for outcome in result.runs for item in outcome.review_items))


@app.command("export-seed")
def export_seed(only: OnlyOption = None) -> None:
    """Write reviewed cards (or the named ones) to src/data/seed/investigations/."""
    from flamescope_common.db import SessionLocal

    settings = get_settings()
    try:
        with SessionLocal() as session:
            written = SeedExporter(session, settings.data_dir).export(only)
    except FlameScopeError as error:
        raise _fail(error.message) from error
    for path in written:
        typer.echo(f"wrote {path}")
    typer.echo(f"exported {len(written)} card(s)")


@app.command()
def status() -> None:
    """Last ingest run per investigation."""
    for entry in _pipeline().last_runs():
        finished = entry.finished_at.isoformat() if entry.finished_at else "-"
        typer.echo(
            f"{entry.report.get('acronym', '?'):<20} {entry.mode:<8} {entry.status:<8} {finished}"
        )
