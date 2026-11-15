"""Content of the seven pitch slides: each is a headline plus a tuple of self-drawing elements.

Numbers come from the running stack (`GET /api/v1/meta/stats`, `GET /api/v1/earth-applications`)
and the test reports; the number-source table is in `flamescope-pitch.md`.
"""

from __future__ import annotations

import itertools

from pitch_style import (
    ACCENT,
    AMBER,
    BACKGROUND,
    BORDER_STRONG,
    CAPTION_STYLE,
    CONTENT_TOP_IN,
    CONTENT_WIDTH_IN,
    COOL,
    EN_DASH,
    FAINT,
    LABEL_STYLE,
    MARGIN_IN,
    MONO,
    MUTED,
    NBSP,
    RIGHT_EDGE_IN,
    ROSE,
    STAT_LABEL_STYLE,
    SUCCESS,
    SURFACE,
    SURFACE_RAISED,
    TEXT,
    VALUE_STYLE,
    VIOLET,
    Box,
    Card,
    Elements,
    Line,
    Mark,
    Screenshot,
    Step,
    Text,
    TextStyle,
    accent_card,
    blend,
    column_left,
    column_width,
)
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

REPO_URL = "https://github.com/AyaanAsish/flamescope"
CHALLENGE = "NASA Space Apps 2026 - Flame in Freefall"
OBJECTIVE_COLOURS = {"O1": ACCENT, "O2": COOL, "O3": SUCCESS, "O4": VIOLET}


def chain(groups: object) -> Elements:
    return tuple(itertools.chain.from_iterable(groups))  # type: ignore[call-overload]


def objective_colour(objectives: str) -> str:
    return OBJECTIVE_COLOURS.get(objectives[:2], MUTED)


# --- slide 1: title -----------------------------------------------------------------------

ONE_IDEA = (
    "FlameScope turns 12 TB of microgravity combustion data into ranked, cited "
    "fire-safety answers for the lunar habitat era."
)
HERO_WIDTH_IN, HERO_TOP_IN = 8.9, 3.7
OVERVIEW_SCATTER = Screenshot("overview", (264, 515, 1416, 900))


def title_slide() -> Elements:
    hero = OVERVIEW_SCATTER.placed(RIGHT_EDGE_IN - HERO_WIDTH_IN, HERO_TOP_IN, HERO_WIDTH_IN)
    return (
        Text(Box(MARGIN_IN, 0.55, 6.0, 0.35), CHALLENGE, TextStyle(13, ACCENT, is_bold=True)),
        Text(Box(MARGIN_IN, 2.05, 10.5, 0.85), ONE_IDEA, TextStyle(22, MUTED)),
        Text(Box(MARGIN_IN, 3.75, 2.9, 0.35), "{{TEAM_NAME}}", TextStyle(16, is_bold=True)),
        Text(Box(MARGIN_IN, 4.15, 2.9, 0.35), "{{MEMBERS}}", TextStyle(14, MUTED)),
        hero,
    )


# --- slide 2: the problem (oxygen versus pressure plane) ----------------------------------

PLOT_LEFT, PLOT_BOTTOM, PLOT_WIDTH, PLOT_HEIGHT = 1.5, 6.0, 6.0, 3.9
PSI_AXIS_MAX, OXYGEN_AXIS_MAX = 16.0, 110.0
MARKER_IN = 0.18
ENVELOPE_FILL_ALPHA = 0.16
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
        Text(Box(left, 4.55, width, 0.4), "in PSI", STAT_LABEL_STYLE),
        Text(
            Box(left, 5.4, width, 0.95),
            "Hard to find and interpret for design.",
            TextStyle(22, is_bold=True),
        ),
    )


def problem_slide() -> Elements:
    panel = Card(Box(MARGIN_IN, CONTENT_TOP_IN, 7.4, 5.0))
    return (panel, *habitat_envelope(), *plane_axes(), *plane_points(), *problem_stats())


# --- slide 3: creative process ------------------------------------------------------------

PROCESS_STATS = (
    ("13", "design documents"),
    ("11", "decision records"),
    ("52", "conflicts resolved"),
)
BUILD_PHASES = (
    "Design",
    "Code",
    "Unit tests",
    "Containers",
    "Makefile",
    "Integration",
    "End-to-end",
)
STAT_TOP_IN, STAT_HEIGHT_IN = 1.65, 1.0
PHASE_TOP_IN, PHASE_HEIGHT_IN, PHASE_GAP_IN = 2.95, 0.6, 0.06
PROCESS_CARD_TOP_IN, PROCESS_CARD_HEIGHT_IN = 3.85, 2.75
SWATCHES = (BACKGROUND, SURFACE, SURFACE_RAISED, TEXT, ACCENT, COOL, SUCCESS, VIOLET)
SWATCH_IN, SWATCH_GAP_IN = 0.42, 0.12
DESIGN_SYSTEM_TEXT = "Flame-orange dark theme, WCAG AA, never colour alone, axe-checked."
CURATION_TEXT = "Each fact sourced: PSI API, experimental tables."
SEED_FILES = ("25", "seed files")
CARD_HEADING_STYLE = TextStyle(20, ACCENT, is_bold=True)


def process_stat(index: int, count: str, label: str) -> Elements:
    width = column_width(len(PROCESS_STATS))
    box = Box(column_left(index, width), STAT_TOP_IN, width, STAT_HEIGHT_IN)
    number_style = TextStyle(40, ACCENT, is_bold=True, font=MONO)
    return (
        Card(box),
        Text(Box(box.left + 0.3, box.top + 0.15, 0.8, 0.7), count, number_style),
        Text(Box(box.left + 1.2, box.top + 0.33, box.width - 1.4, 0.4), label, TextStyle(18)),
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


def process_card(box: Box, heading: str, visual: Elements, body: str) -> Elements:
    """Heading, a visual row (swatches or a figure) and one line of body text."""
    inner, width = box.left + 0.3, box.width - 0.6
    return (
        Card(box),
        Text(Box(inner, box.top + 0.3, width, 0.45), heading, CARD_HEADING_STYLE),
        *visual,
        Text(Box(inner, box.top + 1.6, width, 0.8), body, TextStyle(18)),
    )


def seed_figure(left: float, top: float) -> Elements:
    count, label = SEED_FILES
    return (
        Text(
            Box(left, top - 0.15, 1.0, 0.7), count, TextStyle(40, ACCENT, is_bold=True, font=MONO)
        ),
        Text(Box(left + 0.85, top + 0.05, 3.0, 0.4), label, TextStyle(18, MUTED)),
    )


def process_cards() -> Elements:
    half = column_width(2)
    design_box = Box(column_left(0, half), PROCESS_CARD_TOP_IN, half, PROCESS_CARD_HEIGHT_IN)
    curation_box = Box(column_left(1, half), PROCESS_CARD_TOP_IN, half, PROCESS_CARD_HEIGHT_IN)
    visual_top = PROCESS_CARD_TOP_IN + 0.95
    swatches = swatch_row(design_box.left + 0.3, visual_top)
    seeds = seed_figure(curation_box.left + 0.3, visual_top)
    return (
        *process_card(design_box, "Design system", swatches, DESIGN_SYSTEM_TEXT),
        *process_card(curation_box, "Data curation", seeds, CURATION_TEXT),
    )


def process_slide() -> Elements:
    stats = itertools.starmap(process_stat, ((i, *stat) for i, stat in enumerate(PROCESS_STATS)))
    return (*chain(stats), *build_phases(), *process_cards())


# --- slide 4: what it does (seven views mapped to the objectives) -------------------------

VIEW_COLUMNS = 4
VIEW_ROW_TOPS_IN = (1.55, 4.1)
VIEW_LABEL_GAP_IN, VIEW_NAME_SHARE = 0.08, 0.62
VIEWS = (
    ("Ranking", f"O1{EN_DASH}O3", Screenshot("ranking", (866, 0, 1440, 396))),
    ("Scenario Lab", "O1·O2", Screenshot("scenario", (649, 233, 1416, 762))),
    ("Data Extract", "O2", Screenshot("extract-preview", (629, 60, 1416, 603))),
    ("Safety Tech", "O3", Screenshot("safety-tech", (264, 158, 1050, 700))),
    ("Ask", f"O1{EN_DASH}O4", Screenshot("ask", (264, 158, 1032, 688))),
    ("Compare", "O1", Screenshot("compare", (264, 137, 1180, 769))),
    ("Earth Apps", "O4", Screenshot("earth", (264, 180, 1060, 729))),
)
OBJECTIVE_KEYS = (
    ("O1", "relevant research"),
    ("O2", "model data"),
    ("O3", "safety equipment"),
    ("O4", "Earth uses"),
)
KEY_ROW_STEP_IN = 0.45


def view_tile(index: int, view: tuple[str, str, Screenshot]) -> Elements:
    name, objectives, capture = view
    width = column_width(VIEW_COLUMNS)
    left = column_left(index % VIEW_COLUMNS, width)
    shot = capture.placed(left, VIEW_ROW_TOPS_IN[index // VIEW_COLUMNS], width)
    label_top = shot.top + shot.height + VIEW_LABEL_GAP_IN
    name_width = width * VIEW_NAME_SHARE
    tag_style = TextStyle(12, objective_colour(objectives), True, MONO, PP_ALIGN.RIGHT)
    return (
        shot,
        Text(Box(left, label_top, name_width, 0.3), name, TextStyle(13, is_bold=True)),
        Text(Box(left + name_width, label_top, width - name_width, 0.3), objectives, tag_style),
    )


def objective_key() -> Elements:
    width = column_width(VIEW_COLUMNS)
    box = Box(column_left(VIEW_COLUMNS - 1, width), VIEW_ROW_TOPS_IN[1], width, 2.3)
    rows = (
        (
            Text(
                Box(box.left + 0.3, box.top + 0.3 + row * KEY_ROW_STEP_IN, 0.55, 0.35),
                code,
                TextStyle(15, OBJECTIVE_COLOURS[code], is_bold=True, font=MONO),
            ),
            Text(
                Box(box.left + 0.85, box.top + 0.3 + row * KEY_ROW_STEP_IN, box.width - 1.0, 0.35),
                outcome,
                TextStyle(14),
            ),
        )
        for row, (code, outcome) in enumerate(OBJECTIVE_KEYS)
    )
    return (Card(box, SURFACE_RAISED), *chain(rows))


def views_slide() -> Elements:
    return (*chain(itertools.starmap(view_tile, enumerate(VIEWS))), *objective_key())


# --- slide 5: how it works and the real numbers -------------------------------------------

FLOW_NODE_WIDTH_IN, FLOW_NODE_HEIGHT_IN = 2.05, 1.0
FLOW_ROW_TOPS_IN = (1.6, 2.95)
FLOW_STEP_IN = (CONTENT_WIDTH_IN - FLOW_NODE_WIDTH_IN) / 4
BACKEND_FLOW = (
    ("PSI archive", "", MUTED),
    ("Ingestion", "AI offline", ROSE),
    ("PostgreSQL", "", AMBER),
    ("Services", "deterministic", ACCENT),
    ("Dashboard", "", COOL),
)
REQUEST_TIME_AI = ("3 AI calls", "", VIOLET)
CITATION_CHECK = ("Citation check", "", SUCCESS)
SERVICES_COLUMN, DASHBOARD_COLUMN = 3, 4
MODEL_MODES = "Model: mock or Ollama"
NUMBER_CARD_TOP_IN, NUMBER_CARD_HEIGHT_IN = 4.2, 2.1
CATALOG_NUMBERS = (
    ("25", "investigations"),
    ("2,003", "test runs"),
    ("355", "publications"),
    ("40", "findings"),
)
TEST_NUMBERS = (("1136", "unit"), ("225", "Vitest"), ("247", "integration"), ("108", "end-to-end"))


def flow_box(column: int, row: int) -> Box:
    left = MARGIN_IN + column * FLOW_STEP_IN
    return Box(left, FLOW_ROW_TOPS_IN[row], FLOW_NODE_WIDTH_IN, FLOW_NODE_HEIGHT_IN)


def flow_node(node: tuple[str, str, str], box: Box) -> Elements:
    title, subtitle, accent = node
    text_left, text_width = box.left + 0.25, box.width - 0.35
    title_top = box.top + (0.17 if subtitle else 0.32)
    elements = (
        *accent_card(box, accent),
        Text(Box(text_left, title_top, text_width, 0.35), title, TextStyle(16, is_bold=True)),
    )
    if not subtitle:
        return elements
    subtitle_style = TextStyle(12, accent if accent == ROSE else MUTED, font=MONO)
    return (
        *elements,
        Text(Box(text_left, box.top + 0.55, text_width, 0.3), subtitle, subtitle_style),
    )


def flow_arrows() -> Elements:
    top_row = [flow_box(column, 0) for column in range(len(BACKEND_FLOW))]
    middle = top_row[0].top + FLOW_NODE_HEIGHT_IN / 2
    data_arrows = [
        Line((source.right, middle), (target.left, middle), has_head=True)
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
        Line((ai_box.right, ai_middle), (check_box.left, ai_middle), VIOLET, True),
        Line(
            (dashboard_centre, check_box.top), (dashboard_centre, dashboard.bottom), VIOLET, True
        ),
    )


def number_card(
    box: Box, heading: str, numbers: tuple[tuple[str, str], ...], colour: str
) -> Elements:
    inner_width = box.width - 0.6
    cell = inner_width / len(numbers)
    cells = (
        (
            Text(
                Box(box.left + 0.3 + index * cell, box.top + 0.72, cell, 0.6),
                count,
                TextStyle(28, colour, True, MONO),
            ),
            Text(
                Box(box.left + 0.3 + index * cell, box.top + 1.38, cell, 0.35),
                label,
                TextStyle(13, MUTED),
            ),
        )
        for index, (count, label) in enumerate(numbers)
    )
    return (
        Card(box),
        Text(
            Box(box.left + 0.3, box.top + 0.25, inner_width, 0.35),
            heading,
            TextStyle(14, FAINT, is_bold=True),
        ),
        *chain(cells),
    )


def number_cards() -> Elements:
    half = column_width(2)
    catalog = Box(column_left(0, half), NUMBER_CARD_TOP_IN, half, NUMBER_CARD_HEIGHT_IN)
    tests = Box(column_left(1, half), NUMBER_CARD_TOP_IN, half, NUMBER_CARD_HEIGHT_IN)
    return (
        *number_card(catalog, "Seeded catalog", CATALOG_NUMBERS, ACCENT),
        *number_card(tests, "Tests passing", TEST_NUMBERS, SUCCESS),
    )


def how_it_works_slide() -> Elements:
    nodes = (flow_node(node, flow_box(column, 0)) for column, node in enumerate(BACKEND_FLOW))
    modes_box = Box(MARGIN_IN, FLOW_ROW_TOPS_IN[1] + 0.3, 5.0, 0.4)
    return (
        *chain(nodes),
        *flow_node(REQUEST_TIME_AI, flow_box(SERVICES_COLUMN, 1)),
        *flow_node(CITATION_CHECK, flow_box(DASHBOARD_COLUMN, 1)),
        *flow_arrows(),
        Text(modes_box, MODEL_MODES, TextStyle(18, MUTED, font=MONO)),
        *number_cards(),
    )


# --- slide 6: impact ----------------------------------------------------------------------

IMPACT_TOPS_IN = (1.65, 4.3)
IMPACT_HEIGHT_IN = 2.35
IMPACT_TEXT_WIDTH_IN, IMPACT_FIGURE_WIDTH_IN = 3.3, 1.95
IMPACTS = (
    ("O1", "Habitat engineers", "Scenario evidence, gaps stated", "25", "ranked"),
    ("O2", "Modelers", "Runs with provenance, as CSV", "2,003", "test runs"),
    (
        "O3",
        "Equipment designers",
        "Grouped by detection, suppression, materials",
        "40",
        "findings",
    ),
    ("O4", "Earth practitioners", "Mist, smoke detection, firefighter gear", "4", "applications"),
)


def impact_text(box: Box, impact: tuple[str, ...]) -> Elements:
    code, persona, change, *_ = impact
    left = box.left + 0.35
    return (
        Text(
            Box(left, box.top + 0.3, 1.0, 0.35),
            code,
            TextStyle(16, objective_colour(code), True, MONO),
        ),
        Text(
            Box(left, box.top + 0.72, IMPACT_TEXT_WIDTH_IN, 0.45),
            persona,
            TextStyle(22, is_bold=True),
        ),
        Text(Box(left, box.top + 1.3, IMPACT_TEXT_WIDTH_IN, 0.8), change, TextStyle(17, MUTED)),
    )


def impact_figure(box: Box, impact: tuple[str, ...]) -> Elements:
    code, _, _, figure, unit = impact
    left = box.right - 0.3 - IMPACT_FIGURE_WIDTH_IN
    figure_style = TextStyle(40, objective_colour(code), True, MONO, PP_ALIGN.RIGHT)
    return (
        Text(Box(left, box.top + 0.6, IMPACT_FIGURE_WIDTH_IN, 0.75), figure, figure_style),
        Text(
            Box(left, box.top + 1.45, IMPACT_FIGURE_WIDTH_IN, 0.35),
            unit,
            TextStyle(15, MUTED, align=PP_ALIGN.RIGHT),
        ),
    )


def impact_card(index: int, impact: tuple[str, ...]) -> Elements:
    half = column_width(2)
    box = Box(column_left(index % 2, half), IMPACT_TOPS_IN[index // 2], half, IMPACT_HEIGHT_IN)
    return (
        *accent_card(box, objective_colour(impact[0])),
        *impact_text(box, impact),
        *impact_figure(box, impact),
    )


def impact_slide() -> Elements:
    return chain(itertools.starmap(impact_card, enumerate(IMPACTS)))


# --- slide 7: roadmap and close -----------------------------------------------------------

ROADMAP = (
    "Partial-gravity data from LUCI and FM2, when available",
    "Human review of curated cards",
    "More PSI disciplines",
    "Per-run data where tables lacked conditions",
)
ROADMAP_TOP_IN, ROADMAP_HEIGHT_IN = 1.65, 2.25
CLOSE_BAND = Box(MARGIN_IN, 4.3, CONTENT_WIDTH_IN, 2.2)


def roadmap_card(index: int, step: str) -> Elements:
    width = column_width(len(ROADMAP))
    box = Box(column_left(index, width), ROADMAP_TOP_IN, width, ROADMAP_HEIGHT_IN)
    number = f"{index + 1:02d}"
    return (
        Card(box),
        Text(
            Box(box.left + 0.3, box.top + 0.3, 1.0, 0.4), number, TextStyle(20, ACCENT, True, MONO)
        ),
        Text(Box(box.left + 0.3, box.top + 0.85, box.width - 0.6, 1.3), step, TextStyle(17)),
    )


def close_band() -> Elements:
    link_box = Box(CLOSE_BAND.left + 0.4, CLOSE_BAND.top + 0.85, 8.0, 0.5)
    thanks_box = Box(CLOSE_BAND.right - 4.2, CLOSE_BAND.top + 0.7, 3.8, 0.75)
    return (
        Card(CLOSE_BAND, SURFACE_RAISED),
        Text(link_box, REPO_URL, TextStyle(22, font=MONO)),
        Text(thanks_box, "Thank you", TextStyle(36, ACCENT, is_bold=True, align=PP_ALIGN.RIGHT)),
    )


def close_slide() -> Elements:
    return (*chain(itertools.starmap(roadmap_card, enumerate(ROADMAP))), *close_band())


# --- deck ---------------------------------------------------------------------------------

SLIDES: tuple[tuple[str, Elements], ...] = (
    ("FlameScope", title_slide()),
    ("Lunar habitat air raises fire risk; the evidence is hard to use.", problem_slide()),
    ("We wrote the design first, then built in tested phases.", process_slide()),
    ("Seven views answer every challenge objective, with sources.", views_slide()),
    ("AI reads offline; every online answer is computed or cited.", how_it_works_slide()),
    ("Four groups get sourced fire-safety evidence they can act on.", impact_slide()),
    ("FlameScope turns 12 TB into cited fire-safety answers for lunar habitats.", close_slide()),
)
