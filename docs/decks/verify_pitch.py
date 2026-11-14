"""Verify the FlameScope pitch deck with python-pptx (no renderer needed).

Checks: slide count, a title and speaker notes on every slide, headline and body word limits,
every shape inside the slide, a rough text-overflow estimate, image data present, and core and
app properties free of tool names and of the template's 4:3 format.
Run: `.venv/bin/python docs/decks/verify_pitch.py`.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.presentation import Presentation as PresentationType
from pptx.shapes.base import BaseShape
from pptx.slide import Slide
from pptx.util import Emu

DECK_PATH = Path(__file__).resolve().parent / "flamescope-pitch.pptx"
SLIDE_COUNT = 7
TITLE_SLIDE = 1
HEADLINE_WORD_LIMIT = 12
BODY_WORD_LIMIT = 30
DENSE_BODY_WORD_LIMIT = 40
DENSE_SLIDES = frozenset({3, 4, 6})
UNCOUNTED_NAMES = frozenset({"footer", "slide-number"})
FORBIDDEN_TERMS = ("python", "pptx", "claude", "anthropic", "openai", "gpt", "generated")
APP_PROPERTIES_PARTNAME = "docProps/app.xml"
APP_PROPERTIES_FORBIDDEN = (*FORBIDDEN_TERMS, "microsoft", "powerpoint", "4:3")
AVERAGE_GLYPH_WIDTH_EM = 0.52
LINE_HEIGHT_EM = 1.2
DEFAULT_FONT_PT = 12.0
POINTS_PER_INCH = 72
OVERFLOW_TOLERANCE_IN = 0.05
WORD = re.compile(r"\w")


def word_count(text: str) -> int:
    """Whitespace-separated tokens that hold a letter or digit (a lone '·' is not a word)."""
    return sum(1 for token in text.split() if WORD.search(token))


def has_text(shape: BaseShape) -> bool:
    return bool(shape.has_text_frame and shape.text_frame.text.strip())


def body_words(slide: Slide) -> int:
    title = slide.shapes.title
    return sum(
        word_count(shape.text_frame.text)
        for shape in slide.shapes
        if has_text(shape) and shape.name not in UNCOUNTED_NAMES and shape != title
    )


def estimated_text_height_in(shape: BaseShape) -> float:
    """Rough wrapped height; catches text that would overflow its box without a renderer."""
    width_pt = Emu(shape.width).pt
    total_pt = 0.0
    for paragraph in shape.text_frame.paragraphs:
        sizes = [run.font.size.pt for run in paragraph.runs if run.font.size]
        size = max(sizes, default=DEFAULT_FONT_PT)
        chars_per_line = max(1, int(width_pt / (size * AVERAGE_GLYPH_WIDTH_EM)))
        lines = max(1, -(-len(paragraph.text) // chars_per_line))
        total_pt += lines * size * LINE_HEIGHT_EM
    return total_pt / POINTS_PER_INCH


def is_outside(shape: BaseShape, deck: PresentationType) -> bool:
    starts_outside = shape.left < 0 or shape.top < 0
    ends_outside = (
        shape.left + shape.width > deck.slide_width or shape.top + shape.height > deck.slide_height
    )
    return starts_outside or ends_outside


def overflows(shape: BaseShape) -> bool:
    if not has_text(shape):
        return False
    return estimated_text_height_in(shape) > Emu(shape.height).inches + OVERFLOW_TOLERANCE_IN


def lacks_image(shape: BaseShape) -> bool:
    return shape.shape_type == MSO_SHAPE_TYPE.PICTURE and not shape.image.blob


SHAPE_CHECKS = (
    (is_outside, "extends beyond the slide"),
    (lambda shape, _deck: overflows(shape), "text likely overflows its box"),
    (lambda shape, _deck: lacks_image(shape), "has no image data"),
)


def shape_problems(slide: Slide, deck: PresentationType) -> list[str]:
    return [
        f"{shape.name} {message}"
        for shape in slide.shapes
        for check, message in SHAPE_CHECKS
        if check(shape, deck)
    ]


def title_problems(number: int, slide: Slide) -> list[str]:
    title = slide.shapes.title
    if title is None or not title.text_frame.text.strip():
        return ["missing title"]
    if number != TITLE_SLIDE and word_count(title.text_frame.text) > HEADLINE_WORD_LIMIT:
        return [f"headline over {HEADLINE_WORD_LIMIT} words"]
    return []


def content_problems(number: int, slide: Slide) -> list[str]:
    problems = []
    if not slide.has_notes_slide or not slide.notes_slide.notes_text_frame.text.strip():
        problems.append("missing speaker notes")
    limit = DENSE_BODY_WORD_LIMIT if number in DENSE_SLIDES else BODY_WORD_LIMIT
    if body_words(slide) > limit:
        problems.append(f"{body_words(slide)} body words (limit {limit})")
    return problems


def slide_problems(number: int, slide: Slide, deck: PresentationType) -> list[str]:
    problems = [
        *shape_problems(slide, deck),
        *title_problems(number, slide),
        *content_problems(number, slide),
    ]
    return [f"slide {number}: {problem}" for problem in problems]


def metadata_problems(deck: PresentationType) -> list[str]:
    properties = deck.core_properties
    fields = (
        properties.author,
        properties.last_modified_by,
        properties.title,
        properties.subject,
        properties.keywords,
        properties.comments,
        properties.category,
    )
    text = " ".join(field or "" for field in fields).lower()
    return [f"core properties name {term!r}" for term in FORBIDDEN_TERMS if term in text]


def app_properties_problems(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as package:
        text = package.read(APP_PROPERTIES_PARTNAME).decode("utf-8").lower()
    return [f"app properties name {term!r}" for term in APP_PROPERTIES_FORBIDDEN if term in text]


def verify_deck(path: Path) -> list[str]:
    deck = Presentation(str(path))
    slides = list(deck.slides)
    problems = [] if len(slides) == SLIDE_COUNT else [f"{len(slides)} slides, not {SLIDE_COUNT}"]
    for number, slide in enumerate(slides, start=1):
        problems += slide_problems(number, slide, deck)
    return problems + metadata_problems(deck) + app_properties_problems(path)


def summary(path: Path) -> list[str]:
    deck = Presentation(str(path))
    return [
        f"{number}. [{body_words(slide):2d} body words] {slide.shapes.title.text_frame.text}"
        for number, slide in enumerate(deck.slides, start=1)
    ]


def main(path: Path = DECK_PATH) -> None:
    print("\n".join(summary(path)))
    problems = verify_deck(path)
    if problems:
        sys.exit("verification failed:\n" + "\n".join(problems))
    print(f"{path.name}: {SLIDE_COUNT} slides verified")


if __name__ == "__main__":
    main()
