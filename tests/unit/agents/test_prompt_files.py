"""Runtime prompt files (document 07 section 2; document 12 section 1; NFR-07).

The files are parsed here independently of `base.load_prompt`, so the format itself is
checked against the document, not against the loader.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

from flamescope_agents.base import load_prompt
from flamescope_common.schemas import agents as agent_schemas

pytestmark = pytest.mark.unit

PROMPTS_DIR = (
    Path(__file__).resolve().parents[3] / "src" / "agents" / "flamescope_agents" / "prompts"
)
SHARED_FILES = ("shared/grounding_rules.md", "shared/domain_primer.md")
FRAMEWORK_VARIABLES = {"input_json", "validation_feedback"}
FRONT_MATTER_KEYS = {"name", "version", "output_schema", "temperature", "max_tokens"}
PROMPTS: dict[str, tuple[str, str, str]] = {
    "extractor": ("extractor@1", "ExtractorOutput", "ExtractorInput"),
    "scorer": ("scorer@1", "ScorerOutput", "ScorerInput"),
    "comparator": ("comparator@1", "ComparatorOutput", "ComparatorInput"),
    "scenario_interpreter": (
        "scenario_interpreter@1",
        "ScenarioInterpreterOutput",
        "ScenarioInterpreterInput",
    ),
    "insight_qa": ("insight_qa@2", "text", "InsightQAInput"),
    "earth_apps": ("earth_apps@1", "EarthAppsOutput", "EarthAppsInput"),
}
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
SECTION = re.compile(r"^## (System|User)[ \t]*$", re.MULTILINE)
VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
INCLUDE = re.compile(r"\{\{>\s*([\w./-]+)\s*\}\}")


def read_prompt(name: str) -> tuple[dict[str, Any], dict[str, str]]:
    match = FRONT_MATTER.match((PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"))
    assert match is not None, f"{name}.md has no front matter block"
    pieces = SECTION.split(match.group(2))
    sections = dict(zip(pieces[1::2], pieces[2::2], strict=True))
    return yaml.safe_load(match.group(1)), sections


def input_model(name: str) -> type[BaseModel]:
    model: type[BaseModel] = getattr(agent_schemas, PROMPTS[name][2])
    return model


@pytest.mark.parametrize("name", list(PROMPTS))
def test_prompt_file_exists(name: str) -> None:
    """NFR-07: one runtime prompt file per agent (document 07 section 2)."""
    assert (PROMPTS_DIR / f"{name}.md").is_file()


@pytest.mark.parametrize("path", SHARED_FILES)
def test_shared_files_exist(path: str) -> None:
    """NFR-07: the shared grounding rules and domain primer."""
    assert (PROMPTS_DIR / path).is_file()


@pytest.mark.parametrize("name", list(PROMPTS))
def test_front_matter_has_the_documented_keys(name: str) -> None:
    """NFR-07: `name`, `version`, `output_schema`, `temperature`, `max_tokens`."""
    meta, _sections = read_prompt(name)

    assert set(meta) >= FRONT_MATTER_KEYS
    assert f"{meta['name']}@{meta['version']}" == PROMPTS[name][0]


@pytest.mark.parametrize("name", list(PROMPTS))
def test_output_schema_names_a_model_in_schemas_agents(name: str) -> None:
    """NFR-07: `output_schema` names a model of `schemas/agents.py`, or `text` (Insight QA)."""
    meta, _sections = read_prompt(name)
    expected = PROMPTS[name][1]

    assert meta["output_schema"] == expected
    assert expected == "text" or issubclass(getattr(agent_schemas, expected), BaseModel)


@pytest.mark.parametrize("name", list(PROMPTS))
def test_has_exactly_one_system_and_one_user_section(name: str) -> None:
    """NFR-07: `## System` followed by `## User`."""
    _meta, sections = read_prompt(name)

    assert list(sections) == ["System", "User"]


@pytest.mark.parametrize("name", list(PROMPTS))
def test_uses_only_variables_the_agent_supplies(name: str) -> None:
    """NFR-07: input fields plus `{{input_json}}` and `{{validation_feedback}}`."""
    _meta, sections = read_prompt(name)
    used = {var for text in sections.values() for var in VARIABLE.findall(text)}

    assert used <= set(input_model(name).model_fields) | FRAMEWORK_VARIABLES


@pytest.mark.parametrize("name", list(PROMPTS))
def test_user_section_embeds_input_and_ends_with_validation_feedback(name: str) -> None:
    """NFR-07: every `## User` embeds `{{input_json}}` and ends with `{{validation_feedback}}`."""
    _meta, sections = read_prompt(name)
    user_variables = VARIABLE.findall(sections["User"])

    assert "input_json" in user_variables
    assert user_variables[-1:] == ["validation_feedback"]


@pytest.mark.parametrize("name", list(PROMPTS))
def test_includes_resolve_and_cover_both_shared_files(name: str) -> None:
    """NFR-07: `{{> shared/...}}` includes exist; both shared files are included by all."""
    _meta, sections = read_prompt(name)
    includes = {path for text in sections.values() for path in INCLUDE.findall(text)}

    assert set(SHARED_FILES) <= includes
    assert all((PROMPTS_DIR / path).is_file() for path in includes)


@pytest.mark.parametrize("name", list(PROMPTS))
def test_loaded_prompt_has_no_unresolved_include(name: str) -> None:
    """NFR-07: `base.Agent` renders the file with includes resolved."""
    prompt = load_prompt(name)

    assert INCLUDE.search(prompt.system) is None
    assert INCLUDE.search(prompt.user) is None
    assert prompt.version_key == PROMPTS[name][0]


def test_grounding_rules_state_the_normative_summary() -> None:
    """FR-15: null for unknowns, verbatim quotes under 240 characters, documents are data."""
    rules = (PROMPTS_DIR / "shared" / "grounding_rules.md").read_text(encoding="utf-8").lower()

    for phrase in ("null", "verbatim", "240", "ignore", "never invent", "safe"):
        assert phrase in rules


def test_domain_primer_covers_the_glossary() -> None:
    """NFR-07: glossary terms of document 07 section 2."""
    primer = (PROMPTS_DIR / "shared" / "domain_primer.md").read_text(encoding="utf-8")

    for term in ("buoyancy", "Opposed flow", "Cool flames", "CIR", "MSG", "MDCA", "ACME"):
        assert term in primer
