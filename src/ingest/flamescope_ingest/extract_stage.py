"""Stage 4, extract: `ExtractorAgent`, quote checks and overrides (document 06 section 3.4)."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog

from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_common.config import Settings
from flamescope_common.errors import IngestError
from flamescope_common.schemas.agents import (
    DraftConditions,
    DraftRange,
    DraftSource,
    ExtractorContextItem,
    ExtractorInput,
    ExtractorOutput,
)
from flamescope_common.schemas.card import CARD_SCHEMA_VERSION
from flamescope_common.sources import SourceRef
from flamescope_ingest.discover import Manifest, RawLayout, load_manifest, read_json, write_json
from flamescope_ingest.overrides import OverrideResult, apply_override
from flamescope_ingest.parser import ParsedDoc, load_parsed_docs

logger = structlog.get_logger(__name__)

EXTRACTOR_AGENT = "extractor"
CONTEXT_CHAR_BUDGET = 8000
MAX_SECTION_CHARS = 2500
MAX_EXTRACT_CALLS = 4
OVERVIEW_HINTS = ("overview", "index", "readme")
KEYWORDS = (
    "objective",
    "approach",
    "test matrix",
    "fuel",
    "oxygen",
    "pressure",
    "flow",
    "sample",
    "burner",
    "diagnostic",
    "result",
)
REPORT_KEY = "extraction_report"
CONDITION_DIMENSIONS = ("o2_fraction", "pressure_kpa", "flow_speed_cm_s")


@dataclass
class ExtractResult:
    """The draft card mapping plus what the stage did, for the ingest report."""

    card: dict[str, Any]
    skipped: bool = False
    llm_calls: int = 0
    quote_failures: list[str] = field(default_factory=list)
    overrides: OverrideResult | None = None


def _collapse(text: str) -> str:
    return " ".join(text.split())


class QuoteVerifier:
    """Resolves a draft source to a `SourceRef`; a quote must occur in the cited parsed text."""

    def __init__(self, documents: Mapping[str, ParsedDoc]) -> None:
        self._documents = documents
        self._text = {doc_id: _collapse(doc.full_text()) for doc_id, doc in documents.items()}
        self.failures: list[str] = []

    def resolve(self, draft: DraftSource | None, path: str) -> dict[str, Any] | None:
        """Card source mapping; None, with a recorded failure, when the citation is unproven."""
        if draft is None or draft.doc_id not in self._documents:
            self.failures.append(f"{path}: no valid document cited")
            return None
        document = self._documents[draft.doc_id]
        quote = _collapse(draft.quote) if draft.quote else None
        if quote and quote not in self._text[draft.doc_id]:
            self.failures.append(f"{path}: quote not found in {document.doc_ref}")
            return None
        source = SourceRef(
            kind="s3_object",
            uri=document.doc_ref,
            title=document.title,
            locator=_locate(document, quote),
            quote=quote,
        )
        return source.model_dump(mode="json", exclude_none=True)


def _locate(document: ParsedDoc, quote: str | None) -> str | None:
    """Page or heading of the first section that contains the quote."""
    if not quote:
        return None
    for section in document.sections:
        if quote in _collapse(section.text):
            return f"page {section.page}" if section.page is not None else section.heading
    return None


def _fuel_card(fuel: Any, source: dict[str, Any]) -> dict[str, Any]:
    geometry = {"shape": fuel.shape, "dimensions_mm": fuel.dimensions_mm}
    return {
        "name": fuel.name,
        "phase": fuel.phase,
        "material_class": fuel.material_class,
        "geometry": geometry if fuel.shape or fuel.dimensions_mm else None,
        "source": source,
    }


def _model_card(draft: Any, source: dict[str, Any]) -> dict[str, Any]:
    """Finding and measurement drafts already match the card shape except for the source."""
    return {**draft.model_dump(exclude={"source"}), "source": source}


def _text_card(draft: Any, source: dict[str, Any]) -> dict[str, Any]:
    return {"text": draft.text, "source": source}


class DraftCardBuilder:
    """Converts `ExtractorOutput` (doc_id and quote sources) to card mappings (DC-08)."""

    def __init__(self, verifier: QuoteVerifier) -> None:
        self._verify = verifier.resolve

    def build(self, output: ExtractorOutput) -> dict[str, Any]:
        approach = self._sourced(
            [output.approach] if output.approach else [], "approach", _text_card
        )
        return {
            "platform": output.platform,
            "gravity_level": output.gravity_level,
            "hardware": [item.model_dump() for item in output.hardware],
            "objectives": self._sourced(output.objectives, "objectives", _text_card),
            "approach": approach[0] if approach else None,
            "fuels": self._sourced(output.fuels, "fuels", _fuel_card),
            "conditions": self._conditions(output.conditions),
            "variables": {"varied": output.varied, "fixed": output.fixed},
            "measurements": self._sourced(output.measurements, "measurements", _model_card),
            "findings": self._sourced(output.findings, "findings", _model_card),
            "publications": [item.model_dump() for item in output.publications],
            "fire_safety_tags": list(output.fire_safety_tags),
            "field_confidence": output.field_confidence,
            "open_questions": output.open_questions,
        }

    def _sourced(
        self,
        drafts: Sequence[Any],
        path: str,
        build: Callable[[Any, dict[str, Any]], dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Items whose cited quote verifies; the others are dropped and reported."""
        built: list[dict[str, Any]] = []
        for index, draft in enumerate(drafts):
            source = self._verify(draft.source, f"{path}[{index}].source")
            if source is not None:
                built.append(build(draft, source))
        return built

    def _conditions(self, draft: DraftConditions | None) -> dict[str, Any] | None:
        if draft is None:
            return None
        conditions: dict[str, Any] = {
            "flow_direction": list(draft.flow_direction),
            "gravity_g": list(draft.gravity_g),
        }
        for dimension in CONDITION_DIMENSIONS:
            conditions[dimension] = self._range(
                getattr(draft, dimension), f"conditions.{dimension}"
            )
        return conditions

    def _range(self, draft: DraftRange | None, path: str) -> dict[str, Any] | None:
        if draft is None or (draft.min is None and draft.max is None):
            return None
        source = self._verify(draft.source, f"{path}.source")
        return None if source is None else {"min": draft.min, "max": draft.max, "source": source}


def _merge_values(values: Sequence[Any]) -> Any:
    """Reduce step: lists concatenate without duplicates, dicts keep the first value per key."""
    first = values[0]
    if isinstance(first, list):
        return _unique([item for value in values for item in value])
    if isinstance(first, dict):
        merged: dict[Any, Any] = {}
        for value in reversed(values):
            merged.update(value)
        return merged
    return next((value for value in values if value is not None), None)


def _unique(items: Sequence[Any]) -> list[Any]:
    seen: set[str] = set()
    kept: list[Any] = []
    for item in items:
        key = repr(item)
        if key not in seen:
            seen.add(key)
            kept.append(item)
    return kept


def merge_outputs(outputs: Sequence[ExtractorOutput]) -> ExtractorOutput:
    """Deterministic reduce over the per-batch extractor outputs."""
    merged = {
        name: _merge_values([getattr(output, name) for output in outputs])
        for name in ExtractorOutput.model_fields
    }
    return ExtractorOutput.model_validate(merged)


def _keyword_score(heading: str | None, text: str) -> int:
    haystack = f"{heading or ''} {text}".lower()
    return sum(haystack.count(keyword) for keyword in KEYWORDS)


def _overview_first(documents: Sequence[ParsedDoc]) -> list[ParsedDoc]:

    def is_overview(document: ParsedDoc) -> bool:
        return any(hint in document.doc_ref.lower() for hint in OVERVIEW_HINTS)

    return sorted(documents, key=lambda document: not is_overview(document))


def build_context_batches(
    documents: Sequence[ParsedDoc],
) -> tuple[list[list[ExtractorContextItem]], dict[str, ParsedDoc]]:
    """Context batches within the budget: overview text first, then sections by keyword rank."""
    ordered = _overview_first(documents)
    by_id = {f"D{number}": document for number, document in enumerate(ordered, start=1)}
    candidates: list[tuple[int, int, ExtractorContextItem]] = []
    for doc_id, document in by_id.items():
        for section in document.sections:
            item = ExtractorContextItem(
                doc_id=doc_id,
                title=document.title,
                section=section.heading,
                text=section.text[:MAX_SECTION_CHARS],
            )
            rank = 0 if doc_id == "D1" else 1
            candidates.append((rank, -_keyword_score(section.heading, section.text), item))
    candidates.sort(key=lambda entry: entry[:2])
    return _pack([entry[2] for entry in candidates]), by_id


def _pack(items: Sequence[ExtractorContextItem]) -> list[list[ExtractorContextItem]]:
    """Greedy packing; the call cap bounds LLM cost per investigation, so excess context is cut."""
    batches: list[list[ExtractorContextItem]] = []
    used = 0
    for item in items:
        if not batches or used + len(item.text) > CONTEXT_CHAR_BUDGET:
            if len(batches) == MAX_EXTRACT_CALLS:
                break
            batches.append([])
            used = 0
        batches[-1].append(item)
        used += len(item.text)
    return batches


def _file_types(manifest: Manifest) -> list[str]:
    return sorted({item.extension.lstrip(".") for item in manifest.files if item.extension})


class ExtractStage:
    """Runs the extractor per context batch, merges, verifies quotes and applies overrides."""

    def __init__(
        self,
        settings: Settings,
        orchestrator: AgentOrchestrator,
        layout: RawLayout,
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        self._layout = layout

    def extract(self, acronym: str, *, force: bool = False) -> ExtractResult:
        documents = load_parsed_docs(self._layout, acronym)
        if not documents:
            raise IngestError(
                f"No parsed documents for {acronym}; run parse first", {"acronym": acronym}
            )
        input_hash = self._input_hash(documents)
        draft_path = self._layout.draft_path(acronym)
        if not force and draft_path.is_file():
            existing = read_json(draft_path)
            if existing.get(REPORT_KEY, {}).get("input_hash") == input_hash:
                return ExtractResult(card=existing, skipped=True)
        return self._run(acronym, documents, input_hash)

    def _input_hash(self, documents: Sequence[ParsedDoc]) -> str:
        digest = hashlib.sha256(self._orchestrator.prompt_version(EXTRACTOR_AGENT).encode())
        for document in sorted(documents, key=lambda item: item.doc_ref):
            digest.update(f"{document.doc_ref}|{document.source_sha256}\n".encode())
        return digest.hexdigest()

    def _run(self, acronym: str, documents: Sequence[ParsedDoc], input_hash: str) -> ExtractResult:
        manifest = load_manifest(self._layout, acronym)
        batches, by_id = build_context_batches(documents)
        psi_url = f"s3://{self._settings.psi_bucket}/{manifest.prefix}"
        outputs = [self._call(acronym, psi_url, batch) for batch in batches]
        verifier = QuoteVerifier(by_id)
        card = DraftCardBuilder(verifier).build(merge_outputs(outputs))
        card.update(self._base_fields(acronym, psi_url, manifest))
        merged = apply_override(card, self._settings.data_dir, acronym)
        merged.data[REPORT_KEY] = {"input_hash": input_hash, "quote_failures": verifier.failures}
        write_json(self._layout.draft_path(acronym), merged.data)
        return ExtractResult(
            card=merged.data,
            llm_calls=len(outputs),
            quote_failures=verifier.failures,
            overrides=merged,
        )

    def _call(
        self, acronym: str, psi_url: str, batch: list[ExtractorContextItem]
    ) -> ExtractorOutput:
        payload = ExtractorInput(acronym=acronym, title=acronym, psi_url=psi_url, context=batch)
        output = asyncio.run(self._orchestrator.run(EXTRACTOR_AGENT, payload))
        if not isinstance(output, ExtractorOutput):
            raise IngestError("Extractor returned an unexpected output type", {"acronym": acronym})
        return output

    @staticmethod
    def _base_fields(acronym: str, psi_url: str, manifest: Manifest) -> dict[str, Any]:
        return {
            "schema_version": CARD_SCHEMA_VERSION,
            "acronym": acronym,
            "title": acronym,
            "project": None,
            "psi_url": psi_url,
            "data": {
                "s3_prefix": manifest.prefix,
                "volume_bytes": manifest.total_bytes,
                "file_types": _file_types(manifest),
            },
        }
