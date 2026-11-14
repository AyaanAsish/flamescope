"""Provenance: the `SourceRef` model and helpers (document 04 section 3)."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceKind = Literal["psi_page", "document", "publication", "s3_object", "curated"]
MAX_QUOTE_CHARS = 240
S3_URI_PREFIX = "s3://nasa-psi/"
HTTPS_SCHEME = "https"


def is_allowed_uri(uri: str) -> bool:
    """True for an https URL (PSI page or DOI) or a key in the public `nasa-psi` bucket."""
    if uri.startswith(S3_URI_PREFIX):
        return len(uri) > len(S3_URI_PREFIX)
    parsed = urlparse(uri)
    return parsed.scheme == HTTPS_SCHEME and bool(parsed.netloc)


def truncate_quote(text: str) -> str:
    """Collapse whitespace and cut an excerpt to the SourceRef quote limit."""
    collapsed = " ".join(text.split())
    return collapsed[:MAX_QUOTE_CHARS]


class SourceRef(BaseModel):
    """Where a fact, score or generated claim comes from."""

    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    uri: str = Field(min_length=1)
    title: str | None = None
    locator: str | None = None
    quote: str | None = Field(default=None, max_length=MAX_QUOTE_CHARS)
    chunk_id: int | None = None

    @field_validator("uri")
    @classmethod
    def _uri_scheme_allowed(cls, uri: str) -> str:
        if not is_allowed_uri(uri):
            raise ValueError(f"uri must be an https URL or an {S3_URI_PREFIX} key, got {uri!r}")
        return uri


def curated_source(uri: str, title: str | None = None) -> SourceRef:
    """A `curated` source; only valid in seed and override files (document 04 section 3)."""
    return SourceRef(kind="curated", uri=uri, title=title)
