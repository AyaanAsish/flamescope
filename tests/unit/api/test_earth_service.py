"""FR-10: `EarthService` lists applications with links and references (doc 05 s9).

The repository is a fake; titles and links are placeholders, not scientific facts.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from flamescope_api.services.earth import EarthService

pytestmark = pytest.mark.unit

REFERENCE = {"kind": "psi_page", "uri": "https://psi.nasa.gov/test", "locator": "page 1"}


def _row(identifier: int, sector: str) -> SimpleNamespace:
    application = SimpleNamespace(
        id=identifier,
        title=f"Application {identifier}",
        sector=sector,
        description="Description.",
        maturity=None,
        references=[REFERENCE],
    )
    return SimpleNamespace(application=application, investigations=["ALPHA"], finding_ids=[7])


class FakeEarthRepo:
    def __init__(self) -> None:
        self.sectors: list[str | None] = []
        self._rows = [_row(1, "firefighting"), _row(2, "detection")]

    def list(self, sector: str | None = None) -> list[SimpleNamespace]:
        self.sectors.append(sector)
        return [row for row in self._rows if sector in (None, row.application.sector)]


def test_fr10_items_carry_links_and_references() -> None:
    """FR-10: each item has its investigations, finding IDs and source references."""
    item = EarthService(FakeEarthRepo()).list().items[0]  # type: ignore[arg-type]
    observed = (item.id, item.sector, item.investigations, item.findings, item.references[0].uri)
    assert observed == (1, "firefighting", ["ALPHA"], [7], REFERENCE["uri"])


def test_fr10_sector_filter_is_passed_to_the_repository() -> None:
    """FR-10: `sector` narrows the list."""
    repo = FakeEarthRepo()
    items = EarthService(repo).list("detection").items  # type: ignore[arg-type]
    assert ([item.id for item in items], repo.sectors) == ([2], ["detection"])
