"""FR-01: stage 3, parse (document 06 section 3.3) on small generated fixtures.

`ParsedDoc {doc_ref, title, kind, sections:[{heading, text, char_start, char_end, page}],
tables:[{caption, header, rows, page, units}]}`; tabular files keep the header plus up to 200
rows with units detected from header names; the stage is keyed by the SHA-256 of the raw file.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from openpyxl import Workbook

from flamescope_common.config import Settings
from flamescope_common.errors import IngestError
from flamescope_ingest.discover import Manifest, RawLayout, write_json
from flamescope_ingest.parser import (
    ParsedDoc,
    ParsedSection,
    ParsedTable,
    Parser,
    detect_units,
    load_parsed_docs,
    parse_bytes,
)

pytestmark = pytest.mark.unit

DOC_REF = "s3://nasa-psi/combustion/TEST-1/file"
TABLE_ROW_LIMIT = 200
PDF_TEXT = "Synthetic oxygen test page"
HTML_PAGE = b"""<html><head><title>Synthetic Overview</title>
<style>body { color: red; }</style><script>var hidden = 1;</script></head>
<body><p>Intro text.</p>
<h2>Objective</h2><p>Study a synthetic flame.</p>
<h2>Test matrix</h2><p>Three points &amp; one fuel.</p>
</body></html>"""


def _minimal_pdf(text: str) -> bytes:
    """A one-page PDF with one Helvetica text line and a correct cross-reference table."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n".encode() + content + b"\nendobj\n"
    xref_at = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    return body + f"startxref\n{xref_at}\n%%EOF\n".encode()


def _csv(rows: int, delimiter: str = ",") -> bytes:
    header = delimiter.join(["Run", "Pressure (kPa)", "O2 [%]", "Fuel"])
    lines = [header] + [delimiter.join([f"R{i}", "50", "30", "PMMA"]) for i in range(rows)]
    return "\n".join(lines).encode()


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")
    return buffer.getvalue()


def _xlsx(rows: int) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Matrix"
    sheet.append(["Run", "Flow (cm/s)"])
    for index in range(rows):
        sheet.append([f"R{index}", index])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _assert_offsets_index_full_text(document: ParsedDoc) -> None:
    full_text = document.full_text()
    for section in document.sections:
        assert full_text[section.char_start : section.char_end] == section.text


def test_parsed_doc_shape_matches_document_06() -> None:
    """Field names of `ParsedDoc`, its sections and tables (document 06 section 3.3)."""
    assert {"doc_ref", "title", "kind", "sections", "tables"} <= set(ParsedDoc.model_fields)
    assert {"heading", "text", "char_start", "char_end", "page"} <= set(ParsedSection.model_fields)
    assert {"caption", "header", "rows", "page", "units"} <= set(ParsedTable.model_fields)


def test_html_sections_follow_headings() -> None:
    document = parse_bytes(HTML_PAGE, "overview.html", DOC_REF)
    assert document is not None
    assert document.title == "Synthetic Overview"
    assert document.kind == "html"
    assert document.doc_ref == DOC_REF
    assert [(s.heading, s.text) for s in document.sections] == [
        (None, "Intro text."),
        ("Objective", "Study a synthetic flame."),
        ("Test matrix", "Three points & one fuel."),
    ]
    _assert_offsets_index_full_text(document)


def test_html_skips_script_and_style() -> None:
    document = parse_bytes(HTML_PAGE, "overview.htm", DOC_REF)
    assert document is not None
    assert "hidden" not in document.full_text()
    assert "color" not in document.full_text()


def test_pdf_text_by_page() -> None:
    """PDFs: pypdf for text, one section per page with its page number."""
    document = parse_bytes(_minimal_pdf(PDF_TEXT), "report.pdf", DOC_REF)
    assert document is not None
    assert document.kind == "pdf"
    assert len(document.sections) == 1
    assert PDF_TEXT in document.sections[0].text
    assert document.sections[0].page == 1
    assert document.tables == []
    _assert_offsets_index_full_text(document)


def test_csv_header_rows_and_units() -> None:
    """Tabular files: header plus rows, units detected from header names, one per column."""
    document = parse_bytes(_csv(3), "summary.csv", DOC_REF)
    assert document is not None
    table = document.tables[0]
    assert table.header == ["Run", "Pressure (kPa)", "O2 [%]", "Fuel"]
    assert table.rows[0] == ["R0", "50", "30", "PMMA"]
    assert len(table.rows) == 3
    assert table.units == [None, "kPa", "%", None]
    assert document.sections, "table text is indexed as a section"


def test_csv_keeps_at_most_200_rows() -> None:
    document = parse_bytes(_csv(TABLE_ROW_LIMIT + 50), "matrix.csv", DOC_REF)
    assert document is not None
    assert len(document.tables[0].rows) == TABLE_ROW_LIMIT


def test_tsv_is_tabular() -> None:
    document = parse_bytes(_csv(2, delimiter="\t"), "matrix.tsv", DOC_REF)
    assert document is not None
    assert document.tables[0].header[1] == "Pressure (kPa)"


def test_xlsx_sheet_becomes_a_table() -> None:
    """XLSX tables through openpyxl (document 02 section 3)."""
    document = parse_bytes(_xlsx(TABLE_ROW_LIMIT + 5), "tests.xlsx", DOC_REF)
    assert document is not None
    table = document.tables[0]
    assert table.header == ["Run", "Flow (cm/s)"]
    assert table.units == [None, "cm/s"]
    assert len(table.rows) == TABLE_ROW_LIMIT


def test_docx_is_text_only() -> None:
    """Office files: text only."""
    document = parse_bytes(_docx(["First paragraph.", "Second paragraph."]), "a.docx", DOC_REF)
    assert document is not None
    assert document.tables == []
    assert document.full_text() == "First paragraph.\nSecond paragraph."


def test_json_and_text_files() -> None:
    assert parse_bytes(b'{"a": 1}', "meta.json", DOC_REF) is not None
    text_doc = parse_bytes(b"  plain text  ", "notes.txt", DOC_REF)
    assert text_doc is not None
    assert text_doc.full_text() == "plain text"


def test_invalid_json_raises_ingest_error() -> None:
    with pytest.raises(IngestError):
        parse_bytes(b"{not json", "broken.json", DOC_REF)


def test_unparseable_type_returns_none() -> None:
    assert parse_bytes(b"\x00\x01", "clip.mp4", DOC_REF) is None


@pytest.mark.parametrize(
    ("header", "units"),
    [
        (["Pressure (kPa)"], ["kPa"]),
        (["Flow [cm/s]"], ["cm/s"]),
        (["Label"], [None]),
        (["O2 ( % )", "T"], ["%", None]),
    ],
)
def test_detect_units_from_header_names(header: list[str], units: list[str | None]) -> None:
    assert detect_units(header) == units


def _prepare_raw(layout: RawLayout, files: dict[str, bytes]) -> None:
    manifest = Manifest(acronym="TEST-1", prefix="combustion/TEST-1/", listing_hash="x")
    write_json(layout.manifest_path("TEST-1"), manifest.model_dump(mode="json"))
    for name, content in files.items():
        target = layout.raw_dir("TEST-1") / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def test_parser_writes_parsed_json_and_is_idempotent(ingest_settings: Settings) -> None:
    """Artifact `/data/raw/<acr>/parsed/<doc>.json`; key SHA-256 of the raw file (doc 06 s2)."""
    layout = RawLayout(ingest_settings.raw_dir)
    _prepare_raw(layout, {"overview.html": HTML_PAGE, "clip.mp4": b"\x00"})
    parser = Parser(ingest_settings, layout)

    first = parser.parse("TEST-1")
    assert first.parsed == ["overview.html"]
    assert first.unsupported == ["clip.mp4"]
    stored = json.loads(next(layout.parsed_dir("TEST-1").glob("*.json")).read_text())
    assert stored["source_sha256"] == hashlib.sha256(HTML_PAGE).hexdigest()
    assert stored["doc_ref"] == "s3://nasa-psi/combustion/TEST-1/overview.html"

    assert parser.parse("TEST-1").unchanged == ["overview.html"]
    assert parser.parse("TEST-1", force=True).parsed == ["overview.html"]
    assert [doc.title for doc in load_parsed_docs(layout, "TEST-1")] == ["Synthetic Overview"]


def test_parser_reparses_changed_file(ingest_settings: Settings) -> None:
    layout = RawLayout(ingest_settings.raw_dir)
    _prepare_raw(layout, {"notes.txt": b"first"})
    parser = Parser(ingest_settings, layout)
    parser.parse("TEST-1")
    (layout.raw_dir("TEST-1") / "notes.txt").write_bytes(b"second")
    assert parser.parse("TEST-1").parsed == ["notes.txt"]


def test_parser_records_failures_and_continues(ingest_settings: Settings) -> None:
    layout = RawLayout(ingest_settings.raw_dir)
    _prepare_raw(layout, {"bad.json": b"{", "good.txt": b"ok"})
    result = Parser(ingest_settings, layout).parse("TEST-1")
    assert result.failed == ["bad.json"]
    assert result.parsed == ["good.txt"]
