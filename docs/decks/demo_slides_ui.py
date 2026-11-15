"""Opening and product-view slides of the FlameScope demo deck (slides 1 to 21).

Every view slide is a real 1440x900 capture of the live stack (`screens/demo/`) with numbered
callouts drawn as native shapes, plus a panel with "Do", "Say" and "Shows" for live steps.
Callout positions are given in screenshot pixels and mapped onto the placed picture.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from deck_style import (
    ACCENT,
    BODY,
    BODY_MUTED,
    CODE,
    CONTENT_BOTTOM_IN,
    CONTENT_TOP_IN,
    CONTENT_WIDTH_IN,
    COOL,
    GAP_IN,
    HEADING,
    KICKER,
    LABEL,
    MARGIN_IN,
    MONO,
    MUTED,
    NBSP,
    RIGHT_EDGE_IN,
    SMALL_MUTED,
    SUCCESS,
    SURFACE_RAISED,
    VIOLET,
    Box,
    Callout,
    Card,
    Line,
    Paragraphs,
    Pill,
    Screenshot,
    Text,
    TextStyle,
)

Elements = tuple[object, ...]
Pixel = tuple[int, int]

MAIN_AREA = (240, 0, 1440, 900)  # the view without the 240 px sidebar, top bar kept
SHOT_HEIGHT_IN = CONTENT_BOTTOM_IN - CONTENT_TOP_IN
PANEL_INSET_IN = 0.2


def placed_view(name: str, crop: tuple[int, int, int, int] = MAIN_AREA) -> Screenshot:
    shot = Screenshot(f"demo/{name}", crop)
    return shot.placed(MARGIN_IN, CONTENT_TOP_IN, SHOT_HEIGHT_IN * shot.aspect)


def pin_position(shot: Screenshot, pixel: Pixel) -> tuple[float, float]:
    crop_left, crop_top, crop_right, _ = shot.crop
    scale = shot.width / (crop_right - crop_left)
    x, y = pixel
    return shot.left + (x - crop_left) * scale, shot.top + (y - crop_top) * scale


def callouts(shot: Screenshot, pins: tuple[Pixel, ...]) -> Elements:
    return tuple(
        Callout(number, pin_position(shot, pixel)) for number, pixel in enumerate(pins, 1)
    )


def panel_box(shot: Screenshot) -> Box:
    left = shot.left + shot.width + GAP_IN
    return Box(left, CONTENT_TOP_IN, RIGHT_EDGE_IN - left, SHOT_HEIGHT_IN)


def view_slide(shot: Screenshot, pins: tuple[Pixel, ...], lines: tuple) -> Elements:
    box = panel_box(shot)
    inner = Box(
        box.left + PANEL_INSET_IN,
        box.top + PANEL_INSET_IN,
        box.width - 2 * PANEL_INSET_IN,
        box.height - 2 * PANEL_INSET_IN,
    )
    return (shot, *callouts(shot, pins), Card(box), Paragraphs(inner, lines, "panel"))


def numbered(notes: tuple[str, ...]) -> tuple:
    return tuple(
        (f"{number}{NBSP}{NBSP}{note}", BODY_MUTED) for number, note in enumerate(notes, 1)
    )


@dataclass(frozen=True)
class StepCopy:
    kicker: str
    do: str
    say: str
    shows: str
    notes: tuple[str, ...]

    def lines(self) -> tuple:
        return (
            (self.kicker, KICKER),
            ("Do", LABEL),
            (self.do, BODY),
            ("Say", LABEL),
            (self.say, BODY),
            ("Shows", LABEL),
            (self.shows, BODY),
            *numbered(self.notes),
        )


def feature_lines(
    kicker: str, points: tuple[tuple[str, str], ...], notes: tuple[str, ...]
) -> tuple:
    body = itertools.chain.from_iterable(((head, LABEL), (text, BODY)) for head, text in points)
    return ((kicker, KICKER), *body, *numbered(notes))


# --- 1 to 3: title, user, demo map ----------------------------------------------------------

COMPANION_NOTE = "Detailed companion deck - not the 7-slide Space Apps submission"
TITLE_HERO = Screenshot("demo/overview", (248, 330, 1432, 599)).placed(2.2, 4.45, 8.93)


def title_slide() -> Elements:
    return (
        Text(
            Box(MARGIN_IN, 0.7, 9.0, 0.35),
            "NASA Space Apps 2026 - Flame in Freefall",
            TextStyle(13, ACCENT, True),
        ),
        Text(
            Box(MARGIN_IN, 2.3, 11.0, 0.45),
            "Every view of the product and every part of the backend, step by step.",
            TextStyle(20, MUTED),
        ),
        Text(Box(MARGIN_IN, 2.9, 11.0, 0.35), COMPANION_NOTE, TextStyle(14, COOL)),
        Text(Box(MARGIN_IN, 3.45, 6.0, 0.35), "{{PRESENTER}}", TextStyle(16, is_bold=True)),
        Text(Box(MARGIN_IN, 3.85, 6.0, 0.35), "{{DATE}}", TextStyle(14, MUTED)),
        TITLE_HERO,
    )


USER_QUESTION = (
    "Which of the PSI combustion investigations tell me anything about a fire in a lunar "
    f"habitat at 34{NBSP}% oxygen and 8.2{NBSP}psi?"
)
USER_NEEDS = (
    ("O1", "Which investigations are relevant to crew fire safety?", ACCENT),
    ("O2", "Which numbers can feed a flammability model?", COOL),
    ("O3", "What informs detection, suppression and materials?", SUCCESS),
    ("O4", "What carries over to fire safety on Earth?", VIOLET),
)
ENVELOPE_FACTS = (
    f"Spacesuit: 100{NBSP}% O2 at 4.3{NBSP}psi. Earth sea level: 14.7{NBSP}psi.",
    f"Lunar habitats: 30{NBSP}% O2 or more at 10.2{NBSP}psi or less - more flammable.",
    f"PSI holds no partial-gravity combustion data yet (Moon 0.166{NBSP}g).",
)


def need_row(index: int, need: tuple[str, str, str]) -> Elements:
    objective, text, colour = need
    top = 1.95 + index * 0.72
    return (
        Pill(Box(7.25, top, 0.7, 0.36), objective, colour),
        Text(Box(8.1, top + 0.03, 4.6, 0.6), text, BODY),
    )


def user_slide() -> Elements:
    question_card = Box(MARGIN_IN, CONTENT_TOP_IN, 6.3, 5.2)
    needs = itertools.chain.from_iterable(itertools.starmap(need_row, enumerate(USER_NEEDS)))
    facts = tuple((fact, BODY_MUTED) for fact in ENVELOPE_FACTS)
    return (
        Card(question_card),
        Paragraphs(
            Box(0.9, 1.8, 5.7, 4.7),
            (
                ("THE USER", KICKER),
                ("A habitat fire-safety engineer", TextStyle(22, is_bold=True)),
                (
                    "Choosing materials and detection for a lunar habitat. She has an afternoon, "
                    "not a month.",
                    BODY_MUTED,
                ),
                ("Her question", LABEL),
                (USER_QUESTION, TextStyle(18)),
                ("Challenge facts (doc 01 section 6)", LABEL),
                *facts,
            ),
        ),
        Text(Box(7.25, CONTENT_TOP_IN, 5.4, 0.35), "What she needs from PSI", HEADING),
        *needs,
        Text(
            Box(7.25, 4.95, 5.4, 1.6),
            "The 3-minute live path answers each need in turn. Slides 4 to 21 replay it with "
            "real captures if the network or laptop fails.",
            BODY_MUTED,
        ),
    )


@dataclass(frozen=True)
class Stop:
    view: str
    route: str
    seconds: int
    objective: str


DEMO_STOPS = (
    Stop("Overview", "/", 20, "O1"),
    Stop("Ranking", "/ranking", 25, "O1"),
    Stop("Detail", "/investigations/[id]", 15, "O1 O2"),
    Stop("Compare", "/compare", 20, "O1"),
    Stop("Scenario Lab", "/scenario", 25, "O1 O2"),
    Stop("Data Extract", "/extract", 15, "O2"),
    Stop("Safety Tech", "/safety-tech", 10, "O3"),
    Stop("Ask", "/ask", 25, "all"),
    Stop("Earth Apps", "/earth", 10, "O4"),
    Stop("Architecture", "/architecture", 15, "trust"),
)
STOPS_PER_ROW = 5
STOP_HEIGHT_IN = 1.6
STOP_GAP_IN = 0.3
STOP_ROW_TOPS = (1.75, 4.0)


def stop_box(index: int) -> Box:
    width = (CONTENT_WIDTH_IN - (STOPS_PER_ROW - 1) * STOP_GAP_IN) / STOPS_PER_ROW
    row, column = divmod(index, STOPS_PER_ROW)
    return Box(
        MARGIN_IN + column * (width + STOP_GAP_IN), STOP_ROW_TOPS[row], width, STOP_HEIGHT_IN
    )


def stop_elements(index: int, stop: Stop) -> Elements:
    box = stop_box(index)
    lines = (
        (f"STEP {index + 1}", KICKER),
        (stop.view, TextStyle(18, is_bold=True)),
        (stop.route, CODE),
        (f"{stop.seconds}{NBSP}s · {stop.objective}", SMALL_MUTED),
    )
    inner = Box(box.left + 0.18, box.top + 0.15, box.width - 0.3, box.height - 0.2)
    return (Card(box), Paragraphs(inner, lines, "stop"))


def stop_arrows() -> Elements:
    boxes = [stop_box(index) for index in range(len(DEMO_STOPS))]
    arrows = []
    for source, target in itertools.pairwise(boxes):
        if source.top != target.top:
            continue
        middle = source.top + source.height / 2
        arrows.append(
            Line((source.left + source.width, middle), (target.left, middle), has_head=True)
        )
    return tuple(arrows)


def demo_map_slide() -> Elements:
    stops = itertools.chain.from_iterable(itertools.starmap(stop_elements, enumerate(DEMO_STOPS)))
    footer = (
        "Total 180 s. Sidebar labels are the click targets; every step was run with "
        "Playwright on the live stack."
    )
    return (
        *stops,
        *stop_arrows(),
        Text(Box(MARGIN_IN, 5.95, CONTENT_WIDTH_IN, 0.6), footer, BODY_MUTED),
    )


# --- 4 to 21: the views -----------------------------------------------------------------------

OVERVIEW = StepCopy(
    "STEP 1 · / · 0:00-0:20 · O1",
    "Open http://localhost:3000. Point at the LLM badge, the tiles and the scatter.",
    "This is every PSI combustion investigation, 2,003 test runs on one map, and the shaded "
    "box is her lunar habitat.",
    "O1 · FR-14 · CF-11: four parallel calls, no LLM",
    (
        "LLM badge: ollama · deepseek-v4-pro:cloud",
        "Dataset badge: seed · 25 investigations",
        "Tiles from /meta/stats: 2,003 runs, 355 papers",
        f"Catalog: O2 12-85{NBSP}%, 25.3-506.6{NBSP}kPa",
        "Runs by O2 and pressure; lunar box shaded",
    ),
)
OVERVIEW_PINS = ((1040, 27), (1238, 27), (272, 105), (268, 219), (1306, 580))

RANKING = StepCopy(
    "STEP 2 · /ranking · 0:20-0:45 · O1",
    "Sidebar Ranking. Preset: Lunar habitat. Click the Habitat tab.",
    "Her priorities re-rank all 25 investigations instantly: pure arithmetic over stored, cited "
    "ratings, no AI at query time.",
    "O1 · FR-03, FR-04 · CF-05 · POST /rank",
    (
        "Preset lunar_habitat: lens weights 60/20/20",
        "Lens tabs: Overall, Habitat, Modeling, Controls",
        "Sliders re-rank; weights are normalized",
        "FLEX leads on Habitat with 80",
    ),
)
RANKING_PINS = ((1300, 137), (391, 251), (272, 321), (1262, 351))

EVIDENCE = StepCopy(
    "STEP 2 (cont.) · evidence drawer",
    "Click Evidence on the FLEX row. Esc closes the drawer.",
    "Every rating shows its rationale and source; FLEX ran from 12 to 34 percent oxygen at "
    "reduced and raised pressure.",
    "FR-15 provenance · EvidenceDrawer · evidence-drawer",
    (
        "Atmosphere match 5 / 5 with its rationale",
        "Weight 35 %, contributes 35 points",
        "Source links to the card fields",
        "Origin chip: llm (seed and override also exist)",
    ),
)
EVIDENCE_PINS = ((885, 345), (1140, 368), (885, 445), (1362, 343))

DETAIL = StepCopy(
    "STEP 3 · /investigations/[id] · 0:45-1:00 · O1 O2",
    "Click the FLEX name in row 1. Then the Test runs tab.",
    "One card per investigation: fuels, hardware and conditions, every statement linked to its "
    "PSI source.",
    "FR-01, FR-06 · CF-04 · detail, runs, variables",
    (
        "Badges: Liquid, ISS, Microgravity, 274 runs",
        "Seven tabs, Summary to Data",
        "View in PSI opens the PSI-69 page",
        "Source: PSI record via the geode-py API",
        f"Conditions: 12-34{NBSP}% O2, 70.2-309.3{NBSP}kPa",
    ),
)
DETAIL_PINS = ((262, 178), (268, 233), (1288, 137), (283, 530), (1050, 304))

DETAIL_RUNS = StepCopy(
    "STEP 3 (cont.) · Test runs tab, page 2 of 3",
    "Scroll to the bottom of Test runs. Click Next.",
    "All 274 FLEX tests are here, one row of the PSI experimental table each, paged 100 at a "
    "time.",
    "FR-06 · GET /investigations/{id}/runs, page_size 100",
    (
        "One run per table row: label, fuel, phase",
        "O2, pressure, flow, gravity; n/a is unknown",
        "Each row links to its table and row",
        '"Showing 100 of 274 runs."',
        "Previous / Next pages through all runs",
    ),
)
DETAIL_RUNS_PINS = ((270, 84), (550, 84), (1230, 84), (268, 752), (1230, 793))

EXPLORER = feature_lines(
    "EXPLORER · /explorer · optional detour",
    (
        (
            "Facets",
            "Fuel phase (gas 9, solid 8, liquid 6), gravity, project, O2 and pressure, hardware "
            "and phenomena; mirrored in the URL.",
        ),
        ("Cards", "Acronym, title, badges, ranges and the four scores; Add to compare."),
        (
            "Backend",
            "GET /investigations and GET /facets in parallel (CF-04); full-text plus filters.",
        ),
    ),
    (
        "Facet filters with counts",
        "Sort by acronym or any score",
        "Compare tray",
        "Per-lens scores on each card",
    ),
)
EXPLORER_PINS = ((268, 188), (1094, 116), (1278, 116), (592, 445))

COMPARE = StepCopy(
    "STEP 4 · /compare · 1:00-1:20 · O1",
    "Sidebar Compare. Add investigation: FLEX, SPICE, SAFFIRE-II.",
    "A droplet study, a gas-jet study and a solid-materials study side by side: same and "
    "different at a glance.",
    "O1 · FR-05 · CF-06 · POST /compare",
    (
        "Add investigation picker (2 to 4)",
        "Selected chips, mirrored in ?ids=",
        "Hardware row marked Different (icon + text)",
        "Same rows carry an = icon, not colour alone",
    ),
)
COMPARE_PINS = ((288, 219), (592, 221), (1316, 553), (1316, 373))

LINEAGE = feature_lines(
    "STEP 4 (cont.) · narrative and lineage",
    (
        (
            "Narrative",
            "Six verified sentences on the live model, each linked to the PSI records and "
            "experimental tables it cites.",
        ),
        (
            "Lineage (FR-12)",
            "FLEX sits on MDCA in CIR; SPICE on the SPICE flow duct in MSG; SAFFIRE-II lists "
            "no hardware.",
        ),
    ),
    (
        "A verified narrative sentence",
        "Its citations: PSI experimental tables",
        "Investigation node",
        "SAFFIRE-II: no shared hardware",
        "Apparatus hosted in a facility",
    ),
)
LINEAGE_PINS = ((283, 71), (283, 93), (338, 580), (338, 709), (1088, 720))

SCENARIO = StepCopy(
    "STEP 5 · /scenario · 1:20-1:45 · O1 O2",
    "Sidebar Scenario Lab. Preset: Lunar habitat (assumed default).",
    "She types her habitat; oxygen, pressure and flow are inside tested ground, partial gravity "
    "is not, and FlameScope says so.",
    "O1 O2 · FR-07, FR-16 · CF-07 · POST /scenario",
    (
        f"Preset fills 34{NBSP}%, 56.5{NBSP}kPa, 10{NBSP}cm/s, 0.166{NBSP}g",
        '"assumed default": a design assumption',
        "Covered: O2, pressure and flow",
        "Gravity: No data (catalog has 0 g and 1 g)",
        "Bounds: 0 g from 10 studies, 1 g SAFFIRE-II",
    ),
)
SCENARIO_PINS = ((288, 345), (288, 383), (1322, 297), (1322, 543), (1040, 817))

MATCHES = StepCopy(
    "STEP 5 (cont.) · closest matching investigations",
    "Scroll to Closest matching investigations.",
    "Seven investigations have runs at 60 percent similarity or better: 840 runs she can model "
    "from.",
    "FR-07 · doc 08 s4 weighted distance · scenario-match",
    (
        "Export matching runs (CSV / JSON)",
        "FLEX-2 first: 8 runs at 60 % or better",
        "Best-run similarity 96.3 %",
        "Per-dimension similarity bars",
        "The best run, with its source label",
    ),
)
MATCHES_PINS = ((962, 478), (669, 551), (1300, 552), (935, 607), (1398, 647))

SCENARIO_EXPLAIN = StepCopy(
    "STEP 5 (cont.) · Explain and export",
    "Click Explain. Then Export matching runs (CSV).",
    "The written reading cites the exact test rows; anything uncovered, like gravity, gets a "
    "fixed caveat.",
    "ADR-08 · scenario_id round trip to /extract/export",
    (
        "Interpretation, generated on request",
        "A cited sentence (FLEX test 37)",
        "Citation: PSI-69 experimental table, row 37",
        "Deterministic caveat: gravity no_data",
        "CSV export: the 840 matching runs",
    ),
)
SCENARIO_EXPLAIN_PINS = ((668, 471), (668, 559), (668, 602), (668, 690), (962, 844))

EXTRACT = StepCopy(
    "STEP 6 · /extract · 1:45-2:00 · O2",
    "Sidebar Data Extract. Click Export CSV.",
    "A model-ready table: conditions, outcomes and provenance on every row, with the filters in "
    "the file header.",
    "O2 · FR-08 · CF-08 · POST /extract/preview, /export",
    (
        "Export CSV / Export JSON: all 2,003 rows",
        "Query: fuel phase, O2, pressure, outcomes",
        "Columns: 19 defaults, any subset",
        "Data dictionary drawer",
        "Preview: first rows, source on each",
    ),
)
EXTRACT_PINS = ((1132, 113), (283, 260), (649, 185), (1260, 191), (649, 563))

DICTIONARY_CROP = (672, 0, 1440, 900)
EXPORT_COMMENTS = (
    "# exported_at: 2026-11-15T01:17:05+00:00",
    "# filters: {}",
    "# rubric_version: 2026.11-1",
)
EXPORT_COLUMNS = (
    "investigation,run_label,fuel_name,fuel_phase,shape,characteristic_dimension_mm,o2_fraction,"
    "diluent,pressure_kpa,flow_speed_cm_s,flow_direction,gravity_g,ignited,flame_spread_rate_mm_s,"
    "extinction,is_aggregate,confidence,source_uri,source_locator"
)
HEADER_LINE_CHARS = 60
HEADER_STYLE = TextStyle(12, COOL, font=MONO)


def header_lines() -> tuple[str, ...]:
    """The real export header, the column row broken after commas so it wraps legibly."""
    lines, current = [], ""
    for column in EXPORT_COLUMNS.split(","):
        piece = f"{column},"
        if current and len(current) + len(piece) > HEADER_LINE_CHARS:
            lines.append(current)
            current = ""
        current += piece
    lines.append(current.rstrip(","))
    return (*EXPORT_COMMENTS, *lines)


DICTIONARY_POINTS = (
    ("Dictionary", "GET /extract/dictionary: name, label, unit, description for every column."),
    ("Provenance", "2,003 rows; each ends with confidence, source_uri and source_locator."),
)


def dictionary_slide() -> Elements:
    shot = placed_view("extract-dictionary", DICTIONARY_CROP)
    box = panel_box(shot)
    header_card = Box(box.left, 3.95, box.width, CONTENT_BOTTOM_IN - 3.95)
    return (
        shot,
        *callouts(shot, ((700, 163), (935, 522))),
        Paragraphs(
            Box(box.left, CONTENT_TOP_IN, box.width, 2.35),
            (
                ("DATA EXTRACT · dictionary and CSV", KICKER),
                *itertools.chain.from_iterable(
                    ((head, LABEL), (text, BODY)) for head, text in DICTIONARY_POINTS
                ),
                *numbered(("Column, label, unit", "Units: fraction, kPa, cm/s, g, mm")),
            ),
        ),
        Card(header_card, SURFACE_RAISED),
        Paragraphs(
            Box(
                header_card.left + 0.2,
                header_card.top + 0.15,
                header_card.width - 0.4,
                header_card.height - 0.25,
            ),
            (
                ("Real export header (live stack)", LABEL),
                *((line, HEADER_STYLE) for line in header_lines()),
            ),
        ),
    )


SAFETY = StepCopy(
    "STEP 7 · /safety-tech · 2:00-2:10 · O3",
    "Sidebar Safety Tech.",
    "Forty sourced findings, grouped by the equipment decision they inform; detection alone has "
    "nine.",
    "O3 · FR-09 · CF-10 · /insights/safety-tech, /gaps",
    (
        "Detection: 9 findings from 6 investigations",
        "Supporting investigations link to detail",
        "Each finding carries a confidence",
        "and the publication it comes from",
    ),
)
SAFETY_PINS = ((268, 188), (285, 246), (285, 345), (285, 371))

ASK_QUESTION = "What is known about smoke detection in microgravity?"
ASK = StepCopy(
    "STEP 8 · /ask · 2:10-2:35 · all objectives",
    f'Sidebar Ask. Type "{ASK_QUESTION}" and press Ask. Click citation 1.',
    "The answer streams, then every sentence without a supporting source is removed; the chips "
    "open the sources.",
    "FR-11 · CF-09 · POST /ask (SSE)",
    (
        "The prepared question",
        "A citation chip after every sentence",
        "Related investigations link to detail",
        "Selected citation highlighted in Sources",
    ),
)
ASK_PINS = ((268, 180), (735, 264), (283, 435), (1078, 388))

EARTH = StepCopy(
    "STEP 9 · /earth · 2:35-2:45 · O4",
    "Sidebar Earth Apps. Click the Detection sector.",
    "The challenge's Earth spin-offs, curated by people; harvest-mode AI only proposes "
    "candidates for review.",
    "O4 · FR-10 · CF-10 · GET /earth-applications",
    (
        "Sector filter (?sector=detection)",
        "Smoke detection, one of four applications",
        "Linked: PSI-115, SAME, SAME-R",
        "Sources: challenge text and PSI records",
    ),
)
EARTH_PINS = ((268, 194), (283, 265), (283, 400), (283, 450))

ARCHITECTURE = StepCopy(
    "STEP 10 · /architecture · 2:45-3:00 · trust",
    "Sidebar Architecture. Components tab. Click Domain services. Click CF-05.",
    "The design documents are inside the product, with live status from the running stack.",
    "FR-13 · CF-12 · GET /meta/status every 10 s",
    (
        "Seven tabs; Components selected",
        "C-SVC node (12 component nodes)",
        "NodePanel with live up badge",
        "Interfaces, files, related call flows",
        "Legend: up, mock or idle, down",
    ),
)
ARCHITECTURE_PINS = ((478, 198), (760, 427), (1180, 291), (1046, 467), (296, 518))

CALL_FLOWS = feature_lines(
    "ARCHITECTURE · Call flows and the other tabs",
    (
        (
            "Call flows",
            "CF-01 to CF-13 with an LLM chip (none, optional, yes), the Mermaid sequence from "
            "doc 09 and its failure notes.",
        ),
        (
            "Seven tabs",
            "System context, Layers, Components, Data flow, Data model, Call flows, Deployment; "
            "draw.io download.",
        ),
    ),
    (
        "Flow list with LLM usage chips",
        "CF-05 Ranking sequence diagram",
        "Failure behaviour and doc anchor",
    ),
)
CALL_FLOW_PINS = ((268, 260), (578, 246), (598, 733))


def view(name: str, pins: tuple[Pixel, ...], lines: tuple) -> Elements:
    return view_slide(placed_view(name), pins, lines)


UI_SLIDES: tuple[tuple[str, Elements], ...] = (
    ("FlameScope - live demo", title_slide()),
    ("She needs PSI evidence for a lunar habitat in an afternoon.", user_slide()),
    ("Ten stops, three minutes, every challenge objective covered.", demo_map_slide()),
    (
        "Overview maps 2,003 PSI test runs against the lunar envelope.",
        view("overview-scatter", OVERVIEW_PINS, OVERVIEW.lines()),
    ),
    (
        "The lunar preset re-ranks instantly, with no AI at query time.",
        view("ranking-lunar", RANKING_PINS, RANKING.lines()),
    ),
    (
        "Every score opens its rationale, its source and its origin.",
        view("ranking-evidence", EVIDENCE_PINS, EVIDENCE.lines()),
    ),
    (
        "The detail card links every stated fact to its PSI source.",
        view("detail-summary", DETAIL_PINS, DETAIL.lines()),
    ),
    (
        "Test runs page through every row of the PSI experimental table.",
        view("detail-runs-pager", DETAIL_RUNS_PINS, DETAIL_RUNS.lines()),
    ),
    (
        "Explorer filters the catalog by fuel, atmosphere, hardware, phenomenon.",
        view("explorer", EXPLORER_PINS, EXPLORER),
    ),
    (
        "Compare marks same and different with icons, not colour alone.",
        view("compare-matrix", COMPARE_PINS, COMPARE.lines()),
    ),
    (
        "The narrative is cited and verified; lineage shows shared hardware.",
        view("compare-lineage", LINEAGE_PINS, LINEAGE),
    ),
    (
        "Scenario Lab measures coverage and bounds gravity instead of guessing.",
        view("scenario-lunar", SCENARIO_PINS, SCENARIO.lines()),
    ),
    (
        "Seven investigations hold 840 runs close to her habitat.",
        view("scenario-matches", MATCHES_PINS, MATCHES.lines()),
    ),
    (
        "Explain cites exact test rows; the export carries the same runs.",
        view("scenario-explain", SCENARIO_EXPLAIN_PINS, SCENARIO_EXPLAIN.lines()),
    ),
    (
        "Data Extract builds model-ready tables with provenance columns.",
        view("extract", EXTRACT_PINS, EXTRACT.lines()),
    ),
    ("Every column is defined; every export records filters and rubric.", dictionary_slide()),
    (
        "Safety Tech maps forty sourced findings to equipment decisions.",
        view("safety-tech", SAFETY_PINS, SAFETY.lines()),
    ),
    (
        "Ask streams a cited answer and removes unsupported sentences.",
        view("ask-answer", ASK_PINS, ASK.lines()),
    ),
    (
        "Earth Apps lists curated terrestrial spin-offs by sector.",
        view("earth", EARTH_PINS, EARTH.lines()),
    ),
    (
        "The Architecture page renders the design with live status.",
        view("arch-components", ARCHITECTURE_PINS, ARCHITECTURE.lines()),
    ),
    (
        "All thirteen call flows are browsable, with LLM usage marked.",
        view("arch-flow", CALL_FLOW_PINS, CALL_FLOWS),
    ),
)

__all__ = ["ASK_QUESTION", "UI_SLIDES"]
