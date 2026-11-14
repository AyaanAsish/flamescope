"""Compare (document 12 section 2; document 05 section 6; document 07 sections 3 and 4).

Requirements: FR-05 (compare 2 to 4 investigations: matrix, shared facts, cited narrative),
FR-15 (citations on narrative sentences), NFR-02 (narrative `ok` in mock mode).
Call flow: CF-06 (Compare; one comparator call, citation verifier).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.order(13)]

DOC_05 = "05-api-specification.md"
ATTRIBUTE_ORDER_PREFIX = "Attributes in the matrix, in order:"
RESPONSE_FIELDS = {"investigations", "matrix", "shared", "narrative"}
ROW_FIELDS = {"attribute", "label", "group", "values", "same"}
MIN_COMPARED, MAX_COMPARED = 2, 4


def _compare(api: httpx.Client, acronyms: list[str], *, narrative: bool) -> httpx.Response:
    return api.post("/compare", json={"investigations": acronyms, "narrative": narrative})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _shared(
    details: list[Mapping[str, Any]], key: Callable[[Mapping[str, Any]], set[str]]
) -> list[str]:
    return sorted(set.intersection(*(key(detail) for detail in details)))


@pytest.fixture(scope="module")
def attribute_order(
    doc_section: Callable[[str, str], str], code_names: Callable[[str], list[str]]
) -> list[str]:
    """Document 05 section 6: matrix attributes, in order."""
    section = doc_section(DOC_05, "## 6. Compare")
    line = next(line for line in section.splitlines() if line.startswith(ATTRIBUTE_ORDER_PREFIX))
    return code_names(line)


@pytest.fixture(scope="module")
def chosen(seed_acronyms: list[str]) -> list[str]:
    if len(seed_acronyms) < MAX_COMPARED + 1:
        pytest.skip("precondition absent: fewer than five seed investigations")
    return sorted(seed_acronyms)


@pytest.mark.parametrize("count", range(MIN_COMPARED, MAX_COMPARED + 1))
def test_fr05_compare_two_to_four(
    count: int, chosen: list[str], stack: str, api: httpx.Client, attribute_order: list[str]
) -> None:
    """FR-05, doc 05 s6: response shape; investigations in request order; attribute order."""
    acronyms = chosen[:count]
    response = _compare(api, acronyms, narrative=False)
    assert response.status_code == httpx.codes.OK, response.text
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert [item["acronym"] for item in body["investigations"]] == acronyms
    assert [row["attribute"] for row in body["matrix"]] == attribute_order
    assert {frozenset(row) for row in body["matrix"]} == {frozenset(ROW_FIELDS)}
    assert {tuple(row["values"]) for row in body["matrix"]} == {tuple(acronyms)}


@pytest.mark.parametrize("count", [1, MAX_COMPARED + 1])
def test_fr05_wrong_count_is_bad_request(
    count: int,
    chosen: list[str],
    stack: str,
    api: httpx.Client,
    assert_error_envelope: Callable[..., Any],
) -> None:
    """FR-05, doc 05 s2: fewer than 2 or more than 4 IDs is HTTP 400 `bad_request`."""
    assert_error_envelope(_compare(api, chosen[:count], narrative=False), 400, "bad_request")


def test_fr05_unknown_acronym_is_not_found(
    chosen: list[str], stack: str, api: httpx.Client, assert_error_envelope: Callable[..., Any]
) -> None:
    """FR-05, doc 05 s2: an unknown acronym is HTTP 404 `not_found`."""
    assert_error_envelope(
        _compare(api, [chosen[0], "NO-SUCH-INVESTIGATION"], narrative=False), 404, "not_found"
    )


def test_fr05_same_flag_recomputed_from_values(
    chosen: list[str], stack: str, api: httpx.Client
) -> None:
    """FR-05: `same` is true exactly when every investigation has the same value."""
    matrix = _compare(api, chosen[:MAX_COMPARED], narrative=False).json()["matrix"]
    wrong = [
        row["attribute"]
        for row in matrix
        if row["same"] != (len({_canonical(v) for v in row["values"].values()}) == 1)
    ]
    assert wrong == []


def test_fr05_shared_hardware_tags_and_instruments(
    chosen: list[str], stack: str, api: httpx.Client
) -> None:
    """FR-05, FR-12: `shared` is the intersection of hardware, tags and instruments."""
    acronyms = chosen[: MIN_COMPARED + 1]
    details = [api.get(f"/investigations/{acronym}").json() for acronym in acronyms]
    expected = {
        "hardware": _shared(details, lambda d: set(d["hardware"])),
        "tags": _shared(details, lambda d: set(d["fire_safety_tags"])),
        "instruments": _shared(details, lambda d: {m["instrument"] for m in d["measurements"]}),
    }
    shared = _compare(api, acronyms, narrative=False).json()["shared"]
    assert {key: sorted(values) for key, values in shared.items()} == expected


def test_fr05_narrative_ok_with_citations_in_mock_mode(
    chosen: list[str], stack: str, api: httpx.Client, source_ref_is_valid: Callable[..., bool]
) -> None:
    """FR-05, FR-15, CF-06: mock narrative is `ok` and every sentence cites a source."""
    narrative = _compare(api, chosen[: MIN_COMPARED + 1], narrative=True).json()["narrative"]
    assert narrative["status"] == "ok"
    assert narrative["sentences"]
    uncited = [
        s["text"]
        for s in narrative["sentences"]
        if not s["citations"] or not all(map(source_ref_is_valid, s["citations"]))
    ]
    assert uncited == []
    assert all(sentence["text"] in narrative["text"] for sentence in narrative["sentences"])


def test_fr05_narrative_false_is_skipped(chosen: list[str], stack: str, api: httpx.Client) -> None:
    """FR-05, doc 05 s6: `narrative=false` gives status `skipped` and no sentences."""
    narrative = _compare(api, chosen[:MIN_COMPARED], narrative=False).json()["narrative"]
    assert (narrative["status"], narrative["sentences"]) == ("skipped", [])
