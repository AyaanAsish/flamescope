"""NFR-08, FR-13: the build equals the documents (document 13 section 4 checklist).

Every expected value is parsed from `docs/architecture/`: the endpoint inventory (doc 05 s11),
the repository layout (doc 02 s4), runtime prompt files (doc 07 s2), component IDs (doc 03),
call flows (doc 09), Architecture page content (doc 10 s6) and Makefile targets (doc 11 s4).
Files produced by later build prompts carry a non-strict xfail on exactly those assertions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from flamescope_api.main import create_app

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS = REPO_ROOT / "docs" / "architecture"
UI_CONTENT = REPO_ROOT / "src" / "ui" / "content" / "architecture"
PROMPTS_DIR = REPO_ROOT / "src" / "agents" / "flamescope_agents" / "prompts"
API_PREFIX = "/api/v1"
INVENTORY_SIZE = 24
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
ENDPOINT = re.compile(r"`(GET|POST|PUT|PATCH|DELETE) (/[^`]*)`")
BACKTICKED = re.compile(r"`([^`]+)`")
COMPONENT_ID = re.compile(r"\bC-[A-Z]+\b")
CF_HEADING = re.compile(r"^## (CF-(\d\d)) ", re.MULTILINE)
MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
CODE_BLOCK = re.compile(r"```\n(.*?)```", re.DOTALL)
DEPLOY_FILE = re.compile(r"Dockerfile\.\w+|compose\.yaml")
TREE_INDENT = 2
EXECUTABLE_SUFFIXES = frozenset({".py", ".sh", ".ts", ".tsx", ".js", ".mjs"})
EXECUTABLE_ROOTS = frozenset({"src", "tests", "deploy"})
TAB_CONTENT_FILES = (
    "context.json",
    "layers.json",
    "components.json",
    "dataflow.json",
    "datamodel.json",
    "deployment.json",
)
# Paths of document 02 section 4 that later build prompts create (prompts/00-README.md).
LATER_PROMPT_PATHS = {
    "README.md": "10",
}
# Document 02 section 4: the generated decks' build and verification scripts are the one
# executable exception outside `src/`, `tests/` and `deploy/`.
DECK_SCRIPTS_DIR = "docs/decks"
DECK_SCRIPT_SUFFIX = ".py"


def _section(document: str, start: str, end: str | None = None) -> str:
    text = (DOCS / document).read_text(encoding="utf-8")
    begin = text.index(start)
    return text[begin : text.index(end, begin) if end else len(text)]


def _later_prompt(relative: str) -> str | None:
    for prefix, prompt in LATER_PROMPT_PATHS.items():
        if relative == prefix or relative.startswith(prefix + "/"):
            return prompt
    return None


def _maybe_xfail(relative: str) -> Any:
    prompt = _later_prompt(relative)
    if prompt is None:
        return pytest.param(relative, id=relative)
    mark = pytest.mark.xfail(strict=False, reason=f"created by prompt {prompt}")
    return pytest.param(relative, id=relative, marks=mark)


# --- document 05 section 11: endpoint inventory -------------------------------------------


def documented_endpoints() -> set[tuple[str, str]]:
    inventory = _section("05-api-specification.md", "## 11. Endpoint inventory")
    return {(method, path) for method, path in ENDPOINT.findall(inventory)}


def registered_endpoints() -> set[tuple[str, str]]:
    """Walk the OpenAPI document: FastAPI wraps included routers, so `app.routes` is not flat."""
    paths: dict[str, dict[str, Any]] = create_app().openapi()["paths"]
    return {
        (method.upper(), path.removeprefix(API_PREFIX))
        for path, operations in paths.items()
        for method in operations
        if method in HTTP_METHODS
    }


def test_inventory_lists_24_endpoints() -> None:
    assert len(documented_endpoints()) == INVENTORY_SIZE


def test_registered_routes_equal_inventory() -> None:
    """Document 05 section 11: the 24 endpoints exist, nothing extra, names as documented."""
    registered = registered_endpoints()
    documented = documented_endpoints()
    assert {"missing": documented - registered, "extra": registered - documented} == {
        "missing": set(),
        "extra": set(),
    }


def test_every_route_is_under_api_v1() -> None:
    paths = create_app().openapi()["paths"]
    assert all(path.startswith(API_PREFIX + "/") for path in paths)


def test_openapi_and_docs_urls() -> None:
    """Document 05: OpenAPI at `/api/v1/openapi.json`, Swagger UI at `/api/v1/docs`."""
    app = create_app()
    assert app.openapi_url == f"{API_PREFIX}/openapi.json"
    assert app.docs_url == f"{API_PREFIX}/docs"


# --- document 02 section 4: repository layout ---------------------------------------------


def _tree_lines() -> list[str]:
    block = CODE_BLOCK.search(_section("02-system-architecture.md", "## 4. Repository layout"))
    assert block is not None
    return block.group(1).splitlines()[1:]


def documented_layout() -> list[tuple[str, bool]]:
    """(relative path, is directory) per tree entry; deploy files come from a line comment."""
    entries: list[tuple[str, bool]] = []
    stack: list[str] = []
    for line in _tree_lines():
        content, _, comment = line.partition("#")
        names = content.split()
        if not names:
            continue
        depth = (len(content) - len(content.lstrip())) // TREE_INDENT - 1
        parents = stack[:depth]
        entries += [("/".join([*parents, n.rstrip("/")]), n.endswith("/")) for n in names]
        if len(names) == 1 and names[0].endswith("/"):
            stack = [*parents, names[0].rstrip("/")]
            entries += [("/".join([*stack, f]), False) for f in DEPLOY_FILE.findall(comment)]
    return entries


LAYOUT = documented_layout()


def test_layout_tree_is_parsed() -> None:
    paths = {path for path, _ in LAYOUT}
    assert {"src/common/flamescope_common", "tests/unit", "deploy/helm/flamescope"} <= paths
    assert "deploy/docker/compose.yaml" in paths


@pytest.mark.parametrize("relative", [_maybe_xfail(p) for p, is_dir in LAYOUT if is_dir])
def test_layout_directory_exists(relative: str) -> None:
    """Document 02 section 4 (binding layout)."""
    assert (REPO_ROOT / relative).is_dir()


@pytest.mark.parametrize("relative", [_maybe_xfail(p) for p, is_dir in LAYOUT if not is_dir])
def test_layout_file_exists(relative: str) -> None:
    assert (REPO_ROOT / relative).is_file()


def _visible_files(directory: Path) -> Iterator[Path]:
    for child in directory.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_dir():
            yield from _visible_files(child)
        else:
            yield child


def _is_deck_script(relative: Path) -> bool:
    return relative.parent.as_posix() == DECK_SCRIPTS_DIR and relative.suffix == DECK_SCRIPT_SUFFIX


def test_nothing_executable_outside_src_tests_deploy() -> None:
    """Document 02 section 4: nothing executable outside `src/`, `tests/` and `deploy/`,
    except the deck build scripts directly in `docs/decks/`."""
    relative_paths = (path.relative_to(REPO_ROOT) for path in _visible_files(REPO_ROOT))
    outside = [
        relative.as_posix()
        for relative in relative_paths
        if relative.suffix in EXECUTABLE_SUFFIXES
        and relative.parts[0] not in EXECUTABLE_ROOTS
        and not _is_deck_script(relative)
    ]
    assert outside == []


# --- document 07 section 2: runtime prompt files ------------------------------------------


def documented_prompt_files() -> set[str]:
    table = _section("07-agents-and-llm.md", "## 2. Runtime prompt files", "## 3.")
    return {name for name in BACKTICKED.findall(table) if name.endswith(".md")}


def test_prompt_table_lists_eight_files() -> None:
    assert len(documented_prompt_files()) == 8


@pytest.mark.parametrize("name", sorted(documented_prompt_files()))
def test_runtime_prompt_file_exists(name: str) -> None:
    assert (PROMPTS_DIR / name).is_file()


def test_no_undocumented_prompt_files() -> None:
    present = {path.relative_to(PROMPTS_DIR).as_posix() for path in PROMPTS_DIR.rglob("*.md")}
    assert present == documented_prompt_files()


# --- document 03 component IDs and document 10 section 6 content --------------------------


def documented_component_ids() -> set[str]:
    return set(COMPONENT_ID.findall((DOCS / "03-component-design.md").read_text("utf-8")))


def _content(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((UI_CONTENT / name).read_text(encoding="utf-8"))
    return loaded


def _component_ids_in(diagram: dict[str, Any]) -> list[str]:
    return [
        node["data"]["componentId"]
        for node in diagram.get("nodes", [])
        if node.get("data", {}).get("componentId")
    ]


def test_component_ids_parsed_from_document_03() -> None:
    assert documented_component_ids() == {
        "C-UI",
        "C-API",
        "C-SVC",
        "C-REPO",
        "C-ORCH",
        "C-AGT",
        "C-CV",
        "C-LLM",
        "C-COM",
        "C-DB",
        "C-ING",
        "C-RAW",
    }


@pytest.mark.parametrize("name", TAB_CONTENT_FILES)
def test_content_component_ids_exist_in_document_03(name: str) -> None:
    """ADR-10, document 10 section 6.5: every `componentId` exists in document 03."""
    unknown = set(_component_ids_in(_content(name))) - documented_component_ids()
    assert unknown == set()


def test_components_tab_has_one_node_per_component() -> None:
    """Document 10 section 6.2: one node per document 03 component; node id = componentId."""
    nodes = [
        n for n in _content("components.json")["nodes"] if n.get("data", {}).get("componentId")
    ]
    assert sorted(n["data"]["componentId"] for n in nodes) == sorted(documented_component_ids())
    assert all(node["id"] == node["data"]["componentId"] for node in nodes)


# --- document 09: call-flow files ---------------------------------------------------------


def documented_flows() -> dict[str, str]:
    """`cf-NN.mmd` name to the Mermaid block of that CF section of document 09."""
    text = (DOCS / "09-call-flows.md").read_text(encoding="utf-8")
    headings = list(CF_HEADING.finditer(text))
    flows: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = MERMAID_BLOCK.search(text, heading.end(), end)
        assert block is not None, f"{heading.group(1)} has no Mermaid block"
        flows[f"cf-{heading.group(2)}.mmd"] = block.group(1)
    return flows


def test_document_09_has_thirteen_flows() -> None:
    assert sorted(documented_flows()) == [f"cf-{number:02d}.mmd" for number in range(1, 14)]


@pytest.mark.parametrize("name", sorted(documented_flows()))
def test_flow_file_is_verbatim_copy(name: str) -> None:
    """Document 10 section 6.5: each `.mmd` is a verbatim copy of its document 09 block."""
    path = UI_CONTENT / "flows" / name
    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip() == documented_flows()[name].strip()


def test_no_undocumented_flow_files() -> None:
    present = {path.name for path in (UI_CONTENT / "flows").glob("*.mmd")}
    assert present == set(documented_flows())


# --- document 11 section 4: Makefile targets ----------------------------------------------


def documented_make_targets() -> list[str]:
    table = _section("11-deployment-and-operations.md", "## 4. Makefile targets", "## 5.")
    targets: list[str] = []
    for row in table.splitlines():
        cells = row.split("|")
        if len(cells) > TREE_INDENT and cells[1].strip().startswith("`"):
            targets += BACKTICKED.findall(cells[1])
    return targets


def test_make_target_table_is_parsed() -> None:
    targets = documented_make_targets()
    assert {"help", "deploy", "undeploy", "test-unit", "helm-undeploy"} <= set(targets)
    assert len(targets) == len(set(targets))


@pytest.mark.parametrize("target", documented_make_targets())
def test_makefile_declares_target(target: str) -> None:
    """Document 11 section 4: binding target names, each declared and `.PHONY`."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.search(rf"^{re.escape(target)}:", makefile, re.MULTILINE)
    phony = " ".join(re.findall(r"^\.PHONY:(.*)$", makefile, re.MULTILINE)).split()
    assert target in phony
