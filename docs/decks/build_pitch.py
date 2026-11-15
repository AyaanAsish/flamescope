"""Build the FlameScope judges' pitch deck (`flamescope-pitch.pptx`), then verify it.

Seven slides, the Space Apps limit for Global Award eligibility. The visual system lives in
`pitch_style.py`, the slide content in `pitch_slides.py`; speaker notes are read from
`flamescope-pitch.md`; screenshots are real captures in `screens/`.
Run from the repository root: `.venv/bin/python docs/decks/build_pitch.py`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pitch_slides import CHALLENGE, SLIDES
from pitch_style import (
    ACCENT,
    AMBER,
    BACKGROUND,
    BORDER,
    BORDER_STRONG,
    BORDER_WIDTH_PT,
    CONTENT_TOP_IN,
    CONTENT_WIDTH_IN,
    COOL,
    COVER_TITLE_STYLE,
    DECK_DIR,
    EDGE,
    FAINT,
    FOOTER_STYLE,
    GAP_IN,
    MARGIN_IN,
    MONO,
    MUTED,
    NBSP,
    NUMBER_STYLE,
    RIGHT_EDGE_IN,
    ROSE,
    SCREENS_DIR,
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
    Elements,
    Line,
    Mark,
    Screenshot,
    Text,
    TextStyle,
    add_filled_shape,
    blend,
    fill_text_frame,
    inches,
    rgb,
    set_corner_radius,
    set_outline,
    write_paragraph,
)
from pptx import Presentation
from pptx.presentation import Presentation as PresentationType
from pptx.slide import Slide
from pptx.util import Inches
from verify_pitch import main as verify

# Re-exported for the demo deck scripts (`deck_style.py`, `build_demo.py`, `demo_slides_*.py`).
__all__ = [
    "ACCENT",
    "AMBER",
    "BACKGROUND",
    "BORDER",
    "BORDER_STRONG",
    "BORDER_WIDTH_PT",
    "CONTENT_TOP_IN",
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
    "Card",
    "Line",
    "Mark",
    "Screenshot",
    "Text",
    "TextStyle",
    "add_filled_shape",
    "blend",
    "fill_text_frame",
    "inches",
    "rgb",
    "set_app_properties",
    "set_corner_radius",
    "set_outline",
    "write_paragraph",
]

OUTLINE_PATH = DECK_DIR / "flamescope-pitch.md"
DECK_PATH = DECK_DIR / "flamescope-pitch.pptx"
SLIDE_COUNT = 7
TITLE_SLIDE = 1
FOOTER_TEXT = "FlameScope - NASA Space Apps 2026 - Flame in Freefall"
FOOTER_RULE_TOP_IN, FOOTER_TEXT_TOP_IN = 6.85, 6.98
COVER_TITLE_TOP_IN, TITLE_TOP_IN = 0.95, 0.45
AUTHOR = "{{TEAM_NAME}}"
# New files inherit template dates; pin them so the metadata does not change between rebuilds.
BUILD_TIMESTAMP = datetime(2026, 11, 14, tzinfo=UTC)
NOTES_BLOCK = re.compile(r"### Speaker notes\n(.*?)(?=\n## |\Z)", re.DOTALL)
SLIDE_HEADING = re.compile(r"^## Slide \d+ - ", re.MULTILINE)


def frame(number: int) -> Elements:
    """Footer rule, footer text and slide number shared by every slide."""
    page = f"{number:02d} / {SLIDE_COUNT:02d}"
    return (
        Line(
            (MARGIN_IN, FOOTER_RULE_TOP_IN),
            (RIGHT_EDGE_IN, FOOTER_RULE_TOP_IN),
            BORDER,
            name="footer",
        ),
        Text(Box(MARGIN_IN, FOOTER_TEXT_TOP_IN, 8.0, 0.3), FOOTER_TEXT, FOOTER_STYLE, "footer"),
        Text(
            Box(RIGHT_EDGE_IN - 1.5, FOOTER_TEXT_TOP_IN, 1.5, 0.3),
            page,
            NUMBER_STYLE,
            "slide-number",
        ),
    )


def place_headline(slide: Slide, headline: str, number: int) -> None:
    title = slide.shapes.title
    title.name = "title"
    is_cover = number == TITLE_SLIDE
    title.left, title.width = Inches(MARGIN_IN), Inches(CONTENT_WIDTH_IN)
    title.top = Inches(COVER_TITLE_TOP_IN if is_cover else TITLE_TOP_IN)
    title.height = Inches(1.0)
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
