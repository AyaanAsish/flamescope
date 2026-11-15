"""FR-01, FR-15: seed files validate and every stated fact carries an allowed source.

Governing: document 06 section 5 (seed format, curation rule, acronym keys, interim psi_url),
document 04 sections 3 to 5 (SourceRef, card, vocabularies), document 12 section 1.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
import yaml
from pydantic import BaseModel
from pydantic import ValidationError as SchemaValidationError

from flamescope_common.errors import NotFoundError
from flamescope_common.rubric import Rubric
from flamescope_common.schemas.card import InvestigationCard, SeedInvestigation
from flamescope_common.sources import SourceRef, is_allowed_uri
from flamescope_ingest.seed import (
    list_seed_acronyms,
    load_earth_applications,
    load_fuel_taxonomy,
    load_hardware_catalog,
    load_s3_map,
    load_seed_mapping,
    select_acronyms,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_FILES = sorted((REPO_ROOT / "src" / "data" / "seed" / "investigations").glob("*.yaml"))
DOC_04 = REPO_ROOT / "docs" / "architecture" / "04-data-model.md"
BACKTICKED = re.compile(r"`([^`]+)`")
JSON_BLOCK = re.compile(r"```json\n(.*?)```", re.DOTALL)
PSI_HOST = "psi.nasa.gov"
NASA_DOMAIN = "nasa.gov"
DOI_HOSTS = frozenset({"doi.org", "dx.doi.org"})
S3_PSI_PREFIX = "s3://nasa-psi/"
CHALLENGE_PAGE = "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/"
PLACEHOLDER_TEXT = "..."
# Doc 06 section 3.6: the hardware catalog is seeded with these names.
SEEDED_HARDWARE = ("CIR", "MSG", "MDCA", "ACME insert", "SPICE flow duct")
# Doc 04 section 2, earth_application.sector.
EARTH_SECTORS = frozenset(
    {"firefighting", "detection", "building_safety", "industrial", "wildfire", "transport"}
)
# Doc 04 section 4 example ranges that would be copies; pressure is left out because
# 101.3 kPa is one standard atmosphere, a value real sources legitimately state.
ILLUSTRATIVE_RANGE_DIMENSIONS = ("o2_fraction", "flow_speed_cm_s")


def _seed_id(path: Path) -> str:
    return path.stem


def _raw(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} must hold a mapping"
    return loaded


def _doc_04_tag_vocabulary() -> set[str]:
    line = next(
        row
        for row in DOC_04.read_text(encoding="utf-8").splitlines()
        if row.startswith("- **fire_safety_tags**")
    )
    return set(BACKTICKED.findall(line))


def _doc_04_example_card() -> dict[str, Any]:
    text = DOC_04.read_text(encoding="utf-8")
    section = text[text.index("## 4. InvestigationCard") :]
    match = JSON_BLOCK.search(section)
    assert match is not None, "document 04 section 4 must hold the example card"
    example: dict[str, Any] = json.loads(match.group(1))
    return example


def _source_refs(node: Any) -> Iterator[SourceRef]:
    """Every SourceRef inside a validated model tree."""
    if isinstance(node, SourceRef):
        yield node
    elif isinstance(node, BaseModel):
        for name in type(node).model_fields:
            yield from _source_refs(getattr(node, name))
    elif isinstance(node, dict):
        for child in node.values():
            yield from _source_refs(child)
    elif isinstance(node, list):
        for child in node:
            yield from _source_refs(child)


def _strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for child in node.values():
            yield from _strings(child)
    elif isinstance(node, list):
        for child in node:
            yield from _strings(child)


def _is_psi_or_doi(uri: str) -> bool:
    parsed = urlparse(uri)
    return parsed.scheme == "https" and (parsed.netloc == PSI_HOST or parsed.netloc in DOI_HOSTS)


def _is_nasa_page(uri: str) -> bool:
    """NASA web pages and NTRS records (doc 04 section 3), for example ntrs.nasa.gov."""
    parsed = urlparse(uri)
    host = parsed.netloc
    return parsed.scheme == "https" and (host == NASA_DOMAIN or host.endswith(f".{NASA_DOMAIN}"))


def _curation_allows(source: SourceRef) -> bool:
    """Doc 06 section 5 and doc 04 section 3: the narrower curation rule for seed authors."""
    if source.kind == "curated":
        return _is_psi_or_doi(source.uri) or source.uri == CHALLENGE_PAGE
    return (
        _is_psi_or_doi(source.uri)
        or source.uri.startswith(S3_PSI_PREFIX)
        or _is_nasa_page(source.uri)
    )


@pytest.fixture(scope="module")
def tag_vocabulary() -> set[str]:
    return _doc_04_tag_vocabulary()


@pytest.fixture(scope="module")
def rubric() -> Rubric:
    return Rubric.load(REPO_ROOT / "src" / "data" / "rubric.yaml")


def test_seed_directory_holds_investigations() -> None:
    """FR-01: the offline dataset exists (document 06 section 1, ADR-04)."""
    assert SEED_FILES, "src/data/seed/investigations/ must contain seed files"


def test_tag_vocabulary_parsed_from_document_04(tag_vocabulary: set[str]) -> None:
    """Document 04 section 5 lists twenty controlled fire-safety tags."""
    assert len(tag_vocabulary) == 20
    assert {"flame_spread", "partial_gravity_analogue", "post_fire"} <= tag_vocabulary


@pytest.mark.parametrize("path", SEED_FILES, ids=_seed_id)
class TestEverySeedFile:
    def test_validates_as_seed_investigation(self, path: Path) -> None:
        """FR-01: each file validates as `SeedInvestigation` (document 06 section 5)."""
        record = SeedInvestigation.model_validate(_raw(path))
        assert record.acronym == path.stem

    def test_also_validates_as_bare_card(self, path: Path) -> None:
        """`InvestigationCard` ignores the seed-only keys (document 06 section 5)."""
        card = InvestigationCard.model_validate(_raw(path))
        assert card.acronym == path.stem

    def test_acronym_key_has_no_spaces(self, path: Path) -> None:
        """The acronym is the URL key and the file name (document 06 section 5)."""
        assert " " not in _raw(path)["acronym"]

    def test_psi_url_is_present_and_a_psi_page(self, path: Path) -> None:
        """`psi_url` is required; interim value is the PSI search page (document 06 s5)."""
        psi_url = _raw(path)["psi_url"]
        assert is_allowed_uri(psi_url)
        assert urlparse(psi_url).netloc == PSI_HOST

    def test_every_source_has_an_allowed_uri(self, path: Path) -> None:
        """FR-15: every SourceRef passes `is_allowed_uri` and the curation rule (doc 06 s5)."""
        record = SeedInvestigation.model_validate(_raw(path))
        for source in _source_refs(record):
            assert is_allowed_uri(source.uri), source.uri
            assert _curation_allows(source), f"{source.kind} source {source.uri}"

    def test_every_fact_carries_a_source(self, path: Path) -> None:
        """No scientific fact without a source (document 04 section 4; doc 13 s3 rule 6)."""
        record = SeedInvestigation.model_validate(_raw(path))
        sourced: list[Any] = [
            *record.objectives,
            *record.fuels,
            *record.measurements,
            *record.findings,
            *record.runs,
        ]
        if record.approach is not None:
            sourced.append(record.approach)
        assert all(isinstance(item.source, SourceRef) for item in sourced)
        if record.conditions is not None:
            for name in ("o2_fraction", "pressure_kpa", "flow_speed_cm_s"):
                stated = getattr(record.conditions, name)
                if stated is not None and (stated.min is not None or stated.max is not None):
                    assert stated.source is not None, name

    def test_tags_are_in_the_vocabulary(self, path: Path, tag_vocabulary: set[str]) -> None:
        """Tags restricted to the controlled vocabulary of document 04 section 5."""
        tags = _raw(path).get("fire_safety_tags") or []
        assert set(tags) <= tag_vocabulary, set(tags) - tag_vocabulary

    def test_scores_use_rubric_lenses_and_criteria(self, path: Path, rubric: Rubric) -> None:
        """Seed `scores:` blocks reference only rubric criteria (document 08 section 1)."""
        record = SeedInvestigation.model_validate(_raw(path))
        for lens, criteria in record.scores.items():
            assert set(criteria) <= set(rubric.criterion_ids(lens)), lens
            for score in criteria.values():
                assert score.value is None or score.evidence, "rated value needs evidence"

    def test_hardware_names_resolve_in_hardware_yaml(self, path: Path) -> None:
        """Linking reads hardware from `hardware.yaml` (document 06 section 3.6)."""
        known = load_hardware_catalog(REPO_ROOT / "src" / "data").hardware_names()
        names = {item["name"] for item in _raw(path).get("hardware") or []}
        assert names <= known, names - known

    def test_no_value_copied_from_document_04_example(self, path: Path) -> None:
        """Document 04 section 4: example numbers illustrate shape only."""
        raw = _raw(path)
        example = _doc_04_example_card()
        _assert_no_example_ranges(raw, example)
        _assert_no_example_fuel_geometry(raw, example)
        _assert_no_example_publications(raw, example)
        assert raw.get("field_confidence") != example["field_confidence"]
        placeholders = {PLACEHOLDER_TEXT, *example["open_questions"]}
        assert not placeholders & set(_strings(raw))


def _assert_no_example_ranges(raw: dict[str, Any], example: dict[str, Any]) -> None:
    conditions = raw.get("conditions") or {}
    for dimension in ILLUSTRATIVE_RANGE_DIMENSIONS:
        stated = conditions.get(dimension) or {}
        sample = example["conditions"][dimension]
        assert (stated.get("min"), stated.get("max")) != (sample["min"], sample["max"])


def _assert_no_example_fuel_geometry(raw: dict[str, Any], example: dict[str, Any]) -> None:
    sample = example["fuels"][0]["geometry"]["dimensions_mm"]
    for fuel in raw.get("fuels") or []:
        assert ((fuel.get("geometry") or {}).get("dimensions_mm")) != sample


def _assert_no_example_publications(raw: dict[str, Any], example: dict[str, Any]) -> None:
    sample_doi = example["publications"][0]["doi"]
    for publication in raw.get("publications") or []:
        doi = publication.get("doi") or ""
        assert doi != sample_doi
        assert "xxxx" not in doi


def test_e_field_flames_key_and_title() -> None:
    """Document 06 section 5: key `E-FIELD-Flames`, title `E-FIELD Flames`."""
    raw = _raw(REPO_ROOT / "src" / "data" / "seed" / "investigations" / "E-FIELD-Flames.yaml")
    assert raw["acronym"] == "E-FIELD-Flames"
    assert raw["title"] == "E-FIELD Flames"


def test_seed_requires_psi_url(make_card: Callable[..., dict[str, Any]]) -> None:
    """`psi_url` is required in a seed file (document 06 section 5)."""
    card = make_card()
    del card["psi_url"]
    with pytest.raises(SchemaValidationError):
        SeedInvestigation.model_validate(card)


def test_seed_rejects_unknown_tag(make_card: Callable[..., dict[str, Any]]) -> None:
    """Tags outside the vocabulary of document 04 section 5 are not valid card values."""
    with pytest.raises(SchemaValidationError):
        SeedInvestigation.model_validate(make_card(fire_safety_tags=["not_a_tag"]))


def test_seed_rejects_disallowed_source_uri(make_card: Callable[..., dict[str, Any]]) -> None:
    """FR-15: an http or foreign-bucket URI is not an allowed source (document 04 s3)."""
    bad = {"kind": "document", "uri": "s3://other-bucket/file.pdf"}
    with pytest.raises(SchemaValidationError):
        SeedInvestigation.model_validate(make_card(objectives=[{"text": "x", "source": bad}]))


def test_list_seed_acronyms_equals_file_stems(repo_data_dir: Path) -> None:
    assert list_seed_acronyms(repo_data_dir) == sorted(path.stem for path in SEED_FILES)


def test_load_seed_mapping_reads_one_file(repo_data_dir: Path) -> None:
    first = SEED_FILES[0].stem
    assert load_seed_mapping(repo_data_dir, first)["acronym"] == first


def test_load_seed_mapping_missing_file_is_not_found(repo_data_dir: Path) -> None:
    with pytest.raises(NotFoundError):
        load_seed_mapping(repo_data_dir, "NO-SUCH-INVESTIGATION")


def test_select_acronyms_only_filter_is_case_insensitive() -> None:
    """`--only ACR` (document 06 section 4)."""
    assert select_acronyms(["BASS", "FLEX"], ["flex"]) == ["FLEX"]
    assert select_acronyms(["BASS", "FLEX"], None) == ["BASS", "FLEX"]


def test_select_acronyms_unknown_is_an_error() -> None:
    with pytest.raises(NotFoundError):
        select_acronyms(["BASS"], ["NOPE"])


def test_hardware_yaml_seeds_documented_hardware(repo_data_dir: Path) -> None:
    """Document 06 section 3.6: CIR, MSG, MDCA, ACME insert, SPICE flow duct."""
    names = load_hardware_catalog(repo_data_dir).hardware_names()
    assert set(SEEDED_HARDWARE) <= names


def test_fuel_taxonomy_loads(repo_data_dir: Path) -> None:
    """`fuel_taxonomy.yaml` maps names to phase and class (document 06 section 3.5)."""
    taxonomy = load_fuel_taxonomy(repo_data_dir)
    for entry in taxonomy.fuels:
        assert taxonomy.resolve(entry.name) == entry
        for alias in entry.aliases:
            assert taxonomy.resolve(alias.upper()) == entry


def test_earth_applications_yaml_validates(repo_data_dir: Path) -> None:
    """FR-10: curated applications use the sectors of document 04 and allowed sources."""
    catalog = load_earth_applications(repo_data_dir)
    for application in catalog.applications:
        assert application.sector in EARTH_SECTORS
        assert all(_curation_allows(reference) for reference in application.references)


def test_s3_map_has_documented_format(repo_data_dir: Path) -> None:
    """`s3_map.yaml` format `mappings: [{prefix, acronym}]` (document 06 section 3.1)."""
    raw = yaml.safe_load((repo_data_dir / "seed" / "s3_map.yaml").read_text(encoding="utf-8"))
    assert isinstance(raw["mappings"], list)
    assert len(load_s3_map(repo_data_dir).mappings) == len(raw["mappings"])
