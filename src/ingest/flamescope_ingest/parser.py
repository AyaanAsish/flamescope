"""Stage 3, parse: raw files to `ParsedDoc` with sections and offsets (document 06 section 3.3)."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import zipfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from functools import partial
from html.parser import HTMLParser
from pathlib import Path

import structlog
from pydantic import BaseModel, Field

from flamescope_common.config import Settings
from flamescope_common.errors import IngestError
from flamescope_ingest.discover import RawLayout, load_manifest, read_json, write_json
from flamescope_ingest.harvester import ETAG_FILE

logger = structlog.get_logger(__name__)

TABLE_ROW_LIMIT = 200
TABLE_TEXT_ROWS = 50
MAX_SHEETS = 3
SECTION_GAP = "\n\n"
UNIT_PATTERN = re.compile(r"\(([^)]+)\)|\[([^\]]+)\]")
TAG_PATTERN = re.compile(r"<[^>]+>")
HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
SKIPPED_TAGS = frozenset({"script", "style", "noscript"})
WORD_PARAGRAPH = re.compile(r"<w:p[ >].*?</w:p>", re.DOTALL)
WORD_TEXT = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.DOTALL)
SLIDE_TEXT = re.compile(r"<a:t[^>]*>(.*?)</a:t>", re.DOTALL)
SLIDE_NAME = re.compile(r"ppt/slides/slide(\d+)\.xml")


class ParsedSection(BaseModel):
    heading: str | None = None
    text: str
    char_start: int
    char_end: int
    page: int | None = None


class ParsedTable(BaseModel):
    caption: str | None = None
    header: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    page: int | None = None
    units: list[str | None] = Field(default_factory=list)


class ParsedDoc(BaseModel):
    doc_ref: str
    title: str
    kind: str
    sections: list[ParsedSection] = Field(default_factory=list)
    tables: list[ParsedTable] = Field(default_factory=list)
    source_sha256: str = ""

    def full_text(self) -> str:
        """Section texts in offset order, the text `char_start` and `char_end` index into."""
        return SECTION_GAP.join(section.text for section in self.sections)


@dataclass
class _Draft:
    """Parser output before offsets are assigned."""

    title: str
    kind: str
    blocks: Sequence[tuple[str | None, str, int | None]] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)


def detect_units(header: Iterable[str]) -> list[str | None]:
    """Unit text found in brackets of each header cell, for example `Pressure (kPa)`."""
    units: list[str | None] = []
    for cell in header:
        match = UNIT_PATTERN.search(cell)
        units.append((match.group(1) or match.group(2)).strip() if match else None)
    return units


def _clean(text: str) -> str:
    return " ".join(html.unescape(text).split())


class _HtmlSections(HTMLParser):
    """Collects the title and heading-delimited text blocks of an HTML page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[tuple[str | None, str]] = []
        self._heading: str | None = None
        self._buffer: list[str] = []
        self._open: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in HEADING_TAGS:
            self._flush()
        self._open.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in HEADING_TAGS:
            self._heading = _clean(" ".join(self._buffer))
            self._buffer = []
        if tag in self._open:
            self._open.remove(tag)

    def handle_data(self, data: str) -> None:
        if SKIPPED_TAGS & set(self._open):
            return
        if "title" in self._open:
            self.title += data
            return
        self._buffer.append(data)

    def _flush(self) -> None:
        text = _clean(" ".join(self._buffer))
        if text:
            self.blocks.append((self._heading, text))
        self._buffer = []

    def close(self) -> None:
        super().close()
        self._flush()


def _parse_html(raw: bytes, name: str) -> _Draft:
    parser = _HtmlSections()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    title = _clean(parser.title) or next((h for h, _ in parser.blocks if h), name)
    return _Draft(title, "html", [(heading, text, None) for heading, text in parser.blocks])


def _parse_text(raw: bytes, name: str) -> _Draft:
    return _Draft(name, "text", [(None, raw.decode("utf-8", errors="replace").strip(), None)])


def _parse_json(raw: bytes, name: str) -> _Draft:
    try:
        text = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
    except ValueError as error:
        raise IngestError(f"Invalid JSON in {name}") from error
    return _Draft(name, "json", [(None, text, None)])


def _parse_xml(raw: bytes, name: str) -> _Draft:
    text = _clean(TAG_PATTERN.sub(" ", raw.decode("utf-8", errors="replace")))
    return _Draft(name, "xml", [(None, text, None)])


def _parse_pdf(raw: bytes, name: str) -> _Draft:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    blocks = [
        (f"Page {number}", (page.extract_text() or "").strip(), number)
        for number, page in enumerate(reader.pages, start=1)
    ]
    title = (reader.metadata.title if reader.metadata else None) or name
    return _Draft(str(title), "pdf", blocks, _pdf_tables(raw))


def _pdf_tables(raw: bytes) -> list[ParsedTable]:
    import pdfplumber

    tables: list[ParsedTable] = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                tables += [
                    _table_from_rows(rows, None, number)
                    for rows in page.extract_tables()
                    if rows and len(rows) > 1
                ]
    except Exception as error:  # pdfplumber raises many unrelated types on odd PDFs
        logger.warning("pdf_tables_failed", error=str(error))
    return tables


def _parse_docx(raw: bytes, name: str) -> _Draft:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    paragraphs = [_clean("".join(WORD_TEXT.findall(p))) for p in WORD_PARAGRAPH.findall(xml)]
    text = "\n".join(p for p in paragraphs if p)
    return _Draft(name, "office", [(None, text, None)])


def _parse_pptx(raw: bytes, name: str) -> _Draft:
    blocks: list[tuple[str | None, str, int | None]] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        slides = sorted(
            (int(m.group(1)), entry)
            for entry in archive.namelist()
            if (m := SLIDE_NAME.fullmatch(entry))
        )
        for number, entry in slides:
            xml = archive.read(entry).decode("utf-8", errors="replace")
            blocks.append((f"Slide {number}", _clean(" ".join(SLIDE_TEXT.findall(xml))), number))
    return _Draft(name, "office", blocks)


def _table_from_rows(
    rows: Sequence[Sequence[object]], caption: str | None, page: int | None
) -> ParsedTable:
    cells = [["" if cell is None else str(cell).strip() for cell in row] for row in rows]
    header = cells[0]
    return ParsedTable(
        caption=caption,
        header=header,
        rows=cells[1 : TABLE_ROW_LIMIT + 1],
        page=page,
        units=detect_units(header),
    )


def _parse_delimited(raw: bytes, name: str, delimiter: str) -> _Draft:
    reader = csv.reader(io.StringIO(raw.decode("utf-8", errors="replace")), delimiter=delimiter)
    rows = [row for _, row in zip(range(TABLE_ROW_LIMIT + 1), reader, strict=False) if row]
    return _table_draft(name, [_table_from_rows(rows, name, None)] if rows else [])


def _parse_xlsx(raw: bytes, name: str) -> _Draft:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    tables = []
    for sheet in workbook.worksheets[:MAX_SHEETS]:
        rows = [
            list(row)
            for _, row in zip(
                range(TABLE_ROW_LIMIT + 1), sheet.iter_rows(values_only=True), strict=False
            )
            if any(cell is not None for cell in row)
        ]
        if rows:
            tables.append(_table_from_rows(rows, f"{name} / {sheet.title}", None))
    return _table_draft(name, tables)


def _table_draft(name: str, tables: list[ParsedTable]) -> _Draft:
    blocks = [(table.caption, _table_text(table), None) for table in tables]
    return _Draft(name, "table", blocks, tables)


def _table_text(table: ParsedTable) -> str:
    lines = [" | ".join(table.header)] + [" | ".join(row) for row in table.rows[:TABLE_TEXT_ROWS]]
    return "\n".join(lines)


PARSERS: dict[str, Callable[[bytes, str], _Draft]] = {
    ".html": _parse_html,
    ".htm": _parse_html,
    ".txt": _parse_text,
    ".md": _parse_text,
    ".json": _parse_json,
    ".xml": _parse_xml,
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".pptx": _parse_pptx,
    ".csv": partial(_parse_delimited, delimiter=","),
    ".tsv": partial(_parse_delimited, delimiter="\t"),
    ".xlsx": _parse_xlsx,
}


def build_parsed_doc(draft: _Draft, doc_ref: str, sha256: str) -> ParsedDoc:
    """Assign section offsets in the order the sections are joined by `full_text`."""
    sections: list[ParsedSection] = []
    offset = 0
    for heading, text, page in draft.blocks:
        if not text:
            continue
        sections.append(
            ParsedSection(
                heading=heading,
                text=text,
                char_start=offset,
                char_end=offset + len(text),
                page=page,
            )
        )
        offset += len(text) + len(SECTION_GAP)
    return ParsedDoc(
        doc_ref=doc_ref,
        title=draft.title,
        kind=draft.kind,
        sections=sections,
        tables=draft.tables,
        source_sha256=sha256,
    )


def parse_bytes(raw: bytes, relative_name: str, doc_ref: str) -> ParsedDoc | None:
    """Parse one file; None when the type has no parser (legacy Office or binary formats)."""
    parser = PARSERS.get(Path(relative_name).suffix.lower())
    if parser is None:
        return None
    draft = parser(raw, Path(relative_name).name)
    return build_parsed_doc(draft, doc_ref, hashlib.sha256(raw).hexdigest())


class ParseResult(BaseModel):
    parsed: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)


def parsed_name(relative: str) -> str:
    return relative.replace("/", "__") + ".json"


@dataclass
class _ParseRun:
    """State of one parse pass over an investigation."""

    acronym: str
    raw_dir: Path
    doc_prefix: str
    force: bool
    result: ParseResult = field(default_factory=ParseResult)


class Parser:
    """Parses every raw file of an investigation into `<raw>/<acronym>/parsed/*.json`."""

    def __init__(self, settings: Settings, layout: RawLayout) -> None:
        self._settings = settings
        self._layout = layout

    def parse(self, acronym: str, *, force: bool = False) -> ParseResult:
        manifest = load_manifest(self._layout, acronym)
        raw_dir = self._layout.raw_dir(acronym)
        run = _ParseRun(
            acronym=acronym,
            raw_dir=raw_dir,
            doc_prefix=f"s3://{self._settings.psi_bucket}/{manifest.prefix}",
            force=force,
        )
        for path in sorted(p for p in raw_dir.rglob("*") if p.is_file() and p.name != ETAG_FILE):
            self._parse_file(run, path)
        return run.result

    def _parse_file(self, run: _ParseRun, path: Path) -> None:
        relative = path.relative_to(run.raw_dir).as_posix()
        target = self._layout.parsed_dir(run.acronym) / parsed_name(relative)
        raw = path.read_bytes()
        sha256 = hashlib.sha256(raw).hexdigest()
        if not run.force and target.is_file() and read_json(target).get("source_sha256") == sha256:
            run.result.unchanged.append(relative)
            return
        try:
            document = parse_bytes(raw, relative, run.doc_prefix + relative)
        except (IngestError, OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
            logger.warning("parse_failed", file=relative, error=str(error))
            run.result.failed.append(relative)
            return
        if document is None:
            run.result.unsupported.append(relative)
            return
        write_json(target, document.model_dump(mode="json"))
        run.result.parsed.append(relative)


def load_parsed_docs(layout: RawLayout, acronym: str) -> list[ParsedDoc]:
    """Every parsed document of an investigation, in file-name order."""
    directory = layout.parsed_dir(acronym)
    if not directory.is_dir():
        return []
    return [ParsedDoc.model_validate(read_json(path)) for path in sorted(directory.glob("*.json"))]
