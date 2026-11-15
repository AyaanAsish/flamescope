"""Shared visual system for the FlameScope demo deck.

Re-exports the pitch deck's dark tokens and drawing elements (read-only import from
`build_pitch.py`) and adds the elements the detailed demo deck needs: multi-style text blocks,
numbered callouts over screenshots, native tables, diagram nodes and pills.
"""

from __future__ import annotations

from dataclasses import dataclass

from build_pitch import (
    ACCENT,
    AMBER,
    BACKGROUND,
    BORDER,
    BORDER_STRONG,
    BORDER_WIDTH_PT,
    CONTENT_WIDTH_IN,
    COOL,
    EDGE,
    FAINT,
    GAP_IN,
    MARGIN_IN,
    MONO,
    MUTED,
    NBSP,
    RIGHT_EDGE_IN,
    ROSE,
    SLIDE_HEIGHT_IN,
    SLIDE_WIDTH_IN,
    SUCCESS,
    SURFACE,
    SURFACE_RAISED,
    TEXT,
    TITLE_ONLY_LAYOUT,
    TITLE_STYLE,
    VIOLET,
    Box,
    Card,
    Line,
    Mark,
    Screenshot,
    Text,
    TextStyle,
    add_filled_shape,
    fill_text_frame,
    inches,
    rgb,
    set_corner_radius,
    set_outline,
    write_paragraph,
)
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.slide import Slide
from pptx.util import Inches

__all__ = [
    "ACCENT",
    "AMBER",
    "BACKGROUND",
    "BORDER",
    "BORDER_STRONG",
    "CONTENT_WIDTH_IN",
    "COOL",
    "EDGE",
    "FAINT",
    "GAP_IN",
    "MARGIN_IN",
    "MONO",
    "MUTED",
    "NBSP",
    "RIGHT_EDGE_IN",
    "ROSE",
    "SLIDE_HEIGHT_IN",
    "SLIDE_WIDTH_IN",
    "SUCCESS",
    "SURFACE",
    "SURFACE_RAISED",
    "TEXT",
    "TITLE_ONLY_LAYOUT",
    "TITLE_STYLE",
    "VIOLET",
    "Box",
    "Callout",
    "Card",
    "Line",
    "Mark",
    "Node",
    "Paragraphs",
    "Pill",
    "Screenshot",
    "Table",
    "Text",
    "TextStyle",
    "fill_text_frame",
    "rgb",
]

CONTENT_TOP_IN = 1.5
CONTENT_BOTTOM_IN = 6.7
DANGER = "F87171"

BODY = TextStyle(14)
BODY_MUTED = TextStyle(14, MUTED)
BODY_BOLD = TextStyle(14, is_bold=True)
HEADING = TextStyle(16, is_bold=True)
KICKER = TextStyle(12, ACCENT, is_bold=True, font=MONO)
LABEL = TextStyle(14, ACCENT, is_bold=True)
CODE = TextStyle(13, COOL, font=MONO)
SMALL_MUTED = TextStyle(12, MUTED)

CALLOUT_DIAMETER_IN = 0.34
CALLOUT_STYLE = TextStyle(12, BACKGROUND, is_bold=True, font=MONO, align=PP_ALIGN.CENTER)
PILL_RADIUS_IN = 0.08
NODE_STRIP_IN = 0.06
CELL_MARGIN_IN = 0.06
# PowerPoint's built-in "No Style, No Grid": cell fills alone separate the rows on dark slides.
PLAIN_TABLE_STYLE_ID = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"


@dataclass(frozen=True)
class Paragraphs:
    """One text box whose paragraphs each carry their own style (label, body, code)."""

    box: Box
    lines: tuple[tuple[str, TextStyle], ...]
    name: str = "body"

    def draw(self, slide: Slide) -> None:
        shape = slide.shapes.add_textbox(*inches(self.box))
        shape.name = self.name
        (first_text, first_style), *rest = self.lines
        fill_text_frame(shape, first_text, first_style)
        frame = shape.text_frame
        for text, style in rest:
            write_paragraph(frame.add_paragraph(), text, style)


@dataclass(frozen=True)
class Callout:
    """Numbered accent disc drawn over a screenshot at a point given in inches."""

    number: int
    centre: tuple[float, float]

    def draw(self, slide: Slide) -> None:
        x, y = self.centre
        radius = CALLOUT_DIAMETER_IN / 2
        box = Box(x - radius, y - radius, CALLOUT_DIAMETER_IN, CALLOUT_DIAMETER_IN)
        shape = add_filled_shape(slide, box, ACCENT, MSO_SHAPE.OVAL)
        shape.name = "callout"
        set_outline(shape, BACKGROUND, BORDER_WIDTH_PT * 2)
        frame = shape.text_frame
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        write_paragraph(frame.paragraphs[0], str(self.number), CALLOUT_STYLE)


@dataclass(frozen=True)
class Pill:
    """Small rounded label, for chips such as route names or test IDs."""

    box: Box
    text: str
    colour: str = ACCENT
    size: float = 12

    def draw(self, slide: Slide) -> None:
        shape = add_filled_shape(slide, self.box, SURFACE_RAISED, MSO_SHAPE.ROUNDED_RECTANGLE)
        shape.name = "pill"
        set_outline(shape, self.colour)
        set_corner_radius(shape, PILL_RADIUS_IN)
        frame = shape.text_frame
        frame.margin_left = frame.margin_right = Inches(CELL_MARGIN_IN)
        frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        frame.word_wrap = True
        style = TextStyle(self.size, self.colour, is_bold=True, font=MONO, align=PP_ALIGN.CENTER)
        write_paragraph(frame.paragraphs[0], self.text, style)


@dataclass(frozen=True)
class Node:
    """Diagram node: card with a coloured strip, a title and an optional mono subtitle."""

    box: Box
    title: str
    subtitle: str = ""
    accent: str = ACCENT
    title_size: float = 14

    def draw(self, slide: Slide) -> None:
        Card(self.box).draw(slide)
        strip = Box(self.box.left, self.box.top + 0.1, NODE_STRIP_IN, self.box.height - 0.2)
        Mark(strip, self.accent).draw(slide)
        lines: list[tuple[str, TextStyle]] = [(self.title, TextStyle(self.title_size, TEXT, True))]
        if self.subtitle:
            lines.append((self.subtitle, TextStyle(12, MUTED, font=MONO)))
        inner = Box(
            self.box.left + 0.16,
            self.box.top + 0.08,
            self.box.width - 0.22,
            self.box.height - 0.12,
        )
        Paragraphs(inner, tuple(lines), name="node").draw(slide)


def row_fill(row_index: int) -> str:
    """Header on the hairline colour, then body rows alternating between the two surfaces."""
    if row_index == 0:
        return BORDER
    return SURFACE if row_index % 2 else SURFACE_RAISED


@dataclass(frozen=True)
class Table:
    """Native table on the dark surfaces; the first row is the header."""

    box: Box
    rows: tuple[tuple[str, ...], ...]
    column_widths: tuple[float, ...]
    size: float = 14
    row_height: float = 0.36

    def draw(self, slide: Slide) -> None:
        row_count, column_count = len(self.rows), len(self.column_widths)
        height = Inches(self.row_height * row_count)
        left, top, width, _ = inches(self.box)
        graphic = slide.shapes.add_table(row_count, column_count, left, top, width, height)
        graphic.name = "table"
        table = graphic.table
        table._tbl.tblPr.find(qn("a:tableStyleId")).text = PLAIN_TABLE_STYLE_ID
        for index, column_width in enumerate(self.column_widths):
            table.columns[index].width = Inches(column_width)
        for row_index, row in enumerate(self.rows):
            table.rows[row_index].height = Inches(self.row_height)
            for column_index, text in enumerate(row):
                self._fill_cell(table.cell(row_index, column_index), text, row_index)

    def _fill_cell(self, cell: object, text: str, row_index: int) -> None:
        is_header = row_index == 0
        cell.fill.solid()  # type: ignore[attr-defined]
        cell.fill.fore_color.rgb = rgb(row_fill(row_index))  # type: ignore[attr-defined]
        cell.margin_left = cell.margin_right = Inches(CELL_MARGIN_IN * 2)  # type: ignore[attr-defined]
        cell.margin_top = cell.margin_bottom = Inches(CELL_MARGIN_IN)  # type: ignore[attr-defined]
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE  # type: ignore[attr-defined]
        style = TextStyle(self.size, MUTED if is_header else TEXT, is_bold=is_header)
        frame = cell.text_frame  # type: ignore[attr-defined]
        frame.clear()
        frame.word_wrap = True
        write_paragraph(frame.paragraphs[0], text, style)
