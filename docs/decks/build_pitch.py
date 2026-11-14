"""Build the FlameScope judges' pitch deck (`flamescope-pitch.pptx`), then verify it.

Seven slides, the Space Apps limit for Global Award eligibility. Each slide is a headline plus
a tuple of elements that draw themselves; speaker notes are read from `flamescope-pitch.md`;
screenshots are real captures in `screens/`.
Run from the repository root: `.venv/bin/python docs/decks/build_pitch.py`.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.presentation import Presentation as PresentationType
from pptx.shapes.base import BaseShape
from pptx.slide import Slide
from pptx.util import Inches, Pt
from verify_pitch import main as verify

DECK_DIR = Path(__file__).resolve().parent
SCREENS_DIR = DECK_DIR / "screens"
OUTLINE_PATH = DECK_DIR / "flamescope-pitch.md"
DECK_PATH = DECK_DIR / "flamescope-pitch.pptx"

SLIDE_WIDTH_IN, SLIDE_HEIGHT_IN = 13.333, 7.5
MARGIN_IN = 0.6
CONTENT_WIDTH_IN = SLIDE_WIDTH_IN - 2 * MARGIN_IN
RIGHT_EDGE_IN = SLIDE_WIDTH_IN - MARGIN_IN
CONTENT_TOP_IN = 1.65
GAP_IN = 0.3
TITLE_ONLY_LAYOUT = 5
SLIDE_COUNT = 7
FOOTER_TEXT = "FlameScope - NASA Space Apps 2026 - Flame in Freefall"
AUTHOR = "{{TEAM_NAME}}"
# New files inherit template dates; pin them so the metadata does not change between rebuilds.
BUILD_TIMESTAMP = datetime(2026, 11, 14, tzinfo=UTC)

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
ENVELOPE_FILL_ALPHA = 0.16
ROUNDING_SCALE, MAX_ROUNDING = 100_000, 50_000
EN_DASH = chr(0x2013)  # objective ranges ("O1 to O3"); a literal dash fails RUF001
NBSP = chr(0x00A0)  # no-break space keeps "0 g" and "E-FIELD Flames" on one line
NOTES_BLOCK = re.compile(r"### Speaker notes\n(.*?)(?=\n## |\Z)", re.DOTALL)
SLIDE_HEADING = re.compile(r"^## Slide \d+ - ", re.MULTILINE)


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float

    @property
    def bottom(self) -> float:
        return self.top + self.height


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


Elements = tuple[Element, ...]

# --- slide 1: title -----------------------------------------------------------------------

CHALLENGE = "NASA Space Apps 2026 - Flame in Freefall"
ONE_IDEA = (
    "FlameScope turns 12 TB of microgravity combustion data into ranked, cited "
    "fire-safety answers for the lunar habitat era."
)
OVERVIEW_HERO = Screenshot("overview", (248, 64, 1432, 333)).placed(2.2, 4.45, 8.93)


def title_slide() -> Elements:
    return (
        Text(Box(MARGIN_IN, 0.7, 5.0, 0.35), CHALLENGE, TextStyle(13, ACCENT, is_bold=True)),
        Text(Box(MARGIN_IN, 2.3, 10.0, 1.0), ONE_IDEA, TextStyle(22, MUTED)),
        Text(Box(MARGIN_IN, 3.45, 6.0, 0.35), "{{TEAM_NAME}}", TextStyle(16, is_bold=True)),
        Text(Box(MARGIN_IN, 3.85, 6.0, 0.35), "{{MEMBERS}}", TextStyle(14, MUTED)),
        OVERVIEW_HERO,
    )


# --- slide 2: stakes and problem (oxygen versus pressure plane) ---------------------------

PLOT_LEFT, PLOT_BOTTOM, PLOT_WIDTH, PLOT_HEIGHT = 1.5, 6.0, 6.0, 3.9
PSI_AXIS_MAX, OXYGEN_AXIS_MAX = 16.0, 110.0
MARKER_IN = 0.18
EARTH = (14.7, 21)  # psi, % O2: doc 01 s6 and the iss_cabin preset of doc 08 s4.1
SPACESUIT = (4.3, 100)  # doc 01 s6
HABITAT_MAX_PSI, HABITAT_MIN_OXYGEN, FULL_OXYGEN = 10.2, 30, 100  # doc 01 s6


def plot_point(pressure_psi: float, oxygen_percent: float) -> tuple[float, float]:
    x = PLOT_LEFT + pressure_psi / PSI_AXIS_MAX * PLOT_WIDTH
    y = PLOT_BOTTOM - oxygen_percent / OXYGEN_AXIS_MAX * PLOT_HEIGHT
    return x, y


def marker(point: tuple[float, float], colour: str) -> Mark:
    x, y = plot_point(*point)
    half = MARKER_IN / 2
    return Mark(Box(x - half, y - half, MARKER_IN, MARKER_IN), colour, MSO_SHAPE.OVAL)


def habitat_envelope() -> Elements:
    left, top = plot_point(0, FULL_OXYGEN)
    right, bottom = plot_point(HABITAT_MAX_PSI, HABITAT_MIN_OXYGEN)
    fill = blend(ACCENT, SURFACE, ENVELOPE_FILL_ALPHA)
    values = f"≥30% O2 · ≤10.2{NBSP}psi"
    return (
        Mark(Box(left, top, right - left, bottom - top), fill, border=ACCENT),
        Text(Box(left + 0.15, bottom - 0.68, 3.6, 0.3), "Lunar habitat", LABEL_STYLE),
        Text(Box(left + 0.15, bottom - 0.38, 3.6, 0.3), values, TextStyle(12, ACCENT, font=MONO)),
    )


def plane_axes() -> Elements:
    origin = (PLOT_LEFT, PLOT_BOTTOM)
    axis_style = TextStyle(12, FAINT, align=PP_ALIGN.RIGHT)
    return (
        Line(origin, (PLOT_LEFT + PLOT_WIDTH, PLOT_BOTTOM), BORDER_STRONG),
        Line(origin, (PLOT_LEFT, PLOT_BOTTOM - PLOT_HEIGHT), BORDER_STRONG),
        Text(Box(PLOT_LEFT + 3.0, 6.12, 3.0, 0.3), "Pressure (psi)", axis_style),
        Text(Box(0.85, 1.8, 2.0, 0.3), "Oxygen (%)", CAPTION_STYLE),
    )


def plane_points() -> Elements:
    suit_x, suit_y = plot_point(*SPACESUIT)
    earth_x, earth_y = plot_point(*EARTH)
    right_label = TextStyle(15, is_bold=True, align=PP_ALIGN.RIGHT)
    right_value = TextStyle(12, MUTED, font=MONO, align=PP_ALIGN.RIGHT)
    return (
        marker(SPACESUIT, TEXT),
        marker(EARTH, COOL),
        Text(Box(suit_x + 0.2, suit_y - 0.1, 2.4, 0.3), "Spacesuit", LABEL_STYLE),
        Text(Box(suit_x + 0.2, suit_y + 0.2, 2.4, 0.3), f"100% · 4.3{NBSP}psi", VALUE_STYLE),
        Text(Box(earth_x - 2.6, earth_y - 0.75, 2.5, 0.3), "Earth", right_label),
        Text(Box(earth_x - 2.6, earth_y - 0.45, 2.5, 0.3), f"21% · 14.7{NBSP}psi", right_value),
    )


def problem_stats() -> Elements:
    left, width = 8.5, 4.23
    return (
        Text(Box(left, 1.7, width, 1.05), "24", TextStyle(60, ACCENT, font=MONO)),
        Text(Box(left, 2.8, width, 0.4), "investigations", STAT_LABEL_STYLE),
        Text(Box(left, 3.45, width, 1.05), "~12 TB", TextStyle(60, COOL, font=MONO)),
        Text(Box(left, 4.55, width, 0.4), "of data", STAT_LABEL_STYLE),
        Text(
            Box(left, 5.4, width, 0.9), "Hard to find what matters.", TextStyle(22, is_bold=True)
        ),
    )


def stakes_slide() -> Elements:
    panel = Card(Box(MARGIN_IN, CONTENT_TOP_IN, 7.4, 5.0))
    return (panel, *habitat_envelope(), *plane_axes(), *plane_points(), *problem_stats())


# --- slide 3: our answer ------------------------------------------------------------------


@dataclass(frozen=True)
class AnswerColumn:
    objective: str
    verb: str
    outcome: str
    views: str
    accent: str


ANSWER_COLUMNS = (
    AnswerColumn(
        "O1", "Rank", "Identify relevant investigations", "Ranking · Scenario Lab", ACCENT
    ),
    AnswerColumn("O2", "Summarize", "Extract model-ready data", "Data Extract", COOL),
    AnswerColumn("O3", "Interpret", "Inform controls and equipment", "Safety Tech · Ask", SUCCESS),
)
ANSWER_TOP_IN, ANSWER_HEIGHT_IN = 1.75, 3.55


def column_left(index: int, width: float) -> float:
    return MARGIN_IN + index * (width + GAP_IN)


def column_width(count: int) -> float:
    return (CONTENT_WIDTH_IN - (count - 1) * GAP_IN) / count


def answer_column(column: AnswerColumn, box: Box) -> Elements:
    inner, width = box.left + 0.25, box.width - 0.5
    objective_style = TextStyle(14, column.accent, is_bold=True, font=MONO)
    return (
        Card(box),
        Mark(Box(inner, box.top + 0.3, 0.6, 0.06), column.accent),
        Text(Box(inner, box.top + 0.55, width, 0.4), column.objective, objective_style),
        Text(Box(inner, box.top + 0.95, width, 0.6), column.verb, TextStyle(30, is_bold=True)),
        Text(Box(inner, box.top + 1.7, width, 0.9), column.outcome, TextStyle(20)),
        Text(Box(inner, box.bottom - 0.65, width, 0.35), column.views, TextStyle(14, MUTED)),
    )


def earth_band() -> Elements:
    return (
        Card(Box(MARGIN_IN, 5.55, CONTENT_WIDTH_IN, 1.0), SURFACE_RAISED),
        Text(Box(0.85, 5.85, 0.8, 0.4), "O4", TextStyle(16, VIOLET, is_bold=True, font=MONO)),
        Text(Box(1.6, 5.8, 4.0, 0.45), "Earth add-on", TextStyle(20, is_bold=True)),
        Text(Box(8.2, 5.85, 4.25, 0.4), "Earth Apps", TextStyle(16, MUTED, align=PP_ALIGN.RIGHT)),
    )


def answer_slide() -> Elements:
    width = column_width(len(ANSWER_COLUMNS))
    boxes = [
        Box(column_left(index, width), ANSWER_TOP_IN, width, ANSWER_HEIGHT_IN)
        for index in range(len(ANSWER_COLUMNS))
    ]
    columns = itertools.starmap(answer_column, zip(ANSWER_COLUMNS, boxes, strict=True))
    return (*itertools.chain.from_iterable(columns), *earth_band())


# --- slide 4: O1 ranking and scenario -----------------------------------------------------

SHOT_HEIGHT_IN = 3.55
RANKING_VIEW = Screenshot("ranking", (0, 0, 1440, 900))
SCENARIO_VIEW = Screenshot("scenario", (648, 232, 1416, 900))
RANKING_TEXTS = (
    "Ranking · lunar_habitat preset",
    "Every score opens its evidence; weights re-rank without AI.",
)
SCENARIO_TEXTS = (
    "Scenario Lab · lunar preset",
    f"Partial gravity bounded by 0{NBSP}g and 1{NBSP}g; analogue E-FIELD{NBSP}Flames.",
)


def captioned_shot(shot: Screenshot, texts: tuple[str, str]) -> Elements:
    caption, point = texts
    below = shot.top + shot.height
    return (
        shot,
        Text(Box(shot.left, below + 0.15, shot.width, 0.3), caption, CAPTION_STYLE),
        Text(Box(shot.left, below + 0.5, shot.width, 0.8), point, POINT_STYLE),
    )


def relevance_slide() -> Elements:
    ranking_width = SHOT_HEIGHT_IN * RANKING_VIEW.aspect
    scenario_width = SHOT_HEIGHT_IN * SCENARIO_VIEW.aspect
    left = MARGIN_IN + (CONTENT_WIDTH_IN - ranking_width - GAP_IN - scenario_width) / 2
    ranking = RANKING_VIEW.placed(left, CONTENT_TOP_IN, ranking_width)
    scenario = SCENARIO_VIEW.placed(left + ranking_width + GAP_IN, CONTENT_TOP_IN, scenario_width)
    return (*captioned_shot(ranking, RANKING_TEXTS), *captioned_shot(scenario, SCENARIO_TEXTS))


# --- slide 5: O2, O3 and Ask --------------------------------------------------------------

RECEIPT_LABEL_TOP_IN, RECEIPT_SHOT_TOP_IN = 2.0, 2.45


@dataclass(frozen=True)
class Receipt:
    label: str
    shot: Screenshot
    point: str


RECEIPTS = (
    Receipt(
        "O2 · Data Extract",
        Screenshot("extract", (628, 100, 1416, 535)),
        "CSV and JSON with source and confidence columns.",
    ),
    Receipt(
        "O3 · Safety Tech",
        Screenshot("safety-tech", (264, 150, 1416, 805)),
        "Findings by control type, plus data gaps.",
    ),
    Receipt(
        "Ask",
        Screenshot("ask", (256, 72, 1040, 500)),
        "Uncited sentences removed; live answer shown.",
    ),
)


def receipt_column(receipt: Receipt, left: float, width: float) -> Elements:
    shot = receipt.shot.placed(left, RECEIPT_SHOT_TOP_IN, width)
    below = shot.top + shot.height
    return (
        Text(Box(left, RECEIPT_LABEL_TOP_IN, width, 0.35), receipt.label, LABEL_STYLE),
        shot,
        Text(Box(left, below + 0.25, width, 0.8), receipt.point, POINT_STYLE),
    )


def receipts_slide() -> Elements:
    width = column_width(len(RECEIPTS))
    columns = (
        receipt_column(receipt, column_left(index, width), width)
        for index, receipt in enumerate(RECEIPTS)
    )
    return tuple(itertools.chain.from_iterable(columns))


# --- slide 6: how it works and why to trust it --------------------------------------------


@dataclass(frozen=True)
class Node:
    title: str
    subtitle: str
    accent: str


NODE_WIDTH_IN, NODE_HEIGHT_IN = 2.0, 0.85
PIPELINE = (
    Node("PSI bucket", "s3://nasa-psi", MUTED),
    Node("Ingestion", "AI, offline", ROSE),
    Node("Knowledge base", "PostgreSQL", AMBER),
    Node("Services", "deterministic", ACCENT),
    Node("Dashboard", "", COOL),
)
AGENTS = Node("Agents", "3 request-time calls", VIOLET)
NODE_STEP_IN = (CONTENT_WIDTH_IN - NODE_WIDTH_IN) / (len(PIPELINE) - 1)
ROW_TOP_IN, AGENT_TOP_IN = 1.7, 2.85
SERVICES_INDEX = 3
TEST_TILES = (("1016", "unit"), ("221", "Vitest"), ("247", "integration"), ("106", "end-to-end"))
TILES_WIDTH_IN, TILE_GAP_IN, TILES_TOP_IN = 6.8, 0.2, 4.4
TESTS_CAPTION = "Tests passing, last full run"
GROUNDING = "Every fact sourced; unknown stays null."
ARCHITECTURE_HEIGHT_IN = 2.6
ARCHITECTURE_VIEW = Screenshot("architecture", (264, 238, 1416, 898))


def node_elements(node: Node, box: Box) -> Elements:
    text_left, text_width = box.left + 0.22, box.width - 0.3
    title_box = Box(text_left, box.top + 0.14, text_width, 0.3)
    subtitle_box = Box(text_left, box.top + 0.47, text_width, 0.3)
    elements: Elements = (
        Card(box),
        Mark(Box(box.left, box.top + 0.12, 0.06, box.height - 0.24), node.accent),
        Text(title_box, node.title, TextStyle(14, is_bold=True)),
    )
    if not node.subtitle:
        return elements
    return (*elements, Text(subtitle_box, node.subtitle, TextStyle(11, MUTED, font=MONO)))


def pipeline_boxes() -> list[Box]:
    return [
        Box(MARGIN_IN + index * NODE_STEP_IN, ROW_TOP_IN, NODE_WIDTH_IN, NODE_HEIGHT_IN)
        for index in range(len(PIPELINE))
    ]


def pipeline_arrows(boxes: list[Box]) -> Elements:
    middle = ROW_TOP_IN + NODE_HEIGHT_IN / 2
    arrows = [
        Line((source.left + source.width, middle), (target.left, middle), has_head=True)
        for source, target in itertools.pairwise(boxes)
    ]
    centre = boxes[SERVICES_INDEX].left + NODE_WIDTH_IN / 2
    request_time_llm = Line(
        (centre, boxes[SERVICES_INDEX].bottom),
        (centre, AGENT_TOP_IN),
        VIOLET,
        has_head=True,
        is_dashed=True,
    )
    return (*arrows, request_time_llm)


def pipeline() -> Elements:
    boxes = pipeline_boxes()
    agents_box = Box(boxes[SERVICES_INDEX].left, AGENT_TOP_IN, NODE_WIDTH_IN, NODE_HEIGHT_IN)
    nodes = itertools.starmap(node_elements, zip(PIPELINE, boxes, strict=True))
    return (
        *itertools.chain.from_iterable(nodes),
        *node_elements(AGENTS, agents_box),
        *pipeline_arrows(boxes),
    )


def suite_tile(count: str, suite: str, left: float, width: float) -> Elements:
    return (
        Card(Box(left, TILES_TOP_IN, width, 1.1)),
        Text(Box(left + 0.18, 4.52, width - 0.3, 0.5), count, TextStyle(26, ACCENT, True, MONO)),
        Text(Box(left + 0.18, 5.06, width - 0.3, 0.3), suite, TextStyle(12, MUTED)),
    )


def suite_tiles() -> Elements:
    count = len(TEST_TILES)
    width = (TILES_WIDTH_IN - (count - 1) * TILE_GAP_IN) / count
    tiles = (
        suite_tile(tests, suite, MARGIN_IN + index * (width + TILE_GAP_IN), width)
        for index, (tests, suite) in enumerate(TEST_TILES)
    )
    caption = Text(Box(MARGIN_IN, 4.0, TILES_WIDTH_IN, 0.3), TESTS_CAPTION, CAPTION_STYLE)
    return (caption, *itertools.chain.from_iterable(tiles))


def trust_slide() -> Elements:
    width = ARCHITECTURE_HEIGHT_IN * ARCHITECTURE_VIEW.aspect
    grounding_box = Box(MARGIN_IN, 5.85, TILES_WIDTH_IN, 0.5)
    return (
        *pipeline(),
        *suite_tiles(),
        Text(grounding_box, GROUNDING, TextStyle(20, is_bold=True)),
        ARCHITECTURE_VIEW.placed(RIGHT_EDGE_IN - width, 4.0, width),
    )


# --- slide 7: Earth, next, close ----------------------------------------------------------

EARTH_USES = "Fine water mist, smoke detection, firefighter gear."
NEXT_STEPS = (
    "Run-level data for 14 investigations; LUCI and FM2 partial gravity; more PSI disciplines."
)
CLOSE_CARD_TOP_IN, CLOSE_CARD_HEIGHT_IN = 1.75, 2.4


def titled_card(box: Box, heading: str, body: str) -> Elements:
    inner, width = box.left + 0.3, box.width - 0.6
    return (
        Card(box),
        Text(Box(inner, box.top + 0.3, width, 0.45), heading, TextStyle(20, ACCENT, True)),
        Text(Box(inner, box.top + 0.9, width, 1.3), body, TextStyle(18)),
    )


def close_slide() -> Elements:
    half = column_width(2)
    link_style = TextStyle(20, font=MONO)
    thanks_style = TextStyle(36, ACCENT, is_bold=True, align=PP_ALIGN.RIGHT)
    earth_box = Box(column_left(0, half), CLOSE_CARD_TOP_IN, half, CLOSE_CARD_HEIGHT_IN)
    next_box = Box(column_left(1, half), CLOSE_CARD_TOP_IN, half, CLOSE_CARD_HEIGHT_IN)
    return (
        *titled_card(earth_box, "Earth (O4)", EARTH_USES),
        *titled_card(next_box, "Next", NEXT_STEPS),
        Card(Box(MARGIN_IN, 4.45, CONTENT_WIDTH_IN, 2.1), SURFACE_RAISED),
        Text(Box(0.95, 4.8, 7.5, 0.45), "Code  {{REPO_URL}}", link_style),
        Text(Box(0.95, 5.45, 7.5, 0.45), "Demo  {{DEMO_URL}}", link_style),
        Text(Box(8.6, 5.0, 3.8, 0.7), "Thank you", thanks_style),
    )


# --- views at a glance (ten views mapped to the objectives) -------------------------------

VIEW_CROP = (240, 56, 1440, 806)  # main pane of a 1440 x 900 capture: sidebar and top bar cut
VIEW_COLUMNS = 5
VIEW_GRID_TOP_IN, VIEW_LABEL_GAP_IN, VIEW_ROW_GAP_IN = 1.6, 0.08, 0.5
VIEW_NAME_SHARE = 0.62
OBJECTIVE_COLOURS = {"O1": ACCENT, "O2": COOL, "O3": SUCCESS, "O4": VIOLET}
OBJECTIVE_KEYS = (
    ("O1", "Relevant investigations"),
    ("O2", "Model-ready data"),
    ("O3", "Controls, equipment"),
    ("O4", "Earth uses"),
)
OBJECTIVE_BAND = Box(MARGIN_IN, 5.5, CONTENT_WIDTH_IN, 1.0)


@dataclass(frozen=True)
class View:
    """A dashboard view, the objectives it serves (doc 01 section 3) and its capture."""

    name: str
    objectives: str
    screen: str


VIEWS = (
    View("Overview", "O1", "overview"),
    View("Explorer", "O1·O2", "explorer"),
    View("Ranking", f"O1{EN_DASH}O3", "ranking"),
    View("Compare", "O1", "compare"),
    View("Scenario Lab", "O1·O2", "scenario"),
    View("Data Extract", "O2", "extract"),
    View("Safety Tech", "O3", "safety-tech"),
    View("Earth Apps", "O4", "earth"),
    View("Ask", f"O1{EN_DASH}O4", "ask"),
    View("Architecture", "Demo", "architecture"),
)


def objective_colour(objectives: str) -> str:
    return OBJECTIVE_COLOURS.get(objectives[:2], MUTED)


def view_tile(view: View, left: float, top: float) -> Elements:
    width = column_width(VIEW_COLUMNS)
    shot = Screenshot(view.screen, VIEW_CROP).placed(left, top, width)
    label_top = shot.top + shot.height + VIEW_LABEL_GAP_IN
    name_width = width * VIEW_NAME_SHARE
    tag_style = TextStyle(12, objective_colour(view.objectives), True, MONO, PP_ALIGN.RIGHT)
    return (
        shot,
        Text(Box(left, label_top, name_width, 0.3), view.name, TextStyle(13, is_bold=True)),
        Text(
            Box(left + name_width, label_top, width - name_width, 0.3), view.objectives, tag_style
        ),
    )


def view_grid() -> Elements:
    width = column_width(VIEW_COLUMNS)
    row_step = width / Screenshot("overview", VIEW_CROP).aspect + VIEW_ROW_GAP_IN
    tiles = (
        view_tile(
            view,
            column_left(index % VIEW_COLUMNS, width),
            VIEW_GRID_TOP_IN + index // VIEW_COLUMNS * row_step,
        )
        for index, view in enumerate(VIEWS)
    )
    return tuple(itertools.chain.from_iterable(tiles))


def objective_key(index: int, code: str, outcome: str) -> Elements:
    cell = (OBJECTIVE_BAND.width - 0.6) / len(OBJECTIVE_KEYS)
    left, top = OBJECTIVE_BAND.left + 0.3 + index * cell, OBJECTIVE_BAND.top + 0.32
    code_style = TextStyle(16, OBJECTIVE_COLOURS[code], is_bold=True, font=MONO)
    return (
        Text(Box(left, top, 0.55, 0.4), code, code_style),
        Text(Box(left + 0.55, top - 0.02, cell - 0.65, 0.4), outcome, TextStyle(16)),
    )


def views_slide() -> Elements:
    keys = itertools.starmap(objective_key, ((i, *key) for i, key in enumerate(OBJECTIVE_KEYS)))
    return (
        *view_grid(),
        Card(OBJECTIVE_BAND, SURFACE_RAISED),
        *itertools.chain.from_iterable(keys),
    )


# --- how the backend works (plain-language flow) ------------------------------------------

FLOW_NODE_WIDTH_IN, FLOW_NODE_HEIGHT_IN = 2.05, 1.15
FLOW_ROW_TOPS_IN = (1.85, 4.0)
FLOW_STEP_IN = (CONTENT_WIDTH_IN - FLOW_NODE_WIDTH_IN) / 4
BACKEND_FLOW = (
    Node("PSI archive", "s3://nasa-psi", MUTED),
    Node("Ingestion", "parse · extract · score · index", ROSE),
    Node("PostgreSQL", "cards · vectors", AMBER),
    Node("Services", "deterministic", ACCENT),
    Node("Dashboard", "ten views", COOL),
)
REQUEST_TIME_AI = Node("3 AI calls", "Ask · compare · scenario", VIOLET)
CITATION_CHECK = Node("Citation check", "uncited sentences dropped", SUCCESS)
INGESTION_COLUMN, SERVICES_COLUMN, DASHBOARD_COLUMN = 1, 3, 4
OFFLINE_AI_NOTE = "AI offline"
MODEL_MODES = "Model: mock for tests and offline, Ollama when live."


def flow_box(column: int, row: int) -> Box:
    left = MARGIN_IN + column * FLOW_STEP_IN
    return Box(left, FLOW_ROW_TOPS_IN[row], FLOW_NODE_WIDTH_IN, FLOW_NODE_HEIGHT_IN)


def flow_node(node: Node, box: Box) -> Elements:
    """Larger node than `node_elements`: the subtitle may wrap onto a second line."""
    text_left, text_width = box.left + 0.25, box.width - 0.35
    return (
        Card(box),
        Mark(Box(box.left, box.top + 0.14, 0.06, box.height - 0.28), node.accent),
        Text(Box(text_left, box.top + 0.17, text_width, 0.32), node.title, TextStyle(17, True)),
        Text(Box(text_left, box.top + 0.55, text_width, 0.5), node.subtitle, VALUE_STYLE),
    )


def flow_arrows() -> Elements:
    top_row = [flow_box(column, 0) for column in range(len(BACKEND_FLOW))]
    middle = top_row[0].top + FLOW_NODE_HEIGHT_IN / 2
    data_arrows = [
        Line((source.left + source.width, middle), (target.left, middle), has_head=True)
        for source, target in itertools.pairwise(top_row)
    ]
    services, dashboard = top_row[SERVICES_COLUMN], top_row[DASHBOARD_COLUMN]
    ai_box, check_box = flow_box(SERVICES_COLUMN, 1), flow_box(DASHBOARD_COLUMN, 1)
    services_centre = services.left + FLOW_NODE_WIDTH_IN / 2
    dashboard_centre = dashboard.left + FLOW_NODE_WIDTH_IN / 2
    ai_middle = ai_box.top + FLOW_NODE_HEIGHT_IN / 2
    return (
        *data_arrows,
        Line(
            (services_centre, services.bottom), (services_centre, ai_box.top), VIOLET, True, True
        ),
        Line((ai_box.left + ai_box.width, ai_middle), (check_box.left, ai_middle), VIOLET, True),
        Line(
            (dashboard_centre, check_box.top), (dashboard_centre, dashboard.bottom), VIOLET, True
        ),
    )


def backend_slide() -> Elements:
    nodes = (flow_node(node, flow_box(column, 0)) for column, node in enumerate(BACKEND_FLOW))
    ingestion = flow_box(INGESTION_COLUMN, 0)
    note_box = Box(ingestion.left, ingestion.bottom + 0.15, ingestion.width, 0.35)
    return (
        *itertools.chain.from_iterable(nodes),
        *flow_node(REQUEST_TIME_AI, flow_box(SERVICES_COLUMN, 1)),
        *flow_node(CITATION_CHECK, flow_box(DASHBOARD_COLUMN, 1)),
        *flow_arrows(),
        Text(note_box, OFFLINE_AI_NOTE, TextStyle(14, ROSE, is_bold=True, font=MONO)),
        Text(Box(MARGIN_IN, 5.85, 7.2, 0.4), MODEL_MODES, TextStyle(18, MUTED)),
    )


# --- why trust it -------------------------------------------------------------------------

TRUST_CLAIMS = (
    ("Every fact has a source", ACCENT),
    ("Unknown stays null", COOL),
    ("Ranking is tunable arithmetic", SUCCESS),
    ("Partial gravity bounded, never invented", VIOLET),
)
CLAIM_WIDTH_IN, CLAIM_HEIGHT_IN, CLAIM_STEP_IN = 6.5, 1.0, 1.2
TILE_AREA_LEFT_IN = MARGIN_IN + CLAIM_WIDTH_IN + 0.5
TILE_AREA_TOP_IN, TILE_HEIGHT_IN = 2.15, 2.0
TESTS_RUN_CAPTION = "Tests passing, 2026-11-14 runs"


def claim_row(index: int, claim: str, accent: str) -> Elements:
    box = Box(MARGIN_IN, 1.75 + index * CLAIM_STEP_IN, CLAIM_WIDTH_IN, CLAIM_HEIGHT_IN)
    return (
        Card(box),
        Mark(Box(box.left, box.top + 0.18, 0.08, box.height - 0.36), accent),
        Text(
            Box(box.left + 0.35, box.top + 0.3, box.width - 0.6, 0.45), claim, TextStyle(22, True)
        ),
    )


def test_tile(count: str, suite: str, box: Box) -> Elements:
    return (
        Card(box),
        Text(
            Box(box.left + 0.3, box.top + 0.35, box.width - 0.5, 0.8),
            count,
            TextStyle(44, ACCENT, True, MONO),
        ),
        Text(
            Box(box.left + 0.3, box.top + 1.3, box.width - 0.5, 0.35), suite, TextStyle(16, MUTED)
        ),
    )


def test_tile_grid() -> Elements:
    width = (RIGHT_EDGE_IN - TILE_AREA_LEFT_IN - GAP_IN) / 2
    boxes = (
        Box(
            TILE_AREA_LEFT_IN + index % 2 * (width + GAP_IN),
            TILE_AREA_TOP_IN + index // 2 * (TILE_HEIGHT_IN + GAP_IN),
            width,
            TILE_HEIGHT_IN,
        )
        for index in range(len(TEST_TILES))
    )
    tiles = itertools.starmap(
        test_tile, ((*tile, box) for tile, box in zip(TEST_TILES, boxes, strict=True))
    )
    caption_box = Box(TILE_AREA_LEFT_IN, 1.75, RIGHT_EDGE_IN - TILE_AREA_LEFT_IN, 0.3)
    return (
        Text(caption_box, TESTS_RUN_CAPTION, CAPTION_STYLE),
        *itertools.chain.from_iterable(tiles),
    )


def why_trust_slide() -> Elements:
    claims = itertools.starmap(claim_row, ((i, *claim) for i, claim in enumerate(TRUST_CLAIMS)))
    return (*itertools.chain.from_iterable(claims), *test_tile_grid())


# --- creative process: design first, phased build, design system, test-driven fixes -------


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


PROCESS_STATS = (("13", "design documents"), ("11", "decisions"), ("51", "gaps resolved"))
BUILD_PHASES = (
    "Design",
    "Code",
    "Unit tests",
    "Containers",
    "Makefile",
    "Integration",
    "End-to-end",
)
STAT_TOP_IN, STAT_HEIGHT_IN = 1.7, 1.1
PHASE_TOP_IN, PHASE_HEIGHT_IN, PHASE_GAP_IN = 3.05, 0.6, 0.06
PROCESS_CARD_TOP_IN, PROCESS_CARD_HEIGHT_IN = 3.9, 2.65
SWATCHES = (BACKGROUND, SURFACE, SURFACE_RAISED, TEXT, ACCENT, COOL, SUCCESS, VIOLET)
SWATCH_IN, SWATCH_GAP_IN = 0.42, 0.12
DESIGN_SYSTEM_TEXT = "Dark-only, flame orange, AA contrast, axe-checked."
TEST_FIXES_TEXT = "Contrast 4.5:1\nIcon per coverage state\nCitation per sentence"


def process_stat(index: int, count: str, label: str) -> Elements:
    width = column_width(len(PROCESS_STATS))
    box = Box(column_left(index, width), STAT_TOP_IN, width, STAT_HEIGHT_IN)
    return (
        Card(box),
        Text(
            Box(box.left + 0.3, box.top + 0.2, 1.3, 0.7), count, TextStyle(40, ACCENT, True, MONO)
        ),
        Text(Box(box.left + 1.6, box.top + 0.38, box.width - 1.8, 0.4), label, TextStyle(20)),
    )


def build_phases() -> Elements:
    count = len(BUILD_PHASES)
    width = (CONTENT_WIDTH_IN - (count - 1) * PHASE_GAP_IN) / count
    return tuple(
        Step(
            Box(MARGIN_IN + index * (width + PHASE_GAP_IN), PHASE_TOP_IN, width, PHASE_HEIGHT_IN),
            phase,
            ACCENT if index == 0 else BORDER_STRONG,
        )
        for index, phase in enumerate(BUILD_PHASES)
    )


def swatch_row(left: float, top: float) -> Elements:
    return tuple(
        Mark(
            Box(left + index * (SWATCH_IN + SWATCH_GAP_IN), top, SWATCH_IN, SWATCH_IN),
            colour,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            BORDER_STRONG,
        )
        for index, colour in enumerate(SWATCHES)
    )


def process_cards() -> Elements:
    half = column_width(2)
    design_box = Box(column_left(0, half), PROCESS_CARD_TOP_IN, half, PROCESS_CARD_HEIGHT_IN)
    fixes_box = Box(column_left(1, half), PROCESS_CARD_TOP_IN, half, PROCESS_CARD_HEIGHT_IN)
    inner = design_box.left + 0.3
    return (
        *titled_card(fixes_box, "Tests drove fixes", TEST_FIXES_TEXT),
        Card(design_box),
        Text(
            Box(inner, design_box.top + 0.3, half - 0.6, 0.45),
            "Design system",
            TextStyle(20, ACCENT, True),
        ),
        *swatch_row(inner, design_box.top + 0.95),
        Text(Box(inner, design_box.top + 1.6, half - 0.6, 0.8), DESIGN_SYSTEM_TEXT, TextStyle(18)),
    )


def process_slide() -> Elements:
    stats = itertools.starmap(process_stat, ((i, *stat) for i, stat in enumerate(PROCESS_STATS)))
    return (*itertools.chain.from_iterable(stats), *build_phases(), *process_cards())


# --- deck ---------------------------------------------------------------------------------

SLIDES: tuple[tuple[str, Elements], ...] = (
    ("FlameScope", title_slide()),
    ("Lunar habitat air raises flammability, and the evidence sits in 12 TB.", stakes_slide()),
    ("Ten views answer every challenge objective, from ranking to Earth uses.", views_slide()),
    (
        "Offline ingestion fills one database; online answers stay deterministic and cited.",
        backend_slide(),
    ),
    ("Every number has a source, or it stays empty.", why_trust_slide()),
    ("Design documents came first; tests and a design system shaped the build.", process_slide()),
    ("FlameScope turns 12 TB into cited fire-safety answers for lunar habitats.", close_slide()),
)
TITLE_SLIDE = 1


def frame(number: int) -> Elements:
    """Footer rule, footer text and slide number shared by every slide."""
    page = f"{number:02d} / {SLIDE_COUNT:02d}"
    return (
        Line((MARGIN_IN, 6.85), (RIGHT_EDGE_IN, 6.85), BORDER, name="footer"),
        Text(Box(MARGIN_IN, 6.98, 8.0, 0.3), FOOTER_TEXT, FOOTER_STYLE, "footer"),
        Text(Box(RIGHT_EDGE_IN - 1.5, 6.98, 1.5, 0.3), page, NUMBER_STYLE, "slide-number"),
    )


def place_headline(slide: Slide, headline: str, number: int) -> None:
    title = slide.shapes.title
    title.name = "title"
    is_cover = number == TITLE_SLIDE
    title.left, title.width = Inches(MARGIN_IN), Inches(CONTENT_WIDTH_IN)
    title.top, title.height = Inches(1.2 if is_cover else 0.45), Inches(1.0)
    fill_text_frame(title, headline, COVER_TITLE_STYLE if is_cover else TITLE_STYLE)


def read_speaker_notes(outline_path: Path) -> list[str]:
    chunks = SLIDE_HEADING.split(outline_path.read_text(encoding="utf-8"))[1:]
    notes = [match.group(1).strip() for chunk in chunks if (match := NOTES_BLOCK.search(chunk))]
    if len(notes) != SLIDE_COUNT:
        raise ValueError(f"{outline_path.name}: {len(notes)} note blocks, need {SLIDE_COUNT}")
    return notes


def set_metadata(deck: PresentationType) -> None:
    properties = deck.core_properties
    properties.author = AUTHOR
    properties.title = "FlameScope"
    properties.subject = CHALLENGE
    properties.last_modified_by = properties.keywords = properties.comments = ""
    properties.category = ""
    properties.revision = 1
    properties.created = properties.modified = properties.last_printed = BUILD_TIMESTAMP


APP_PROPERTIES_PARTNAME = "/docProps/app.xml"
# The template's extended properties name a desktop application and a 4:3 format; replace them
# with neutral values that match this deck.
APP_PROPERTIES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
    "<TotalTime>0</TotalTime><PresentationFormat>Widescreen (16:9)</PresentationFormat>"
    "<Slides>{slides}</Slides><Notes>{slides}</Notes><HiddenSlides>0</HiddenSlides>"
    "<ScaleCrop>false</ScaleCrop><LinksUpToDate>false</LinksUpToDate>"
    "<SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged></Properties>"
)


def set_app_properties(deck: PresentationType) -> None:
    parts = deck.part.package.iter_parts()
    app_part = next(part for part in parts if part.partname == APP_PROPERTIES_PARTNAME)
    # python-pptx models app.xml only as a raw part, so its blob is the one place to write it.
    app_part._blob = APP_PROPERTIES_XML.format(slides=len(deck.slides)).encode()


def add_slide(deck: PresentationType, number: int, headline: str, elements: Elements) -> Slide:
    slide = deck.slides.add_slide(deck.slide_layouts[TITLE_ONLY_LAYOUT])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(BACKGROUND)
    place_headline(slide, headline, number)
    for element in (*elements, *frame(number)):
        element.draw(slide)
    return slide


def build_deck() -> PresentationType:
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(SLIDE_WIDTH_IN), Inches(SLIDE_HEIGHT_IN)
    notes = read_speaker_notes(OUTLINE_PATH)
    for number, ((headline, elements), note) in enumerate(zip(SLIDES, notes, strict=True), 1):
        slide = add_slide(deck, number, headline, elements)
        slide.notes_slide.notes_text_frame.text = note
    set_metadata(deck)
    set_app_properties(deck)
    return deck


def missing_screenshots() -> list[str]:
    shots = [item for _, elements in SLIDES for item in elements if isinstance(item, Screenshot)]
    return [shot.path.name for shot in shots if not shot.path.is_file()]


def main() -> None:
    missing = missing_screenshots()
    if missing:
        raise FileNotFoundError(f"screenshots missing in {SCREENS_DIR}: {missing}")
    build_deck().save(str(DECK_PATH))
    verify(DECK_PATH)


if __name__ == "__main__":
    main()
