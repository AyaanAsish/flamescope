"""Catalog endpoints (document 12 section 2; document 05 sections 1, 2 and 4).

Requirements: FR-01 (cards: list and detail), FR-02 (search and filter, facets), FR-06 (runs,
varied and fixed variables), FR-12 (hardware lineage, projects). Call flows: CF-04
(Explorer list and detail), CF-06 (lineage graph for Compare).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(11)]

Rows = Callable[..., list[dict[str, Any]]]
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100
SMALL_PAGE = 5
FUEL_PHASES = ("gas", "liquid", "solid")
SCORE_SORTS = ("overall", "habitat", "modeling", "controls")
CONDITION_DIMENSIONS = ("o2_fraction", "pressure_kpa", "flow_speed_cm_s", "gravity_g")
SUMMARY_FIELDS = {
    "id", "acronym", "title", "project", "platform", "gravity_level", "fuel_phases", "hardware",
    "summary", "fire_safety_tags", "o2_range", "pressure_range_kpa", "flow_range_cm_s",
    "scores", "reviewed", "psi_url",
}  # fmt: skip
DETAIL_FIELDS = SUMMARY_FIELDS | {
    "card", "publications", "measurements", "findings", "score_breakdown", "run_count", "data",
}  # fmt: skip
RUN_FIELDS = {
    "id", "label", "fuel", "geometry", "condition", "outcome", "is_aggregate", "source",
    "confidence",
}  # fmt: skip
PUBLICATION_FIELDS = {"doi", "title", "authors", "year", "venue", "url", "key_findings"}
FACETS = ("fuel_phase", "hardware", "project", "tag", "platform", "gravity_level")
# Document 01 section 6 hardware relationships, checked for the investigations that are seeded.
DOCUMENTED_HARDWARE_USERS = {
    "MDCA": ("FLEX", "FLEX-2", "CFI"),
    "SPICE flow duct": ("BASS", "BASS-II", "SPICE", "SLICE"),
    "CIR": ("BRE", "CFI-G", "E-FIELD-Flames", "FLEX", "FLEX-2", "CFI"),
    "MSG": ("BASS", "BASS-II", "SPICE", "SLICE"),
}
SHARED_INSTRUMENT_USERS = ("SAME", "SAME-R", "DAFT", "DAFT-2")
# Doc 05 s4: overlap with the derived range; a null end is open when the other end is known.
RANGE_FILTERS = {
    "o2_min": "(o2_max >= :value OR (o2_max IS NULL AND o2_min IS NOT NULL))",
    "o2_max": "(o2_min <= :value OR (o2_min IS NULL AND o2_max IS NOT NULL))",
    "pressure_min_kpa": (
        "(pressure_max_kpa >= :value "
        "OR (pressure_max_kpa IS NULL AND pressure_min_kpa IS NOT NULL))"
    ),
    "pressure_max_kpa": (
        "(pressure_min_kpa <= :value "
        "OR (pressure_min_kpa IS NULL AND pressure_max_kpa IS NOT NULL))"
    ),
}
HALF_OPEN_ACRONYM = "CFI-G"  # seed states o2_fraction {min: null, max: 0.85}
RANGE_FILTER_VALUES = {
    "o2_min": 0.3,
    "o2_max": 0.5,
    "pressure_min_kpa": 50,
    "pressure_max_kpa": 70.3,
}


@pytest.fixture(scope="module")
def first_acronym(seed_acronyms: list[str]) -> str:
    return sorted(seed_acronyms)[0]


@pytest.fixture(scope="module")
def hardware_names(stack: str, sql: Rows) -> list[str]:
    return [row["name"] for row in sql("SELECT name FROM hardware ORDER BY name")]


# --- list, pagination, search, filters, sort ----------------------------------------------


def test_fr01_list_default_pagination(
    stack: str, api: httpx.Client, seed_acronyms: list[str]
) -> None:
    """FR-01, doc 05 s1: page 1, page_size 24 by default, `total` counts every match."""
    body = api.get("/investigations").json()
    assert (body["page"], body["page_size"], body["total"]) == (
        1,
        DEFAULT_PAGE_SIZE,
        len(seed_acronyms),
    )
    assert len(body["items"]) == min(DEFAULT_PAGE_SIZE, len(seed_acronyms))


def test_fr01_pages_partition_the_catalog(
    stack: str, api: httpx.Client, seed_acronyms: list[str]
) -> None:
    """FR-01: consecutive small pages cover every investigation exactly once."""
    pages = []
    for page in range(1, len(seed_acronyms) // SMALL_PAGE + 2):
        body = api.get("/investigations", params={"page": page, "page_size": SMALL_PAGE}).json()
        assert len(body["items"]) <= SMALL_PAGE
        pages += [item["acronym"] for item in body["items"]]
    assert sorted(pages) == sorted(seed_acronyms)


@pytest.mark.parametrize(
    ("params", "status"),
    [({"page_size": MAX_PAGE_SIZE}, 200), ({"page_size": 1}, 200),
     ({"page_size": MAX_PAGE_SIZE + 1}, 422), ({"page_size": 0}, 422), ({"page": 0}, 422)],
)  # fmt: skip
def test_fr01_page_size_bounds(
    params: dict[str, int],
    status: int,
    stack: str,
    api: httpx.Client,
    assert_error_envelope: Callable[..., dict[str, Any]],
) -> None:
    """FR-01, doc 05 s1: `page_size` 1..100; violations are the 422 envelope."""
    response = api.get("/investigations", params=params)
    if status == httpx.codes.OK:
        assert response.status_code == status
        return
    assert_error_envelope(response, status, "validation_error")


def test_fr01_summary_shape(stack: str, api: httpx.Client) -> None:
    """FR-01, doc 05 s4: `InvestigationSummary` fields and score keys."""
    items = api.get("/investigations").json()["items"]
    assert {frozenset(item) for item in items} == {frozenset(SUMMARY_FIELDS)}
    assert {frozenset(item["scores"]) for item in items} == {frozenset({*SCORE_SORTS})}


# Facet-like filters of document 05 section 4: the values to try and the matching SQL condition.
VALUE_FILTERS = {
    "fuel_phase": (
        "SELECT unnest(ARRAY['gas', 'liquid', 'solid']) AS value",
        ":value = ANY(fuel_phases)",
    ),
    "hardware": (
        "SELECT name AS value FROM hardware",
        "EXISTS (SELECT 1 FROM investigation_hardware ih JOIN hardware h ON h.id = ih.hardware_id "
        "WHERE ih.investigation_id = i.id AND h.name = :value)",
    ),
    "project": (
        "SELECT name AS value FROM project",
        "project_id = (SELECT id FROM project WHERE name = :value)",
    ),
    "tag": (
        "SELECT DISTINCT unnest(fire_safety_tags) AS value FROM investigation",
        ":value = ANY(fire_safety_tags)",
    ),
    "gravity_level": (
        "SELECT unnest(ARRAY['microgravity', 'normal', 'partial', 'mixed']) AS value",
        "gravity_level = :value",
    ),
}
MATERIAL_CONDITION = (
    "EXISTS (SELECT 1 FROM test_run t JOIN fuel f ON f.id = t.fuel_id "
    "WHERE t.investigation_id = i.id AND f.name ILIKE :value)"
)
DOC_04_EXAMPLE_FUEL = "PMMA"


@pytest.mark.parametrize("name", sorted(VALUE_FILTERS))
def test_fr02_value_filter(
    name: str, sql: Rows, listed: Callable[..., list[str]], queried: Callable[..., list[str]]
) -> None:
    """FR-02: `fuel_phase`, `hardware`, `project`, `tag`, `gravity_level` equal the database."""
    values_query, condition = VALUE_FILTERS[name]
    values = sorted(row["value"] for row in sql(values_query))
    actual = {value: listed({name: value}) for value in values}
    assert actual == {value: queried(condition, value=value) for value in values}


def test_fr02_material_filter(
    seed_records: dict[str, dict[str, Any]],
    listed: Callable[..., list[str]],
    queried: Callable[..., list[str]],
) -> None:
    """FR-02: `material` equals the investigations with a run burning that fuel."""
    fuels = [record.get("fuels") or [] for record in seed_records.values()]
    seeded = {fuel["name"] for items in fuels for fuel in items}
    materials = sorted(seeded) or [DOC_04_EXAMPLE_FUEL]
    actual = {name: listed({"material": name}) for name in materials}
    assert actual == {name: queried(MATERIAL_CONDITION, value=f"%{name}%") for name in materials}


@pytest.mark.parametrize("name", sorted(RANGE_FILTERS))
def test_fr02_range_filter(
    name: str, listed: Callable[..., list[str]], queried: Callable[..., list[str]]
) -> None:
    """FR-02: oxygen and pressure range filters keep overlapping stated ranges."""
    value = RANGE_FILTER_VALUES[name]
    assert listed({name: value}) == queried(RANGE_FILTERS[name], value=value)


def test_fr02_half_open_range_is_open_not_a_point(
    stack: str,
    api: httpx.Client,
    seed_records: dict[str, dict[str, Any]],
    listed: Callable[..., list[str]],
) -> None:
    """FR-02, docs 04 s2 and 05 s4: a stated `[null, max]` stays open on the low side."""
    record = seed_records.get(HALF_OPEN_ACRONYM)
    if record is None:
        pytest.skip(f"precondition absent: {HALF_OPEN_ACRONYM} is not in the seed set")
    stated = record["conditions"]["o2_fraction"]
    below_max = stated["max"] / 2
    item = api.get(f"/investigations/{HALF_OPEN_ACRONYM}").json()
    observed = (item["o2_range"], HALF_OPEN_ACRONYM in listed({"o2_max": below_max}))
    assert observed == ([None, stated["max"]], True)


def test_fr02_combined_filters(sql: Rows, listed: Callable[..., list[str]]) -> None:
    """FR-02: filters combine with AND (most common hardware and project)."""
    hardware = sql(
        "SELECT h.name FROM hardware h JOIN investigation_hardware ih ON ih.hardware_id = h.id "
        "GROUP BY h.name ORDER BY count(*) DESC, h.name LIMIT 1"
    )[0]["name"]
    project = sql("SELECT name FROM project ORDER BY name LIMIT 1")[0]["name"]
    params = {"hardware": hardware, "project": project}
    expected = sorted(set(listed({"hardware": hardware})) & set(listed({"project": project})))
    assert listed(params) == expected


def test_fr02_text_search(
    seed_records: dict[str, dict[str, Any]],
    listed: Callable[..., list[str]],
    queried: Callable[..., list[str]],
) -> None:
    """FR-02: `q` matches title, summary and objectives (full text) or acronym and title."""
    record = next(iter(seed_records.values()))
    word = max(re.findall(r"[A-Za-z]{5,}", record["summary"]), key=len)
    where = (
        "search_tsv @@ websearch_to_tsquery('english', :q) OR acronym ILIKE :pattern "
        "OR title ILIKE :pattern"
    )
    found = listed({"q": word})
    assert found == queried(where, q=word, pattern=f"%{word}%")
    assert record["acronym"] in found


def test_fr02_text_search_finds_acronym_case_insensitively(
    first_acronym: str, listed: Callable[..., list[str]]
) -> None:
    """FR-02: searching a lower-case acronym finds that investigation."""
    assert first_acronym in listed({"q": first_acronym.lower()})


def test_fr02_sort_by_acronym(stack: str, api: httpx.Client) -> None:
    """FR-02, doc 05 s4: default sort is `acronym` ascending."""
    for params in ({}, {"sort": "acronym"}):
        items = api.get("/investigations", params={**params, "page_size": MAX_PAGE_SIZE}).json()[
            "items"
        ]
        acronyms = [item["acronym"] for item in items]
        assert acronyms == sorted(acronyms)


@pytest.mark.parametrize("sort", SCORE_SORTS)
def test_fr02_sort_by_score(sort: str, stack: str, api: httpx.Client) -> None:
    """FR-02: score sorts are descending with null scores last."""
    items = api.get("/investigations", params={"sort": sort, "page_size": MAX_PAGE_SIZE}).json()[
        "items"
    ]
    scores = [item["scores"][sort] for item in items]
    known = [score for score in scores if score is not None]
    assert scores == known + [None] * (len(scores) - len(known))
    assert known == sorted(known, reverse=True)


# --- detail ---------------------------------------------------------------------------------


def test_fr01_detail_by_acronym_lower_case_and_id(
    stack: str, api: httpx.Client, first_acronym: str
) -> None:
    """FR-01, doc 05 s1: acronym, case-insensitive acronym and numeric ID give the same card."""
    by_acronym = api.get(f"/investigations/{first_acronym}").json()
    by_lower = api.get(f"/investigations/{first_acronym.lower()}").json()
    by_id = api.get(f"/investigations/{by_acronym['id']}").json()
    assert set(by_acronym) == DETAIL_FIELDS
    assert by_acronym == by_lower == by_id
    assert set(by_acronym["data"]) == {"s3_prefix", "volume_bytes", "file_types"}
    assert by_acronym["card"]["acronym"] == first_acronym


def test_fr01_detail_matches_summary(
    stack: str, api: httpx.Client, seed_acronyms: list[str]
) -> None:
    """FR-01: the detail repeats the summary fields of the list."""
    summaries = {
        item["acronym"]: item
        for item in api.get("/investigations", params={"page_size": MAX_PAGE_SIZE}).json()["items"]
    }
    mismatched = [
        acronym
        for acronym in seed_acronyms
        if {key: api.get(f"/investigations/{acronym}").json()[key] for key in SUMMARY_FIELDS}
        != summaries[acronym]
    ]
    assert mismatched == []


def test_fr01_unknown_investigation_is_404_envelope(
    stack: str, api: httpx.Client, assert_error_envelope: Callable[..., dict[str, Any]]
) -> None:
    """FR-01, doc 05 s2: unknown acronym is `not_found` in the error envelope."""
    for path in (
        "/investigations/NO-SUCH-INVESTIGATION",
        "/investigations/NO-SUCH-INVESTIGATION/runs",
    ):
        assert_error_envelope(api.get(path), 404, "not_found")


# --- runs, variables, publications ----------------------------------------------------------


def _runs(api: httpx.Client, acronym: str) -> dict[str, Any]:
    response = api.get(f"/investigations/{acronym}/runs", params={"page_size": MAX_PAGE_SIZE})
    assert response.status_code == httpx.codes.OK, response.text
    return dict(response.json())


def test_fr06_runs_page_matches_database(
    stack: str, api: httpx.Client, sql: Rows, seed_acronyms: list[str]
) -> None:
    """FR-06, CF-04: `/runs` is a page whose `total` equals the database runs."""
    counts = {
        row["acronym"]: row["n"]
        for row in sql(
            "SELECT i.acronym, count(t.id) AS n FROM investigation i "
            "LEFT JOIN test_run t ON t.investigation_id = i.id GROUP BY i.acronym"
        )
    }
    bodies = {acronym: _runs(api, acronym) for acronym in seed_acronyms}
    assert {acronym: body["total"] for acronym, body in bodies.items()} == counts
    bad_items = [
        item for body in bodies.values() for item in body["items"] if set(item) != RUN_FIELDS
    ]
    assert bad_items == []


def _condition_values(runs: list[dict[str, Any]], name: str) -> list[Any]:
    return sorted({run["condition"].get(name) for run in runs} - {None})


def _variable_inconsistencies(variables: dict[str, Any], runs: list[dict[str, Any]]) -> list[str]:
    problems = []
    for varied in variables["varied"]:
        if varied["name"] in CONDITION_DIMENSIONS and sorted(
            varied["values"]
        ) != _condition_values(runs, varied["name"]):
            problems.append(f"varied {varied['name']}")
    for fixed in variables["fixed"]:
        if fixed["name"] in CONDITION_DIMENSIONS and _condition_values(
            runs, fixed["name"]
        ) not in ([], [fixed["value"]]):
            problems.append(f"fixed {fixed['name']}")
    return problems


def test_fr06_variables_consistent_with_runs(
    stack: str, api: httpx.Client, seed_acronyms: list[str]
) -> None:
    """FR-06: varied values are the distinct run values; fixed values hold for every run."""
    problems = {}
    for acronym in seed_acronyms:
        runs = _runs(api, acronym)
        variables = api.get(f"/investigations/{acronym}/variables").json()
        assert set(variables) == {"varied", "fixed", "run_count"}
        assert variables["run_count"] == runs["total"]
        problems[acronym] = _variable_inconsistencies(variables, runs["items"])
    assert problems == {acronym: [] for acronym in seed_acronyms}


def test_fr01_publications_match_seed(
    stack: str, api: httpx.Client, seed_records: dict[str, dict[str, Any]]
) -> None:
    """FR-01: `/publications` lists the seed publications with the documented fields."""
    actual = {}
    for acronym in seed_records:
        publications = api.get(f"/investigations/{acronym}/publications").json()
        assert all(set(item) >= PUBLICATION_FIELDS for item in publications)
        actual[acronym] = sorted(item["title"] for item in publications)
    expected = {
        acronym: sorted(item["title"] for item in record.get("publications") or [])
        for acronym, record in seed_records.items()
    }
    assert actual == expected


# --- facets, hardware lineage, projects -----------------------------------------------------


COUNT_BY_VALUE = "SELECT {value} AS value, count(*) AS n FROM {source} GROUP BY 1"
FACET_SOURCES = {
    "fuel_phase": ("v", "investigation, unnest(fuel_phases) v"),
    "tag": ("v", "investigation, unnest(fire_safety_tags) v"),
    "platform": ("platform", "investigation WHERE platform IS NOT NULL"),
    "gravity_level": ("gravity_level", "investigation WHERE gravity_level IS NOT NULL"),
    "hardware": ("h.name", "investigation_hardware ih JOIN hardware h ON h.id = ih.hardware_id"),
    "project": ("p.name", "investigation i JOIN project p ON p.id = i.project_id"),
}
FACET_QUERIES = {
    name: COUNT_BY_VALUE.format(value=value, source=source)
    for name, (value, source) in FACET_SOURCES.items()
}


def test_fr02_facet_counts_equal_database(stack: str, api: httpx.Client, sql: Rows) -> None:
    """FR-02, doc 05 s4: every facet lists each value with its investigation count."""
    facets = api.get("/facets").json()
    assert set(facets) == set(FACETS)
    actual = {
        name: sorted((item["value"], item["count"]) for item in facets[name]) for name in FACETS
    }
    expected = {
        name: sorted((row["value"], row["n"]) for row in sql(FACET_QUERIES[name]))
        for name in FACETS
    }
    assert actual == expected


def test_fr02_single_valued_facets_sum_to_catalog(
    stack: str, api: httpx.Client, sql: Rows
) -> None:
    """FR-02: platform and gravity-level counts sum to the investigations stating them."""
    facets = api.get("/facets").json()
    for name in ("platform", "gravity_level"):
        statement = f"SELECT count(*) AS n FROM investigation WHERE {name} IS NOT NULL"  # noqa: S608
        stated = sql(statement)[0]["n"]
        assert sum(item["count"] for item in facets[name]) == stated


def test_fr12_lineage_graph_integrity(
    lineage: dict[str, Any], seed_acronyms: list[str], hardware_names: list[str]
) -> None:
    """FR-12: unique node IDs; edges end at nodes; every investigation and hardware is a node."""
    ids = [node["id"] for node in lineage["nodes"]]
    assert len(ids) == len(set(ids))
    dangling = [
        edge for edge in lineage["edges"] if edge["source"] not in ids or edge["target"] not in ids
    ]
    assert dangling == []
    expected = {f"inv:{acronym}" for acronym in seed_acronyms} | {
        f"hw:{name}" for name in hardware_names
    }
    assert expected <= set(ids)


def _seeded_uses(seed_records: dict[str, dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        (f"inv:{acronym}", f"hw:{item['name']}", item["role"])
        for acronym, record in seed_records.items()
        for item in record.get("hardware") or []
    }


def _served_uses(lineage: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (edge["source"], edge["target"], edge["role"])
        for edge in lineage["edges"]
        if edge["source"].startswith("inv:") and edge["target"].startswith("hw:")
    }


def _seeded_parents(hardware_file: dict[str, Any]) -> set[tuple[str, str]]:
    items = [item for item in hardware_file["hardware"] if item.get("parent")]
    return {(f"hw:{item['name']}", f"hw:{item['parent']}") for item in items}


def _seeded_members(seed_records: dict[str, dict[str, Any]]) -> set[tuple[str, str]]:
    projects = {acronym: record.get("project") for acronym, record in seed_records.items()}
    return {(f"inv:{acronym}", f"proj:{name}") for acronym, name in projects.items() if name}


def test_fr12_lineage_edges_follow_seed_files(
    lineage: dict[str, Any],
    lineage_edges: Callable[..., set[tuple[str, str]]],
    seed_records: dict[str, dict[str, Any]],
    hardware_file: dict[str, Any],
) -> None:
    """FR-12: apparatus/host/instrument edges, `hosted_in` parents and `member_of` projects."""
    actual = (_served_uses(lineage), lineage_edges("hosted_in"), lineage_edges("member_of"))
    expected = (
        _seeded_uses(seed_records),
        _seeded_parents(hardware_file),
        _seeded_members(seed_records),
    )
    assert actual == expected


def test_fr12_documented_hardware_relationships(
    lineage_edges: Callable[..., set[tuple[str, str]]], seed_acronyms: list[str]
) -> None:
    """FR-12, doc 01 s6: MDCA, SPICE flow duct, CIR and MSG users, where seeded."""
    expected = {
        (f"inv:{acronym}", f"hw:{hardware}")
        for hardware, users in DOCUMENTED_HARDWARE_USERS.items()
        for acronym in users
        if acronym in seed_acronyms
    }
    assert expected - lineage_edges() == set()


def test_fr12_shared_smoke_instrument(
    lineage: dict[str, Any],
    lineage_edges: Callable[..., set[tuple[str, str]]],
    seed_acronyms: list[str],
) -> None:
    """FR-12, doc 01 s6: SAME and SAME-R share an instrument reused in DAFT and DAFT-2."""
    seeded = [acronym for acronym in SHARED_INSTRUMENT_USERS if acronym in seed_acronyms]
    if len(seeded) < len(SHARED_INSTRUMENT_USERS):
        pytest.skip(f"precondition absent: seed set lacks some of {SHARED_INSTRUMENT_USERS}")
    kinds = {node["id"]: node.get("kind") for node in lineage["nodes"]}
    instruments = [
        {
            target
            for source, target in lineage_edges()
            if source == f"inv:{acronym}" and kinds.get(target) == "instrument"
        }
        for acronym in seeded
    ]
    assert set.intersection(*instruments)


def test_fr12_projects_list_members(
    stack: str,
    api: httpx.Client,
    hardware_file: dict[str, Any],
    seed_records: dict[str, dict[str, Any]],
) -> None:
    """FR-12, doc 05 s4: each project with its description and member acronyms."""
    expected = [
        {
            "name": project["name"],
            "description": project["description"],
            "investigations": sorted(
                a for a, record in seed_records.items() if record.get("project") == project["name"]
            ),
        }
        for project in sorted(hardware_file["projects"], key=lambda item: item["name"])
    ]
    served = api.get("/projects").json()
    assert [
        {**item, "investigations": sorted(item["investigations"])} for item in served
    ] == expected
