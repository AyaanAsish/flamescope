"""`CitationVerifier`: deterministic, LLM-free support check of cited sentences (doc 07 s4).

A sentence is supported when it cites at least one known context entry, every number in it
(unit-normalized) appears in the cited text, and the share of its content words found in the
cited text reaches `VERIFY_MIN_OVERLAP`. With several citations the cited texts are pooled.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from flamescope_common.config import Settings, get_settings
from flamescope_common.schemas.agents import (
    INSUFFICIENT_INFORMATION_SENTENCE,
    SentenceWithFacts,
    VerifiedAnswer,
)
from flamescope_common.schemas.api import VerifiedSentence
from flamescope_common.sources import SourceRef
from flamescope_common.units import PERCENT_PER_FRACTION, to_cm_s, to_kpa

NUMBER_RELATIVE_TOLERANCE = 0.01
MIN_CONTENT_WORD_LENGTH = 3
_STOP_WORD_TEXT = (
    "a an and are as at be been but by can for from had has have in into is it its of on or "
    "that the their these this those to was were which with within also than then there"
)
STOP_WORDS = frozenset(_STOP_WORD_TEXT.split())

_MARKER = re.compile(r"\s*\[([cf]:\d+)\]")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
# Markers that open a split piece belong to the previous sentence ("... text. [c:1] Next ...").
_LEADING_MARKERS = re.compile(r"^((?:\s*\[[cf]:\d+\])+)\s*[.!?]*\s*(.*)$", re.DOTALL)
_NUMBER_WITH_UNIT = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(%|kpa|psi|atm|bar|torr|cm/s|mm/s|m/s)?", re.I
)
_WORD = re.compile(r"[a-z0-9]+")
_PRESSURE_UNITS = {"kpa", "psi", "atm", "bar", "torr"}
_SPEED_UNITS = {"cm/s", "mm/s", "m/s"}


@dataclass(frozen=True)
class ContextEntry:
    """A citable context item: its text and the `SourceRef` a citation to it carries."""

    text: str
    source: SourceRef


@dataclass(frozen=True)
class _Claim:
    text: str
    citation_ids: tuple[str, ...]


def split_sentences(draft: str) -> list[str]:
    """Split on sentence punctuation; trailing citation markers stay with their sentence."""
    sentences: list[str] = []
    for piece in _SENTENCE_BOUNDARY.split(draft.strip()):
        remainder = piece.strip()
        leading = _LEADING_MARKERS.match(remainder)
        if sentences and leading:
            sentences[-1] = f"{sentences[-1]} {leading.group(1).strip()}"
            remainder = leading.group(2).strip()
        if remainder:
            sentences.append(remainder)
    return sentences


def _number_forms(value: float, unit: str | None) -> list[float]:
    """The number as written plus its canonical form (kPa, fraction, cm/s) when it has a unit."""
    key = (unit or "").lower()
    if key in _PRESSURE_UNITS:
        return [value, to_kpa(value, key)]
    if key in _SPEED_UNITS:
        return [value, to_cm_s(value, key)]
    if key == "%":
        return [value, value / PERCENT_PER_FRACTION]
    return [value]


def _numbers(text: str) -> list[list[float]]:
    return [
        _number_forms(float(match.group(1)), match.group(2))
        for match in _NUMBER_WITH_UNIT.finditer(text)
    ]


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in _WORD.findall(text.lower())
        if len(word) >= MIN_CONTENT_WORD_LENGTH and word not in STOP_WORDS and not word.isdigit()
    }


def _numbers_supported(sentence: str, cited_text: str) -> bool:
    available = [form for forms in _numbers(cited_text) for form in forms]
    return all(
        any(
            math.isclose(form, known, rel_tol=NUMBER_RELATIVE_TOLERANCE)
            for form in forms
            for known in available
        )
        for forms in _numbers(sentence)
    )


def _overlap(sentence: str, cited_text: str) -> float:
    words = _content_words(sentence)
    if not words:
        return 0.0
    return len(words & _content_words(cited_text)) / len(words)


class CitationVerifier:
    """Keeps sentences whose citations support them and counts the dropped ones."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._min_overlap = (settings or get_settings()).verify_min_overlap

    def verify(
        self, sentences: str | Sequence[SentenceWithFacts], context: Mapping[str, ContextEntry]
    ) -> VerifiedAnswer:
        """Verify an Ask draft (text with `[c:ID]` / `[f:ID]` markers) or fact-cited sentences.

        `context` is keyed by marker (`c:123`, `f:45`) or by fact ID.
        """
        claims = self._claims(sentences)
        kept = [verified for claim in claims if (verified := self._check(claim, context))]
        dropped = len(claims) - len(kept)
        if not kept:
            fixed = VerifiedSentence(text=INSUFFICIENT_INFORMATION_SENTENCE, supported=True)
            return VerifiedAnswer(
                sentences=[fixed], dropped=dropped, text=INSUFFICIENT_INFORMATION_SENTENCE
            )
        return VerifiedAnswer(
            sentences=kept, dropped=dropped, text=" ".join(item.text for item in kept)
        )

    def _claims(self, sentences: str | Sequence[SentenceWithFacts]) -> list[_Claim]:
        if isinstance(sentences, str):
            return [self._claim(text, []) for text in split_sentences(sentences)]
        return [self._claim(item.text, item.fact_ids) for item in sentences]

    def _claim(self, text: str, fact_ids: Sequence[str]) -> _Claim:
        marker_ids = _MARKER.findall(text)
        bare_text = _MARKER.sub("", text).strip()
        return _Claim(bare_text, tuple(dict.fromkeys([*fact_ids, *marker_ids])))

    def _check(
        self, claim: _Claim, context: Mapping[str, ContextEntry]
    ) -> VerifiedSentence | None:
        entries = [context[key] for key in claim.citation_ids if key in context]
        if not entries or not claim.text:
            return None
        cited_text = "\n".join(entry.text for entry in entries)
        if not _numbers_supported(claim.text, cited_text):
            return None
        if _overlap(claim.text, cited_text) < self._min_overlap:
            return None
        return VerifiedSentence(
            text=claim.text, citations=[entry.source for entry in entries], supported=True
        )
