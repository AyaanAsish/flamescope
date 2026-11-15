"""Visual system of the FlameScope pitch deck: dark tokens, text styles and drawing elements.

Each element is a frozen dataclass that draws itself on a slide. `build_pitch.py` re-exports
these names for the other deck scripts (`deck_style.py`, the demo modules).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.shapes.base import BaseShape
from pptx.slide import Slide
from pptx.util import Inches, Pt

DECK_DIR = Path(__file__).resolve().parent
SCREENS_DIR = DECK_DIR / "screens"

SLIDE_WIDTH_IN, SLIDE_HEIGHT_IN = 13.333, 7.5
MARGIN_IN = 0.6
CONTENT_WIDTH_IN = SLIDE_WIDTH_IN - 2 * MARGIN_IN
RIGHT_EDGE_IN = SLIDE_WIDTH_IN - MARGIN_IN
CONTENT_TOP_IN = 1.65
GAP_IN = 0.3
TITLE_ONLY_LAYOUT = 5

BACKGROUND, SURFACE, SURFACE_RAISED = "0A0E14", "10151D", "161C26"
BORDER, BORDER_STRONG, EDGE = "232B38", "334155", "475569"
TEXT, MUTED, FAINT = "E6EAF0", "94A3B8", "8391A7"
ACCENT, COOL, SUCCESS = "F97316", "38BDF8", "34D399"
VIOLET, ROSE, AMBER = "A78BFA", "FB7185", "FBBF24"
SANS, MONO = "Inter", "JetBrains Mono"

BORDER_WIDTH_PT = 0.75  # 1 px at 96 dpi
EDGE_WIDTH_PT = 1.5
CARD_RADIUS_IN = 0.1
SCREEN_RADIUS_IN = 0.08
ROUNDING_SCALE, MAX_ROUNDING = 100_000, 50_000
EN_DASH = chr(0x2013)  # objective ranges ("O1 to O3"); a literal dash fails RUF001
NBSP = chr(0x00A0)  # no-break space keeps "0 g" and "E-FIELD Flames" on one line


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def right(self) -> float:
        return self.left + self.width


@dataclass(frozen=True)
class TextStyle:
    size: float
    color: str = TEXT
    is_bold: bool = False
    font: str = SANS
    align: PP_ALIGN = PP_ALIGN.LEFT


TITLE_STYLE = TextStyle(26, is_bold=True)
COVER_TITLE_STYLE = TextStyle(54, is_bold=True)
FOOTER_STYLE = TextStyle(10, FAINT)
NUMBER_STYLE = TextStyle(10, FAINT, font=MONO, align=PP_ALIGN.RIGHT)
CAPTION_STYLE = TextStyle(12, FAINT)
POINT_STYLE = TextStyle(16)
LABEL_STYLE = TextStyle(15, is_bold=True)
VALUE_STYLE = TextStyle(12, MUTED, font=MONO)
STAT_LABEL_STYLE = TextStyle(18, MUTED)


def rgb(hex_colour: str) -> RGBColor:
    return RGBColor.from_string(hex_colour)


def blend(foreground: str, background: str, alpha: float) -> str:
    """Solid colour of `foreground` at `alpha` over `background` (keeps shapes opaque)."""
    channels = zip(rgb(foreground), rgb(background), strict=True)
    return "".join(f"{round(fg * alpha + bg * (1 - alpha)):02X}" for fg, bg in channels)


def inches(box: Box) -> tuple[int, int, int, int]:
    return Inches(box.left), Inches(box.top), Inches(box.width), Inches(box.height)


def column_width(count: int) -> float:
    return (CONTENT_WIDTH_IN - (count - 1) * GAP_IN) / count


def column_left(index: int, width: float) -> float:
    return MARGIN_IN + index * (width + GAP_IN)


# --- drawing primitives -------------------------------------------------------------------


def write_paragraph(paragraph: object, text: str, style: TextStyle) -> None:
    paragraph.alignment = style.align  # type: ignore[attr-defined]
    run = paragraph.add_run()  # type: ignore[attr-defined]
    run.text = text
    run.font.size = Pt(style.size)
    run.font.bold = style.is_bold
    run.font.name = style.font
    run.font.color.rgb = rgb(style.color)


def fill_text_frame(shape: BaseShape, text: str, style: TextStyle) -> None:
    frame = shape.text_frame  # type: ignore[attr-defined]
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.TOP
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    first, *rest = text.split("\n")
    write_paragraph(frame.paragraphs[0], first, style)
    for line in rest:
        write_paragraph(frame.add_paragraph(), line, style)


def set_corner_radius(shape: BaseShape, radius_in: float) -> None:
    geometry = shape._element.spPr.find(qn("a:prstGeom"))
    av_list = geometry.find(qn("a:avLst"))
    if av_list is None:
        av_list = etree.SubElement(geometry, qn("a:avLst"))
    av_list.clear()
    shorter_side = min(shape.width, shape.height)
    adjust = min(MAX_ROUNDING, round(Inches(radius_in) / shorter_side * ROUNDING_SCALE))
    etree.SubElement(av_list, qn("a:gd"), name="adj", fmla=f"val {adjust}")


def set_outline(shape: BaseShape, colour: str, width_pt: float = BORDER_WIDTH_PT) -> None:
    shape.line.color.rgb = rgb(colour)  # type: ignore[attr-defined]
    shape.line.width = Pt(width_pt)  # type: ignore[attr-defined]


def add_filled_shape(slide: Slide, box: Box, fill: str, kind: MSO_SHAPE) -> BaseShape:
    shape = slide.shapes.add_shape(kind, *inches(box))
    shape.shadow.inherit = False
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.fill.background()
    return shape


# --- slide elements -----------------------------------------------------------------------


class Element(Protocol):
    def draw(self, slide: Slide) -> None: ...


@dataclass(frozen=True)
class Text:
    box: Box
    content: str
    style: TextStyle = POINT_STYLE
    name: str = "body"

    def draw(self, slide: Slide) -> None:
        shape = slide.shapes.add_textbox(*inches(self.box))
        shape.name = self.name
        fill_text_frame(shape, self.content, self.style)


@dataclass(frozen=True)
class Card:
    """Rounded surface panel with a hairline border."""

    box: Box
    fill: str = SURFACE

    def draw(self, slide: Slide) -> None:
        shape = add_filled_shape(slide, self.box, self.fill, MSO_SHAPE.ROUNDED_RECTANGLE)
        shape.name = "card"
        set_outline(shape, BORDER)
        set_corner_radius(shape, CARD_RADIUS_IN)


@dataclass(frozen=True)
class Mark:
    """Flat colour shape: accent strips, plot markers, the habitat envelope."""

    box: Box
    fill: str
    kind: MSO_SHAPE = MSO_SHAPE.RECTANGLE
    border: str | None = None

    def draw(self, slide: Slide) -> None:
        shape = add_filled_shape(slide, self.box, self.fill, self.kind)
        shape.name = "mark"
        if self.border:
            set_outline(shape, self.border, EDGE_WIDTH_PT)


@dataclass(frozen=True)
class Line:
    start: tuple[float, float]
    end: tuple[float, float]
    colour: str = EDGE
    has_head: bool = False
    is_dashed: bool = False
    name: str = "line"

    def draw(self, slide: Slide) -> None:
        (x1, y1), (x2, y2) = self.start, self.end
        connector = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
        )
        connector.name = self.name
        set_outline(connector, self.colour, EDGE_WIDTH_PT)
        if self.is_dashed:
            connector.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if self.has_head:
            line_properties = connector.line._get_or_add_ln()
            etree.SubElement(line_properties, qn("a:tailEnd"), type="triangle")


@dataclass(frozen=True)
class Screenshot:
    """A pixel crop (left, top, right, bottom) of a capture in `screens/`, placed at a width."""

    name: str
    crop: tuple[int, int, int, int]
    left: float = 0.0
    top: float = 0.0
    width: float = 1.0

    @property
    def path(self) -> Path:
        return SCREENS_DIR / f"{self.name}.png"

    @property
    def aspect(self) -> float:
        left, top, right, bottom = self.crop
        return (right - left) / (bottom - top)

    @property
    def height(self) -> float:
        return self.width / self.aspect

    def placed(self, left: float, top: float, width: float) -> Screenshot:
        return Screenshot(self.name, self.crop, left, top, width)

    def draw(self, slide: Slide) -> None:
        picture = slide.shapes.add_picture(str(self.path), Inches(self.left), Inches(self.top))
        picture.name = f"screen-{self.name}"
        pixel_width, pixel_height = picture.image.size
        crop_left, crop_top, crop_right, crop_bottom = self.crop
        picture.crop_left = crop_left / pixel_width
        picture.crop_top = crop_top / pixel_height
        picture.crop_right = 1 - crop_right / pixel_width
        picture.crop_bottom = 1 - crop_bottom / pixel_height
        picture.width, picture.height = Inches(self.width), Inches(self.height)
        picture.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
        set_corner_radius(picture, SCREEN_RADIUS_IN)
        set_outline(picture, BORDER)


@dataclass(frozen=True)
class Step:
    """One build phase drawn as a chevron with its label inside."""

    box: Box
    label: str
    outline: str = BORDER_STRONG

    def draw(self, slide: Slide) -> None:
        shape = add_filled_shape(slide, self.box, SURFACE_RAISED, MSO_SHAPE.CHEVRON)
        shape.name = "step"
        set_outline(shape, self.outline)
        fill_text_frame(shape, self.label, TextStyle(12, is_bold=True, align=PP_ALIGN.CENTER))
        shape.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE  # type: ignore[attr-defined]


Elements = tuple[Element, ...]


def accent_card(box: Box, accent: str, fill: str = SURFACE) -> Elements:
    """Card with a short vertical accent strip on its left edge."""
    strip = Box(box.left, box.top + 0.14, 0.06, box.height - 0.28)
    return Card(box, fill), Mark(strip, accent)
