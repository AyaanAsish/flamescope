"""`CitationVerifier` (document 07 section 4; FR-05, FR-07, FR-11, FR-15)."""

from __future__ import annotations

import pytest

from flamescope_agents.citation_verifier import CitationVerifier, ContextEntry, split_sentences
from flamescope_common.config import Settings
from flamescope_common.schemas.agents import SentenceWithFacts
from flamescope_common.schemas.api import VerifiedSentence
from flamescope_common.sources import SourceRef

pytestmark = pytest.mark.unit

FIXED_SENTENCE = "The curated PSI corpus does not contain enough information to answer that."
CHUNK_SOURCE = SourceRef(kind="document", uri="s3://nasa-psi/test-folder/report.pdf")
FACT_SOURCE = SourceRef(kind="psi_page", uri="https://psi.nasa.gov/test-1")
CONTEXT = {
    "c:101": ContextEntry(
        text="TEST-1 burned thin samples in microgravity at 21% oxygen and 101.3 kPa.",
        source=CHUNK_SOURCE,
    ),
    "c:102": ContextEntry(
        text="Opposed flow of 5 cm/s was imposed in the test duct.", source=CHUNK_SOURCE
    ),
    "f1": ContextEntry(text="TEST-1 flew on the ISS in a test rack.", source=FACT_SOURCE),
}
SUPPORTED = "TEST-1 burned thin samples in microgravity at 21% oxygen. [c:101]"
NUMBER_MISMATCH = "TEST-1 burned thin samples in microgravity at 35% oxygen. [c:101]"
NO_MARKER = "TEST-1 burned thin samples in microgravity."


@pytest.fixture
def verifier() -> CitationVerifier:
    return CitationVerifier(Settings(_env_file=None))  # type: ignore[call-arg]


def test_supported_sentence_is_kept_without_its_marker(verifier: CitationVerifier) -> None:
    """FR-11: a supported sentence is kept, markers stripped, citation attached."""
    answer = verifier.verify(SUPPORTED, CONTEXT)

    assert answer.sentences == [
        VerifiedSentence(
            text="TEST-1 burned thin samples in microgravity at 21% oxygen.",
            citations=[CHUNK_SOURCE],
            supported=True,
        )
    ]
    assert answer.dropped == 0


def test_number_mismatch_is_dropped(verifier: CitationVerifier) -> None:
    """FR-11: every number in the sentence must appear in the cited text."""
    answer = verifier.verify(f"{SUPPORTED} {NUMBER_MISMATCH}", CONTEXT)

    assert [sentence.text for sentence in answer.sentences] == [
        "TEST-1 burned thin samples in microgravity at 21% oxygen."
    ]
    assert answer.dropped == 1


def test_sentence_without_marker_is_dropped(verifier: CitationVerifier) -> None:
    """FR-11: a sentence without a citation marker is unsupported."""
    answer = verifier.verify(f"{NO_MARKER} {SUPPORTED}", CONTEXT)

    assert len(answer.sentences) == 1
    assert answer.dropped == 1


def test_unknown_citation_is_dropped(verifier: CitationVerifier) -> None:
    """FR-15: a marker that names no supplied context entry supports nothing."""
    answer = verifier.verify(f"{SUPPORTED} TEST-1 burned thin samples. [c:999]", CONTEXT)

    assert answer.dropped == 1


def test_all_dropped_returns_the_fixed_sentence(verifier: CitationVerifier) -> None:
    """FR-11: when every sentence is dropped the fixed sentence is returned, uncited."""
    answer = verifier.verify(f"{NO_MARKER} {NUMBER_MISMATCH}", CONTEXT)

    assert answer.sentences == [VerifiedSentence(text=FIXED_SENTENCE, supported=True)]
    assert answer.dropped == 2


def test_dropped_counts_every_removed_sentence(verifier: CitationVerifier) -> None:
    """FR-11: `dropped` equals the number of unsupported sentences."""
    draft = " ".join([SUPPORTED, NUMBER_MISMATCH, NO_MARKER, SUPPORTED])

    answer = verifier.verify(draft, CONTEXT)

    assert (len(answer.sentences), answer.dropped) == (2, 2)


def test_numbers_are_compared_after_unit_normalization(verifier: CitationVerifier) -> None:
    """FR-11: 14.7 psi is supported by 101.3 kPa in the cited text."""
    sentence = "TEST-1 burned thin samples in microgravity at 14.7 psi. [c:101]"

    assert verifier.verify(sentence, CONTEXT).dropped == 0


def test_texts_cited_by_one_sentence_are_pooled(verifier: CitationVerifier) -> None:
    """FR-11: numbers and words may come from different cited entries."""
    sentence = "TEST-1 burned thin samples in opposed flow of 5 cm/s. [c:101] [c:102]"

    answer = verifier.verify(sentence, CONTEXT)

    assert answer.dropped == 0
    assert answer.sentences[0].citations == [CHUNK_SOURCE, CHUNK_SOURCE]


def test_low_word_overlap_is_dropped(verifier: CitationVerifier) -> None:
    """FR-11: content-word overlap must reach `VERIFY_MIN_OVERLAP` (0.35)."""
    sentence = "Researchers concluded cabin fabrics resist ignition everywhere. [c:101]"

    assert verifier.verify(sentence, CONTEXT).dropped == 1


def test_overlap_threshold_is_configurable() -> None:
    """FR-11: a stricter `VERIFY_MIN_OVERLAP` drops a partially supported sentence."""
    strict = CitationVerifier(Settings(_env_file=None, verify_min_overlap=0.95))  # type: ignore[call-arg]
    sentence = "TEST-1 burned thin samples in microgravity during several campaigns. [c:101]"

    assert CitationVerifier(Settings(_env_file=None)).verify(sentence, CONTEXT).dropped == 0  # type: ignore[call-arg]
    assert strict.verify(sentence, CONTEXT).dropped == 1


def test_fact_cited_sentences_are_verified_by_fact_id(verifier: CitationVerifier) -> None:
    """FR-05, FR-07: comparator and interpreter sentences cite by fact ID."""
    sentences = [
        SentenceWithFacts(text="TEST-1 flew on the ISS in a test rack.", fact_ids=["f1"]),
        SentenceWithFacts(text="TEST-1 flew on the ISS in a test rack.", fact_ids=[]),
    ]

    answer = verifier.verify(sentences, CONTEXT)

    assert answer.sentences[0].citations == [FACT_SOURCE]
    assert answer.dropped == 1


def test_markers_after_final_punctuation_stay_with_their_sentence() -> None:
    """FR-11: `<sentence>. [c:1] <next sentence>. [f:7]` keeps each marker on its sentence."""
    draft = "TEST-1 burned samples. [c:101] [c:102] TEST-1 flew on the ISS. [f:45] Done. [c:1]."

    assert split_sentences(draft) == [
        "TEST-1 burned samples. [c:101] [c:102]",
        "TEST-1 flew on the ISS. [f:45]",
        "Done. [c:1]",
    ]


def test_every_sentence_of_a_multi_sentence_answer_is_verified(
    verifier: CitationVerifier,
) -> None:
    """FR-11: each sentence is checked against its own trailing markers."""
    draft = f"{SUPPORTED} TEST-1 flew on the ISS in a test rack. [f:1]"
    context = CONTEXT | {"f:1": CONTEXT["f1"]}

    answer = verifier.verify(draft, context)

    assert [sentence.citations for sentence in answer.sentences] == [[CHUNK_SOURCE], [FACT_SOURCE]]
    assert answer.dropped == 0


def test_verification_is_deterministic(verifier: CitationVerifier) -> None:
    """FR-11: deterministic, no LLM."""
    draft = " ".join([SUPPORTED, NUMBER_MISMATCH, NO_MARKER])

    assert verifier.verify(draft, CONTEXT) == verifier.verify(draft, CONTEXT)
