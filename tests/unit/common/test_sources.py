"""`SourceRef` and allowed URIs (document 04 section 3; FR-15)."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError as PydanticValidationError

from flamescope_common.sources import (
    SourceKind,
    SourceRef,
    curated_source,
    is_allowed_uri,
    truncate_quote,
)

pytestmark = pytest.mark.unit

MAX_QUOTE = 240
CHALLENGE_PAGE = "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/"
ALLOWED_URIS = [
    "https://psi.nasa.gov/investigation/example",
    "https://doi.org/10.0000/example",
    "s3://nasa-psi/some/folder/file.pdf",
    CHALLENGE_PAGE,
]
REJECTED_URIS = [
    "http://psi.nasa.gov/insecure",
    "https://",
    "s3://nasa-psi/",
    "s3://another-bucket/key.pdf",
    "ftp://example.org/file",
    "file:///etc/passwd",
    "psi.nasa.gov/no-scheme",
    "",
]


def test_kinds_equal_document_04_section_3() -> None:
    """FR-15: the five source kinds."""
    assert set(get_args(SourceKind)) == {
        "psi_page",
        "document",
        "publication",
        "s3_object",
        "curated",
    }


def test_kind_and_uri_are_the_only_required_fields() -> None:
    """FR-15: `kind` and `uri` are required; the rest is optional."""
    source = SourceRef(kind="document", uri="s3://nasa-psi/a.pdf")

    assert (source.title, source.locator, source.quote, source.chunk_id) == (None,) * 4


@pytest.mark.parametrize("missing", ["kind", "uri"])
def test_missing_required_field_is_rejected(missing: str) -> None:
    """FR-15: a source without `kind` or `uri` is invalid."""
    fields = {"kind": "document", "uri": "s3://nasa-psi/a.pdf"}
    del fields[missing]

    with pytest.raises(PydanticValidationError):
        SourceRef.model_validate(fields)


def test_unknown_kind_is_rejected() -> None:
    """FR-15: only the documented kinds."""
    with pytest.raises(PydanticValidationError):
        SourceRef(kind="blog", uri="https://example.org/post")  # type: ignore[arg-type]


@pytest.mark.parametrize("uri", ALLOWED_URIS)
def test_allowed_uri_schemes(uri: str) -> None:
    """FR-15: any https URL with a host and any non-empty key under s3://nasa-psi/."""
    assert is_allowed_uri(uri)
    assert SourceRef(kind="psi_page", uri=uri).uri == uri


@pytest.mark.parametrize("uri", REJECTED_URIS)
def test_disallowed_uris_are_rejected(uri: str) -> None:
    """FR-15: no other scheme, bucket or host-less URL."""
    assert not is_allowed_uri(uri)
    with pytest.raises(PydanticValidationError):
        SourceRef(kind="document", uri=uri)


def test_full_source_ref_shape() -> None:
    """FR-15: the JSON shape of document 04 section 3 round-trips."""
    shape = {
        "kind": "document",
        "uri": "s3://nasa-psi/folder/srd.pdf",
        "title": "Science Requirements Document",
        "locator": "page 14",
        "quote": "short supporting excerpt",
        "chunk_id": 1234,
    }

    assert SourceRef.model_validate(shape).model_dump() == shape


def test_quote_of_240_characters_is_accepted_and_241_rejected() -> None:
    """FR-15: quotes are at most 240 characters."""
    SourceRef(kind="document", uri="s3://nasa-psi/a.pdf", quote="q" * MAX_QUOTE)

    with pytest.raises(PydanticValidationError):
        SourceRef(kind="document", uri="s3://nasa-psi/a.pdf", quote="q" * (MAX_QUOTE + 1))


def test_curated_source_requires_an_allowed_uri() -> None:
    """FR-15: `curated` still carries a PSI, DOI or challenge-page URI."""
    assert curated_source(CHALLENGE_PAGE).kind == "curated"
    with pytest.raises(PydanticValidationError):
        curated_source("internal-notes")


def test_truncate_quote_collapses_whitespace_and_limits_length() -> None:
    """FR-15: helper keeps quotes within the limit."""
    assert truncate_quote("  flame   spread\n rate ") == "flame spread rate"
    assert len(truncate_quote("word " * 200)) == MAX_QUOTE
