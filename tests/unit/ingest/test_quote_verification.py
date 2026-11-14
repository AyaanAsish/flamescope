"""FR-01, FR-15: stage 4 quote verification (document 06 section 3.4, document 07 section 3).

Each extracted field cites a `DraftSource {doc_id, quote}`; the quote must be a substring of
the cited parsed text, failing fields are nulled and reported, and the `doc_id` becomes the
document URI of the resulting `SourceRef`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pytest

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.config import Settings
from flamescope_common.errors import IngestError
from flamescope_common.schemas.agents import ExtractorInput, ExtractorOutput
from flamescope_common.sources import SourceRef
from flamescope_ingest.discover import Manifest, RawLayout, read_json, write_json
from flamescope_ingest.extract_stage import (
    DraftCardBuilder,
    ExtractStage,
    QuoteVerifier,
    build_context_batches,
)
from flamescope_ingest.parser import ParsedDoc, ParsedSection

pytestmark = pytest.mark.unit

ACRONYM = "TEST-1"
PREFIX = "combustion/TEST-1/"
DOC_URI = "s3://nasa-psi/combustion/TEST-1/overview.html"
SECTION_TEXT = "The burner   supplied an oxygen fraction of 0.40 at 50 kPa."
PROMPT_VERSION = "extractor@1"


def _parsed(
    doc_ref: str = DOC_URI, text: str = SECTION_TEXT, title: str = "Overview"
) -> ParsedDoc:
    return ParsedDoc(
        doc_ref=doc_ref,
        title=title,
        kind="html",
        sections=[ParsedSection(heading="Results", text=text, char_start=0, char_end=len(text))],
        source_sha256="sha-" + doc_ref,
    )


def _output(**fields: Any) -> ExtractorOutput:
    return ExtractorOutput.model_validate(fields)


def _source(quote: str | None, doc_id: str = "D1") -> dict[str, Any]:
    return {"doc_id": doc_id, "quote": quote}


@pytest.fixture
def verifier() -> QuoteVerifier:
    return QuoteVerifier({"D1": _parsed()})


def test_verbatim_quote_becomes_source_ref(verifier: QuoteVerifier) -> None:
    """The `doc_id` becomes the document URI (document 07 section 3, ExtractorAgent)."""
    resolved = verifier.resolve(
        _output(objectives=[{"text": "t", "source": _source("oxygen fraction of 0.40")}])
        .objectives[0]
        .source,
        "objectives[0].source",
    )
    assert resolved is not None
    source = SourceRef.model_validate(resolved)
    assert source.uri == DOC_URI
    assert source.quote == "oxygen fraction of 0.40"
    assert verifier.failures == []


def test_quote_matches_across_collapsed_whitespace(verifier: QuoteVerifier) -> None:
    draft = _output(objectives=[{"text": "t", "source": _source("The burner supplied")}])
    assert verifier.resolve(draft.objectives[0].source, "objectives[0].source") is not None


def test_quote_not_in_cited_text_is_rejected_and_reported(verifier: QuoteVerifier) -> None:
    draft = _output(objectives=[{"text": "t", "source": _source("oxygen fraction of 0.45")}])
    assert verifier.resolve(draft.objectives[0].source, "objectives[0].source") is None
    assert verifier.failures == ["objectives[0].source: quote not found in " + DOC_URI]


def test_unknown_document_is_rejected(verifier: QuoteVerifier) -> None:
    draft = _output(objectives=[{"text": "t", "source": _source("burner", doc_id="D9")}])
    assert verifier.resolve(draft.objectives[0].source, "objectives[0].source") is None
    assert len(verifier.failures) == 1


def test_quote_from_other_document_is_rejected() -> None:
    """The quote must occur in the cited document, not merely somewhere in the corpus."""
    verifier = QuoteVerifier(
        {"D1": _parsed(), "D2": _parsed("s3://nasa-psi/combustion/TEST-1/b.txt", "Other text.")}
    )
    draft = _output(objectives=[{"text": "t", "source": _source("Other text.", doc_id="D1")}])
    assert verifier.resolve(draft.objectives[0].source, "objectives[0].source") is None


def test_failing_fields_are_nulled_and_reported() -> None:
    """Document 06 s3.4: failing fields are nulled and reported; supported ones are kept."""
    verifier = QuoteVerifier({"D1": _parsed()})
    output = _output(
        objectives=[
            {"text": "kept", "source": _source("oxygen fraction of 0.40")},
            {"text": "dropped", "source": _source("not in the text")},
        ],
        conditions={
            "o2_fraction": {"min": 0.4, "max": 0.4, "source": _source("0.40")},
            "pressure_kpa": {"min": 70, "max": 70, "source": _source("70 kPa")},
        },
        findings=[
            {
                "statement": "s",
                "category": "fundamental",
                "confidence": 0.5,
                "source": _source("absent quote"),
            }
        ],
    )
    card = DraftCardBuilder(verifier).build(output)
    assert [objective["text"] for objective in card["objectives"]] == ["kept"]
    assert card["conditions"]["o2_fraction"]["min"] == pytest.approx(0.4)
    assert card["conditions"]["pressure_kpa"] is None
    assert card["findings"] == []
    assert len(verifier.failures) == 3


def test_context_batches_put_overview_first() -> None:
    """Context pack: overview text first, then sections ranked by keywords (doc 06 s3.4)."""
    other = _parsed("s3://nasa-psi/combustion/TEST-1/a_paper.pdf", "fuel oxygen pressure flow")
    overview = _parsed("s3://nasa-psi/combustion/TEST-1/overview.html", "plain words")
    batches, by_id = build_context_batches([other, overview])
    assert by_id["D1"].doc_ref.endswith("overview.html")
    assert batches[0][0].doc_id == "D1"


class FakeOrchestrator:
    """Stands in for `AgentOrchestrator`: returns a fixed extractor output."""

    def __init__(self, output: ExtractorOutput) -> None:
        self._output = output
        self.payloads: list[ExtractorInput] = []

    def prompt_version(self, name: str) -> str:
        assert name == "extractor"
        return PROMPT_VERSION

    async def run(self, name: str, payload: ExtractorInput) -> ExtractorOutput:
        assert name == "extractor"
        self.payloads.append(payload)
        return self._output


def _prepare(settings: Settings, documents: Sequence[ParsedDoc]) -> RawLayout:
    layout = RawLayout(settings.raw_dir)
    manifest = Manifest(acronym=ACRONYM, prefix=PREFIX, listing_hash="h")
    write_json(layout.manifest_path(ACRONYM), manifest.model_dump(mode="json"))
    for index, document in enumerate(documents):
        write_json(layout.parsed_dir(ACRONYM) / f"{index}.json", document.model_dump(mode="json"))
    return layout


def _stage(settings: Settings, output: ExtractorOutput) -> tuple[ExtractStage, FakeOrchestrator]:
    orchestrator = FakeOrchestrator(output)
    layout = _prepare(settings, [_parsed()])
    return ExtractStage(settings, cast(AgentOrchestrator, orchestrator), layout), orchestrator


def test_extract_stage_writes_verified_draft(ingest_settings: Settings) -> None:
    """Artifact `/data/raw/<acr>/card.draft.json` (document 06 section 2)."""
    output = _output(
        objectives=[
            {"text": "ok", "source": _source("an oxygen fraction")},
            {"text": "bad", "source": _source("invented quote")},
        ]
    )
    stage, orchestrator = _stage(ingest_settings, output)
    result = stage.extract(ACRONYM)
    assert result.llm_calls == len(orchestrator.payloads) == 1
    assert [item["text"] for item in result.card["objectives"]] == ["ok"]
    assert result.quote_failures == ["objectives[1].source: quote not found in " + DOC_URI]
    stored = read_json(RawLayout(ingest_settings.raw_dir).draft_path(ACRONYM))
    assert stored["objectives"] == result.card["objectives"]
    assert stored["acronym"] == ACRONYM


def test_extract_stage_applies_overrides_on_top(ingest_settings: Settings) -> None:
    """Overrides in `src/data/overrides/<acronym>.yaml` are deep-merged on top."""
    (ingest_settings.data_dir / "overrides" / f"{ACRONYM}.yaml").write_text(
        "title: Curated title\nplatform: ISS\n", encoding="utf-8"
    )
    stage, _ = _stage(ingest_settings, _output(platform="ground"))
    result = stage.extract(ACRONYM)
    assert result.card["title"] == "Curated title"
    assert result.card["platform"] == "ISS"
    assert result.overrides is not None
    assert {"title", "platform"} <= result.overrides.paths


def test_extract_stage_is_skipped_when_inputs_unchanged(ingest_settings: Settings) -> None:
    """Idempotency key: hash of parsed docs + prompt version; `--force` reruns."""
    stage, orchestrator = _stage(ingest_settings, _output())
    stage.extract(ACRONYM)
    assert stage.extract(ACRONYM).skipped
    assert len(orchestrator.payloads) == 1
    assert not stage.extract(ACRONYM, force=True).skipped
    assert len(orchestrator.payloads) == 2


def test_extract_stage_without_parsed_docs_fails(ingest_settings: Settings) -> None:
    orchestrator = cast(AgentOrchestrator, FakeOrchestrator(_output()))
    stage = ExtractStage(ingest_settings, orchestrator, RawLayout(ingest_settings.raw_dir))
    with pytest.raises(IngestError):
        stage.extract(ACRONYM)
