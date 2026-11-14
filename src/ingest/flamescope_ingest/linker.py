"""Stage 6, link: projects, hardware, instruments and publications (document 06 section 3.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import structlog

from flamescope_common.schemas.card import CardPublication, HardwareRef, SeedInvestigation
from flamescope_ingest.seed import HardwareCatalog

logger = structlog.get_logger(__name__)

CROSSREF_WORKS_URL = "https://api.crossref.org/works/"
CROSSREF_TIMEOUT_S = 10.0
DOI_LOOKUP_ATTEMPTS = 3
YEAR_PARTS_KEY = "date-parts"
USER_AGENT = "flamescope-ingest/0.1"


class DoiResolver(Protocol):
    def resolve(self, doi: str) -> CardPublication | None: ...


@dataclass
class LinkResult:
    record: SeedInvestigation
    unknown_hardware: list[str] = field(default_factory=list)
    unresolved_dois: list[str] = field(default_factory=list)


def _first(values: Any) -> str | None:
    return values[0] if isinstance(values, list) and values else None


def _publication_year(message: dict[str, Any]) -> int | None:
    for key in ("issued", "published-print", "published-online"):
        parts = message.get(key, {}).get(YEAR_PARTS_KEY) or [[]]
        if parts[0] and isinstance(parts[0][0], int):
            return int(parts[0][0])
    return None


def _author_names(message: dict[str, Any]) -> list[str]:
    names = [
        f"{a.get('given', '')} {a.get('family', '')}".strip() for a in message.get("author", [])
    ]
    return [name for name in names if name]


class CrossrefResolver:
    """Resolves a DOI to title, authors, year and venue through the public Crossref API."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=CROSSREF_TIMEOUT_S, headers={"User-Agent": USER_AGENT}
        )

    def resolve(self, doi: str) -> CardPublication | None:
        message = self._fetch(doi)
        title = _first(message.get("title")) if message else None
        if message is None or title is None:
            return None
        return CardPublication(
            doi=doi,
            title=title,
            year=_publication_year(message),
            authors=_author_names(message),
            venue=_first(message.get("container-title")),
            url=f"https://doi.org/{doi}",
        )

    def _fetch(self, doi: str) -> dict[str, Any] | None:
        for attempt in range(1, DOI_LOOKUP_ATTEMPTS + 1):
            try:
                response = self._client.get(f"{CROSSREF_WORKS_URL}{doi}")
                if response.status_code == httpx.codes.NOT_FOUND:
                    return None
                response.raise_for_status()
                message = response.json().get("message")
                return message if isinstance(message, dict) else None
            except httpx.HTTPError as error:
                logger.warning("doi_lookup_failed", doi=doi, attempt=attempt, error=str(error))
        return None


class Linker:
    """Checks hardware against `hardware.yaml` and enriches publications when allowed."""

    def __init__(self, catalog: HardwareCatalog, resolver: DoiResolver | None = None) -> None:
        self._known_hardware = catalog.hardware_names()
        self._resolver = resolver

    def link(self, record: SeedInvestigation) -> LinkResult:
        known, unknown = self._split_hardware(record.hardware)
        publications, unresolved = self._publications(record.publications)
        linked = record.model_copy(update={"hardware": known, "publications": publications})
        return LinkResult(record=linked, unknown_hardware=unknown, unresolved_dois=unresolved)

    def _split_hardware(self, refs: list[HardwareRef]) -> tuple[list[HardwareRef], list[str]]:
        known = [ref for ref in refs if ref.name in self._known_hardware]
        unknown = [ref.name for ref in refs if ref.name not in self._known_hardware]
        return known, unknown

    def _publications(
        self, publications: list[CardPublication]
    ) -> tuple[list[CardPublication], list[str]]:
        if self._resolver is None:
            return publications, []
        resolved: list[CardPublication] = []
        unresolved: list[str] = []
        for publication in publications:
            enriched = self._enrich(publication)
            if enriched is None and publication.doi:
                unresolved.append(publication.doi)
            resolved.append(enriched or publication)
        return resolved, unresolved

    def _enrich(self, publication: CardPublication) -> CardPublication | None:
        if self._resolver is None or not publication.doi:
            return None
        found = self._resolver.resolve(publication.doi)
        if found is None:
            return None
        return publication.model_copy(
            update={
                "title": found.title,
                "year": found.year or publication.year,
                "authors": found.authors or publication.authors,
                "venue": found.venue or publication.venue,
                "url": found.url or publication.url,
            }
        )
