"""Build the FlameScope detailed demo deck (`flamescope-demo.pptx`), then verify it.

The detailed companion deck, not the 7-slide Space Apps submission: one slide per product view
with live captures from `screens/demo/` and numbered callouts, then the backend in depth.
Slides are declared in `demo_slides_ui.py`, `demo_slides_system.py` and `demo_slides_logic.py`;
speaker notes are read from `flamescope-demo.md` (`### Speaker notes` under `## Slide N - `).
Run from the repository root: `.venv/bin/python docs/decks/build_demo.py`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from build_pitch import set_app_properties
from deck_style import (
    BACKGROUND,
    BORDER,
    CONTENT_WIDTH_IN,
    FAINT,
    MARGIN_IN,
    MONO,
    RIGHT_EDGE_IN,
    SLIDE_HEIGHT_IN,
    SLIDE_WIDTH_IN,
    TITLE_ONLY_LAYOUT,
    TITLE_STYLE,
    Box,
    Line,
    Screenshot,
    Text,
    TextStyle,
    fill_text_frame,
    rgb,
)
from demo_slides_logic import LOGIC_SLIDES
from demo_slides_system import SYSTEM_SLIDES
from demo_slides_ui import UI_SLIDES
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.presentation import Presentation as PresentationType
from pptx.slide import Slide
from pptx.util import Inches
from verify_demo import main as verify

DECK_DIR = Path(__file__).resolve().parent
OUTLINE_PATH = DECK_DIR / "flamescope-demo.md"
DECK_PATH = DECK_DIR / "flamescope-demo.pptx"

SLIDES = (*UI_SLIDES, *SYSTEM_SLIDES, *LOGIC_SLIDES)
TITLE_SLIDE = 1
FOOTER_TEXT = "FlameScope - live demo, detailed companion deck"
DECK_TITLE = "FlameScope - live demo"
AUTHOR = "{{PRESENTER}}"
# New files inherit template dates; pin them so the metadata does not change between rebuilds.
BUILD_TIMESTAMP = datetime(2026, 11, 14, tzinfo=UTC)
COVER_STYLE = TextStyle(54, is_bold=True)
FOOTER_STYLE = TextStyle(10, FAINT)
NUMBER_STYLE = TextStyle(10, FAINT, font=MONO, align=PP_ALIGN.RIGHT)
FOOTER_RULE_IN, FOOTER_TEXT_IN = 6.85, 6.98
NOTES_BLOCK = re.compile(r"### Speaker notes\n(.*?)(?=\n## |\Z)", re.DOTALL)
SLIDE_HEADING = re.compile(r"^## Slide \d+ - ", re.MULTILINE)


def frame(number: int) -> tuple[object, ...]:
    """Footer rule, footer text and slide number shared by every slide."""
    page = f"{number:02d} / {len(SLIDES):02d}"
    return (
        Line((MARGIN_IN, FOOTER_RULE_IN), (RIGHT_EDGE_IN, FOOTER_RULE_IN), BORDER, name="footer"),
        Text(Box(MARGIN_IN, FOOTER_TEXT_IN, 8.0, 0.3), FOOTER_TEXT, FOOTER_STYLE, "footer"),
        Text(
            Box(RIGHT_EDGE_IN - 1.5, FOOTER_TEXT_IN, 1.5, 0.3), page, NUMBER_STYLE, "slide-number"
        ),
    )


def place_headline(slide: Slide, headline: str, number: int) -> None:
    title = slide.shapes.title
    title.name = "title"
    is_cover = number == TITLE_SLIDE
    title.left, title.width = Inches(MARGIN_IN), Inches(CONTENT_WIDTH_IN)
    title.top, title.height = Inches(1.2 if is_cover else 0.4), Inches(1.0)
    fill_text_frame(title, headline, COVER_STYLE if is_cover else TITLE_STYLE)


def read_speaker_notes(outline_path: Path) -> list[str]:
    chunks = SLIDE_HEADING.split(outline_path.read_text(encoding="utf-8"))[1:]
    notes = [match.group(1).strip() for chunk in chunks if (match := NOTES_BLOCK.search(chunk))]
    if len(notes) != len(SLIDES):
        raise ValueError(f"{outline_path.name}: {len(notes)} note blocks, need {len(SLIDES)}")
    return notes


def set_metadata(deck: PresentationType) -> None:
    properties = deck.core_properties
    properties.author = AUTHOR
    properties.title = DECK_TITLE
    properties.subject = "Detailed companion deck for the live FlameScope demo"
    properties.last_modified_by = properties.keywords = properties.comments = ""
    properties.category = ""
    properties.revision = 1
    properties.created = properties.modified = properties.last_printed = BUILD_TIMESTAMP


def add_slide(deck: PresentationType, number: int, headline: str, elements: tuple) -> Slide:
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
        raise FileNotFoundError(f"screenshots missing in screens/demo: {missing}")
    build_deck().save(str(DECK_PATH))
    verify(DECK_PATH, len(SLIDES))


if __name__ == "__main__":
    main()
