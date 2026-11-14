"""Repositories: the only place that issues SQL (document 03 section 6)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnClause, literal_column

from flamescope_common.schemas.api import OpenRangePair

# An explicit regconfig: a plain string bind would be sent as varchar and fail to resolve.
ENGLISH_TS_CONFIG: ColumnClause[Any] = literal_column("'english'::regconfig")


def to_float(value: Decimal | float | None) -> float | None:
    """Numeric columns arrive as `Decimal`; the API speaks float."""
    return None if value is None else float(value)


def range_pair(low: Decimal | float | None, high: Decimal | float | None) -> OpenRangePair | None:
    """A `[min, max]` pair with a null open end (doc 04 s2), or None when both ends are null."""
    if low is None and high is None:
        return None
    return (to_float(low), to_float(high))
