"""NFR-07, NFR-12: static import rules (document 03 section 10; document 02 section 2 rules 4, 6).

Imports are read with `ast`, including function-local and `TYPE_CHECKING` imports, and
relative imports are resolved to absolute module names before checking.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
PACKAGE_DIRS = {
    "flamescope_common": SRC / "common" / "flamescope_common",
    "flamescope_agents": SRC / "agents" / "flamescope_agents",
    "flamescope_api": SRC / "api" / "flamescope_api",
    "flamescope_ingest": SRC / "ingest" / "flamescope_ingest",
}
FIRST_PARTY = tuple(PACKAGE_DIRS)
ROUTERS = "flamescope_api.routers"
SERVICES = "flamescope_api.services"
REPOSITORIES = "flamescope_api.repositories"
LLM_PACKAGE = "flamescope_common.llm"
PROVIDERS_PACKAGE = "flamescope_common.llm.providers"
ADK_RUNTIME = ("google.adk.agents", "google.adk.runners", "google.adk.sessions")
ADK_MODELS = ("google.adk.models",)
LITELLM = ("litellm", "google.adk.models.lite_llm")
DATABASE_ACCESS = ("sqlalchemy", "flamescope_common.db")

# Document 03 section 10: first-party packages each package may import (besides itself).
ALLOWED_FIRST_PARTY = {
    "flamescope_common": (),
    "flamescope_agents": ("flamescope_common",),
    "flamescope_ingest": ("flamescope_common", "flamescope_agents"),
    "flamescope_api": ("flamescope_common", "flamescope_agents"),
}


@dataclass(frozen=True)
class ImportEdge:
    importer: str
    imported: str

    def __str__(self) -> str:
        return f"{self.importer} -> {self.imported}"


def _module_name(package: str, path: Path) -> str:
    relative = path.relative_to(PACKAGE_DIRS[package]).with_suffix("")
    parts = [package, *relative.parts]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _package_of(module: str, path: Path) -> list[str]:
    parts = module.split(".")
    return parts if path.name == "__init__.py" else parts[:-1]


def _resolve_from(node: ast.ImportFrom, module: str, path: Path) -> list[str]:
    """Absolute names for a `from ... import ...`, including possible submodule targets."""
    if node.level == 0:
        base = node.module or ""
    else:
        package = _package_of(module, path)
        anchor = package[: len(package) - (node.level - 1)]
        base = ".".join([*anchor, node.module] if node.module else anchor)
    return [base, *(f"{base}.{alias.name}" for alias in node.names)]


def imports_of(source: str, module: str, path: Path) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported |= set(_resolve_from(node, module, path))
    return imported


def _python_files(directory: Path) -> Iterator[Path]:
    yield from (
        path for path in sorted(directory.rglob("*.py")) if "__pycache__" not in path.parts
    )


def all_edges() -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    for package, directory in PACKAGE_DIRS.items():
        for path in _python_files(directory):
            module = _module_name(package, path)
            source = path.read_text(encoding="utf-8")
            edges += [
                ImportEdge(module, name) for name in sorted(imports_of(source, module, path))
            ]
    return edges


def _within(name: str, prefixes: tuple[str, ...] | str) -> bool:
    options = (prefixes,) if isinstance(prefixes, str) else prefixes
    return any(name == prefix or name.startswith(prefix + ".") for prefix in options)


@pytest.fixture(scope="module")
def edges() -> list[ImportEdge]:
    found = all_edges()
    assert found, "no imports found: package paths of document 02 section 4 changed?"
    return found


@pytest.mark.parametrize("package", sorted(ALLOWED_FIRST_PARTY))
def test_package_dependency_table(package: str, edges: list[ImportEdge]) -> None:
    """Document 03 section 10: each package imports only the packages its row allows."""
    allowed = (package, *ALLOWED_FIRST_PARTY[package])
    violations = [
        str(edge)
        for edge in edges
        if _within(edge.importer, package)
        and _within(edge.imported, FIRST_PARTY)
        and not _within(edge.imported, allowed)
    ]
    assert violations == []


def test_ingest_never_imports_api(edges: list[ImportEdge]) -> None:
    """Document 03 section 7: C-ING never imports from `flamescope_api`."""
    violations = [
        str(e)
        for e in edges
        if _within(e.importer, "flamescope_ingest") and _within(e.imported, "flamescope_api")
    ]
    assert violations == []


def test_routers_never_import_repositories_or_agents(edges: list[ImportEdge]) -> None:
    """Document 03 section 10: routers use services, deps and schemas only."""
    violations = [
        str(e)
        for e in edges
        if _within(e.importer, ROUTERS)
        and _within(e.imported, (REPOSITORIES, "flamescope_agents"))
    ]
    assert violations == []


def test_services_never_import_routers(edges: list[ImportEdge]) -> None:
    """Document 03 section 10: services import repositories, orchestrator, common."""
    violations = [
        str(e) for e in edges if _within(e.importer, SERVICES) and _within(e.imported, ROUTERS)
    ]
    assert violations == []


def test_database_access_only_below_repositories(edges: list[ImportEdge]) -> None:
    """Document 02 section 2 rule 4: services reach the database only through repositories."""
    violations = [
        str(e)
        for e in edges
        if _within(e.importer, (ROUTERS, SERVICES)) and _within(e.imported, DATABASE_ACCESS)
    ]
    assert violations == []


def test_adk_agent_runtime_only_in_agents(edges: list[ImportEdge]) -> None:
    """Document 07 section 6: `LlmAgent`, `Runner`, sessions only in `flamescope_agents`."""
    violations = [
        str(e)
        for e in edges
        if _within(e.imported, ADK_RUNTIME) and not _within(e.importer, "flamescope_agents")
    ]
    assert violations == []


def test_adk_model_classes_only_in_llm_package(edges: list[ImportEdge]) -> None:
    """Document 07 section 6: ADK model classes (`BaseLlm`, `LiteLlm`) only in `llm/`."""
    violations = [
        str(e)
        for e in edges
        if _within(e.imported, ADK_MODELS) and not _within(e.importer, LLM_PACKAGE)
    ]
    assert violations == []


def test_litellm_only_in_providers(edges: list[ImportEdge]) -> None:
    """Document 02 section 2 rule 6: only `llm/providers/` imports LiteLLM."""
    violations = [
        str(e)
        for e in edges
        if _within(e.imported, LITELLM) and not _within(e.importer, PROVIDERS_PACKAGE)
    ]
    assert violations == []


def test_checker_resolves_relative_and_local_imports(tmp_path: Path) -> None:
    """The checker itself: relative, function-local and package `__init__` imports."""
    source = (
        "from . import repositories\n"
        "from ..services.ranking import RankingService\n"
        "def build():\n"
        "    import flamescope_agents.orchestrator\n"
    )
    path = tmp_path / "rank.py"
    found = imports_of(source, "flamescope_api.routers.rank", path)
    assert "flamescope_api.routers.repositories" in found
    assert "flamescope_api.services.ranking" in found
    assert "flamescope_agents.orchestrator" in found
    init = tmp_path / "__init__.py"
    assert "flamescope_api.services.x" in imports_of(
        "from .x import y\n", "flamescope_api.services", init
    )
