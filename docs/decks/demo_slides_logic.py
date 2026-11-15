"""Backend slides of the FlameScope demo deck, part 2: scoring, scenario maths, retrieval,
gaps, design system, operations, tests, data state, next steps and questions (docs 08 to 13)."""

from __future__ import annotations

import itertools

from build_pitch import blend
from deck_style import (
    ACCENT,
    AMBER,
    BODY,
    BODY_MUTED,
    BORDER_STRONG,
    CONTENT_TOP_IN,
    CONTENT_WIDTH_IN,
    COOL,
    FAINT,
    KICKER,
    LABEL,
    MARGIN_IN,
    MONO,
    MUTED,
    NBSP,
    RIGHT_EDGE_IN,
    ROSE,
    SMALL_MUTED,
    SUCCESS,
    SURFACE,
    SURFACE_RAISED,
    TEXT,
    VIOLET,
    Box,
    Card,
    Mark,
    Node,
    Paragraphs,
    Table,
    Text,
    TextStyle,
)
from demo_slides_system import Link, card_with_text, note
from pptx.enum.text import PP_ALIGN

Elements = tuple[object, ...]
FORMULA = TextStyle(14, COOL, font=MONO)

# --- rubric and presets (doc 08 sections 1 and 3) -------------------------------------------

RUBRIC_ROWS = (
    ("Habitat relevance · 0.4 · O1", "Modeling value · 0.3 · O2", "Controls value · 0.3 · O3"),
    ("fuel_realism 0.25", "quantitative_outputs 0.25", "detection 0.25"),
    ("atmosphere_match 0.25", "parameter_sweep 0.25", "suppression 0.25"),
    ("flow_regime 0.15", "geometry_definition 0.15", "material_screening 0.20"),
    ("phenomenon 0.20", "data_accessibility 0.20", "post_fire 0.15"),
    ("gravity_bounding 0.15", "model_validation 0.15", "hardware_heritage 0.15"),
)
PRESET_ROWS = (
    ("Preset", "Lenses H/M/C", "Criterion emphasis"),
    ("balanced", "0.4 / 0.3 / 0.3", "rubric defaults"),
    (
        "lunar_habitat",
        "0.6 / 0.2 / 0.2",
        "atmosphere_match .35, fuel_realism .25, gravity_bounding .20, "
        "phenomenon .15, flow_regime .05",
    ),
    (
        "spacecraft_cabin",
        "0.5 / 0.2 / 0.3",
        "flow_regime, fuel_realism, phenomenon .25 each; "
        "atmosphere_match .15, gravity_bounding .10",
    ),
    ("modeler", "0.2 / 0.6 / 0.2", "rubric defaults within lenses"),
    (
        "equipment_designer",
        "0.2 / 0.2 / 0.6",
        "detection .30, suppression .30, material_screening .16, "
        "post_fire .12, hardware_heritage .12",
    ),
)


def rubric_slide() -> Elements:
    width = CONTENT_WIDTH_IN / 3
    return (
        Table(
            Box(MARGIN_IN, CONTENT_TOP_IN, CONTENT_WIDTH_IN, 2.1),
            RUBRIC_ROWS,
            (width,) * 3,
            14,
            0.35,
        ),
        Table(Box(MARGIN_IN, 3.8, CONTENT_WIDTH_IN, 2.9), PRESET_ROWS, (2.1, 1.6, 8.43), 12, 0.4),
    )


# --- scoring formulas and worked example (doc 08 sections 2 and 6) --------------------------

SCORE_FORMULAS = (
    ("Formulas (doc 08 section 2)", KICKER),
    ("N = criteria with a value; null = no evidence", FORMULA),
    ("lens_score = 20 * Σ_N w·v / Σ_N w", FORMULA),
    ("confidence = Σ_N w", FORMULA),
    ("contribution = 20 * w·v / Σ_N w", FORMULA),
    ("overall = Σ W·lens_score / Σ W", FORMULA),
    (
        "Weights are normalized; explicit weights override the preset, which overrides the "
        "rubric. "
        "Order: score, then confidence, then acronym; null scores last.",
        BODY_MUTED,
    ),
)
WORKED_ROWS = (
    ("Habitat criterion", "w", "v", "w·v"),
    ("fuel_realism", "0.25", "5", "1.25"),
    ("atmosphere_match", "0.25", "3", "0.75"),
    ("flow_regime", "0.15", "null", "-"),
    ("phenomenon", "0.20", "4", "0.80"),
    ("gravity_bounding", "0.15", "2", "0.30"),
    ("Σ over N", "0.85", "", "3.10"),
)
WORKED_RESULT = "20 * 3.10 / 0.85 = 72.94 → 72.9 · confidence 0.85 (test_ranking_aggregate)"
LIVE_SCORE = (
    ("Live on this stack: FLEX, lunar_habitat", LABEL),
    (
        "All five habitat criteria have evidence (fuel 3, atmosphere 5, flow 3, phenomenon 5, "
        f"gravity 3): 20{NBSP}*{NBSP}4.0{NBSP}/{NBSP}1.0 = 80, confidence 1.0 - slide 5.",
        BODY,
    ),
)


def formulas_slide() -> Elements:
    return (
        *card_with_text(Box(MARGIN_IN, CONTENT_TOP_IN, 5.9, 3.4), SCORE_FORMULAS),
        *card_with_text(Box(MARGIN_IN, 5.1, 5.9, 1.6), LIVE_SCORE),
        Table(Box(6.8, CONTENT_TOP_IN, 5.93, 2.9), WORKED_ROWS, (2.6, 1.0, 1.0, 1.33), 14, 0.4),
        Text(Box(6.8, 4.55, 5.93, 0.7), WORKED_RESULT, TextStyle(16, ACCENT, True)),
    )


# --- scenario maths (doc 08 section 4) ------------------------------------------------------

SCENARIO_FORMULAS = (
    ("Distance (doc 08 section 4.2)", KICKER),
    ("num_d = min(1, |s_d - c_d| / (max_d - min_d))", FORMULA),
    ("num_d = 1 when the run has no value", FORMULA),
    ("fuel: 0 material · 0.3 class · 0.6 phase · 1", FORMULA),
    ("distance = Σ w_d·num_d / Σ w_d", FORMULA),
    ("similarity = 1 - distance", FORMULA),
    (
        "Weights o2 0.35, pressure 0.25, flow 0.15, fuel 0.25; unset dimensions drop out. "
        "Gravity is "
        "never in the distance (ADR-08). Aggregate runs count 0 inside their stated range.",
        BODY_MUTED,
    ),
)
DISTANCE_ROWS = (
    ("Dimension", "Scenario", "Run", "Range", "num", "w·num"),
    ("o2_fraction", "0.34", "0.21", "0.10-0.85", "0.1733", "0.0607"),
    ("pressure_kpa", "56.5", "101.3", "50-101.3", "0.8733", "0.2183"),
    ("flow_speed_cm_s", "10", "20", "0-60", "0.1667", "0.0250"),
    ("fuel", "PMMA", "PMMA", "-", "0", "0"),
)
SCENARIO_RULES = (
    ("distance 0.3040 → similarity 0.696 (test_scenario_distance)", TextStyle(16, ACCENT, True)),
    (
        "Coverage: covered inside [min, max], extrapolated outside, no_data without values; "
        "gravity "
        "is covered only within 0.02 g of a run.",
        BODY,
    ),
    (
        "Investigation similarity = best run; matching_runs = runs at 0.6 or more, which is also "
        "what the scenario_id export keeps.",
        BODY,
    ),
)


def scenario_math_slide() -> Elements:
    return (
        *card_with_text(Box(MARGIN_IN, CONTENT_TOP_IN, 5.9, 5.2), SCENARIO_FORMULAS),
        Table(
            Box(6.8, CONTENT_TOP_IN, 5.93, 2.0),
            DISTANCE_ROWS,
            (1.55, 0.85, 0.75, 1.12, 0.83, 0.83),
            13,
            0.4,
        ),
        Paragraphs(Box(6.8, 3.75, 5.93, 2.95), SCENARIO_RULES),
    )


# --- hybrid retrieval and the Ask stream (doc 05 section 10, CF-09) -------------------------

RETRIEVAL_NODES = (
    ("Embed question", "LLMGateway.embed", VIOLET),
    ("keyword_search", "tsvector, every hit", AMBER),
    ("fuse_ranks", "RRF, k = 60, top_k 8", ACCENT),
    ("InsightQAAgent", "streamed text", VIOLET),
    ("CitationVerifier", "drops unsupported", SUCCESS),
)
SSE_ROWS = (
    ("event", "data"),
    ("meta", "request_id, retrieved chunks and fused scores"),
    ("token", "text deltas (many)"),
    ("citations", "verified sentences with SourceRefs, dropped count"),
    ("related", "investigations to open"),
    ("done | error", "status ok | code and message (terminal)"),
)
RETRIEVAL_NOTES = (
    ("Thresholds", LABEL),
    (
        "A vector hit counts only at cosine ≥ MIN_VECTOR_SIMILARITY: 0.2 for mock, 0.55 for "
        "ollama (215 chunks): best on-corpus chunk 0.694-0.838, best off-corpus 0.413-0.490.",
        BODY,
    ),
    ("Fusion", LABEL),
    ("RRF adds 1 / (60 + rank) per list: the live meta event scores the top chunk 0.0325.", BODY),
    ("Nothing above threshold: the fixed sentence, no LLM call.", BODY_MUTED),
)
NODE_GAP_IN = 0.3


def retrieval_slide() -> Elements:
    width = (CONTENT_WIDTH_IN - (len(RETRIEVAL_NODES) - 1) * NODE_GAP_IN) / len(RETRIEVAL_NODES)
    boxes = [
        Box(MARGIN_IN + i * (width + NODE_GAP_IN), 1.6, width, 0.85)
        for i in range(len(RETRIEVAL_NODES))
    ]
    vector = Box(boxes[1].left, 2.65, width, 0.85)
    nodes = (
        Node(box, title, detail, colour, 13)
        for box, (title, detail, colour) in zip(boxes, RETRIEVAL_NODES, strict=True)
    )
    return (
        *nodes,
        Node(vector, "vector_search", "pgvector cosine", AMBER, 13),
        *(Link(source, target) for source, target in itertools.pairwise(boxes)),
        Link(boxes[0], vector),
        Link(vector, boxes[2]),
        Table(Box(MARGIN_IN, 3.8, 6.0, 2.6), SSE_ROWS, (1.6, 4.4), 14, 0.42),
        Paragraphs(Box(6.9, 3.8, RIGHT_EDGE_IN - 6.9, 2.9), RETRIEVAL_NOTES),
    )


# --- gaps: partial gravity and the parameter grid (doc 08 section 5) ------------------------

OXYGEN_BINS, PRESSURE_BINS = 18, 9  # 0.10-1.00 by 0.05, 20-110 kPa by 10
ENVELOPE_FIRST_OXYGEN_BIN, ENVELOPE_LAST_PRESSURE_BIN = 4, 5  # 0.30 and the 70-80 kPa bin
GRID_LEFT, GRID_TOP, CELL_WIDTH, CELL_HEIGHT = 6.15, 1.65, 0.34, 0.38
# (oxygen bin, pressure bin) cells covered by at least one run on the live stack (2026-11-15),
# as computed by services/safety_tech.py; the other 116 cells form the one gap region.
TESTED_CELLS = frozenset(
    {(0, 8), (5, 3), (5, 7), (5, 8), (6, 3), (6, 7), (6, 8), (7, 8), (8, 3), (8, 8), (9, 8)}
    | {(10, 3), (10, 8), (14, 2), (14, 3), (14, 7), (14, 8), (15, 3)}
    | {(column, row) for column in range(1, 5) for row in range(2, 9)}
)
TESTED_FILL = blend(COOL, SURFACE, 0.45)
ENVELOPE_FILL = blend(ACCENT, SURFACE, 0.45)
GAP_TEXT = (
    ("No partial-gravity data", LABEL),
    (
        "PSI holds fire data at 0 g and 1 g only. FlameScope states the gap, uses them as bounds, "
        "names E-FIELD Flames as the analogue and LUCI and FM2 as future data.",
        BODY,
    ),
    ("Parameter-space gaps", LABEL),
    (
        "A cell is a gap when no run's oxygen and pressure spans both overlap it. Gaps join into "
        "4-connected regions, envelope regions first: param_gap_<n>.",
        BODY,
    ),
    ("Today", LABEL),
    (
        "2,003 runs cover 46 of 162 cells; the other 116 form one region that intersects the "
        "lunar envelope. No run lies between 0 g and 1 g.",
        BODY,
    ),
)


def cell_fill(column: int, row: int) -> str:
    if (column, row) in TESTED_CELLS:
        return TESTED_FILL
    in_envelope = column >= ENVELOPE_FIRST_OXYGEN_BIN and row <= ENVELOPE_LAST_PRESSURE_BIN
    return ENVELOPE_FILL if in_envelope else SURFACE_RAISED


def grid_cell(column: int, row: int) -> Mark:
    fill = cell_fill(column, row)
    top = GRID_TOP + (PRESSURE_BINS - 1 - row) * CELL_HEIGHT
    box = Box(GRID_LEFT + column * CELL_WIDTH, top, CELL_WIDTH - 0.03, CELL_HEIGHT - 0.03)
    return Mark(box, fill, border=None)


def gap_grid() -> Elements:
    cells = (
        grid_cell(c, r) for c, r in itertools.product(range(OXYGEN_BINS), range(PRESSURE_BINS))
    )
    bottom = GRID_TOP + PRESSURE_BINS * CELL_HEIGHT
    axis = TextStyle(12, FAINT)
    return (
        *cells,
        Text(Box(GRID_LEFT, bottom + 0.08, 3.0, 0.3), "O2 0.10", axis),
        Text(
            Box(GRID_LEFT + 3.1, bottom + 0.08, 3.0, 0.3),
            "1.00",
            TextStyle(12, FAINT, align=PP_ALIGN.RIGHT),
        ),
        Text(
            Box(GRID_LEFT - 0.95, GRID_TOP, 0.9, 0.3),
            "110 kPa",
            TextStyle(12, FAINT, align=PP_ALIGN.RIGHT),
        ),
        Text(
            Box(GRID_LEFT - 0.95, bottom - 0.3, 0.9, 0.3),
            "20 kPa",
            TextStyle(12, FAINT, align=PP_ALIGN.RIGHT),
        ),
        *legend_row(bottom + 0.5, TESTED_FILL, "Tested cell (46)"),
        *legend_row(
            bottom + 0.82, ENVELOPE_FILL, "Untested, lunar envelope (O2 ≥ 0.30, ≤ 70.3 kPa)"
        ),
        *legend_row(bottom + 1.14, SURFACE_RAISED, "Untested elsewhere (116 untested in all)"),
    )


def legend_row(top: float, fill: str, label: str) -> Elements:
    return (
        Mark(Box(GRID_LEFT, top, 0.3, 0.25), fill, border=BORDER_STRONG),
        Text(Box(GRID_LEFT + 0.4, top - 0.03, 6.0, 0.3), label, SMALL_MUTED),
    )


def gaps_slide() -> Elements:
    return (*card_with_text(Box(MARGIN_IN, CONTENT_TOP_IN, 4.5, 5.2), GAP_TEXT), *gap_grid())


# --- UI design system (doc 10 section 2) ----------------------------------------------------

TOKENS = (
    ("--bg", "0A0E14"),
    ("--surface-1", "10151D"),
    ("--surface-2", "161C26"),
    ("--border", "232B38"),
    ("--text", "E6EAF0"),
    ("--text-muted", "94A3B8"),
    ("--accent", "F97316"),
    ("--cool", "38BDF8"),
    ("--success", "34D399"),
    ("--warning", "FBBF24"),
    ("--danger", "F87171"),
    ("--liquid", "A78BFA"),
)
TOKENS_PER_ROW = 6
SWATCH_WIDTH_IN, SWATCH_GAP_IN = 1.85, 0.206
DESIGN_RULES = (
    ("Binding quality rules", LABEL),
    (
        "Dark only; no pure black or white. Text contrast at least 4.5:1; meaning never by colour "
        "alone (icon or label too).",
        BODY,
    ),
    (
        "Every data panel has loading, empty, error-with-retry and data states. Numbers carry "
        "units; "
        "oxygen in percent.",
        BODY,
    ),
    (
        "Inter for text, JetBrains Mono for numbers and IDs; 4 px grid, 10 px card radius. Focus "
        "ring in accent; / focuses search; Esc closes drawers; 150 ms motion, reduced-motion "
        "aware.",
        BODY,
    ),
    (
        "Fuel phases: gas #38BDF8, liquid #A78BFA, solid #F97316. Lenses: habitat orange, "
        "modeling blue, controls green. test_e2e_10 runs an axe-core contrast check.",
        BODY_MUTED,
    ),
)


def swatch(index: int, token: tuple[str, str]) -> Elements:
    name, colour = token
    row, column = divmod(index, TOKENS_PER_ROW)
    left = MARGIN_IN + column * (SWATCH_WIDTH_IN + SWATCH_GAP_IN)
    top = CONTENT_TOP_IN + row * 1.25
    return (
        Mark(Box(left, top, SWATCH_WIDTH_IN, 0.5), colour, border=BORDER_STRONG),
        Text(
            Box(left, top + 0.55, SWATCH_WIDTH_IN, 0.45),
            f"{name}\n#{colour}",
            TextStyle(12, MUTED, font=MONO),
        ),
    )


def design_slide() -> Elements:
    swatches = itertools.chain.from_iterable(itertools.starmap(swatch, enumerate(TOKENS)))
    return (
        *swatches,
        *card_with_text(Box(MARGIN_IN, 4.05, CONTENT_WIDTH_IN, 2.65), DESIGN_RULES, SURFACE),
    )


# --- deployment and Makefile (doc 11, CF-01) ------------------------------------------------

MAKE_ROWS = (
    ("Group", "Makefile targets"),
    ("Setup", "help, doctor, ollama-pull, env, venv, ui-install"),
    ("Quality", "lint, fmt"),
    ("Stack", "build, deploy, status, logs, restart, undeploy, clean, open"),
    ("Data", "ingest-seed, ingest-harvest"),
    ("Tests", "test-unit, test-integration, test-e2e, test, all"),
    ("Optional", "helm-template, helm-deploy, helm-undeploy"),
)
DEPLOY_STEPS = (
    ("make deploy (CF-01)", LABEL),
    (
        "env → check Ollama models → db healthy → ingest job (migrate + seed) → api and ui → wait "
        "for /api/v1/ready → print URLs.",
        BODY,
    ),
    ("Timing on this Mac", LABEL),
    (
        "Live deploy about 2-3 min including scoring; mock about 25 s (last measured, not "
        "re-run). Last seed ingest_run on this stack: 6.4 s.",
        BODY,
    ),
    ("Switch to mock", LABEL),
    (
        "LLM_PROVIDER=mock and EMBED_PROVIDER=mock in .env, then make undeploy && make deploy.",
        BODY,
    ),
)


def deployment_slide() -> Elements:
    table = Table(Box(MARGIN_IN, CONTENT_TOP_IN, 6.6, 3.4), MAKE_ROWS, (1.4, 5.2), 14, 0.45)
    footer = (
        "26 targets, stock macOS make 3.81; wait loops in deploy/scripts/wait-for.sh; Helm "
        "chart optional."
    )
    return (
        table,
        Text(Box(MARGIN_IN, 5.3, 6.6, 1.3), footer, BODY_MUTED),
        *card_with_text(Box(7.5, CONTENT_TOP_IN, RIGHT_EDGE_IN - 7.5, 5.2), DEPLOY_STEPS),
    )


# --- testing pyramid (doc 12, tests/reports) ------------------------------------------------

PYRAMID = (
    ("End to end · 108", "Playwright, every route and journey, 1440x900 and 1024x768", 5.0, COOL),
    (
        "Integration · 247",
        "build, deploy, database, ingestion, all 24 endpoints, p95 latency",
        8.0,
        SUCCESS,
    ),
    (
        "Unit · 1,136 pytest + 225 Vitest",
        "pure logic, schemas, agents on MockLlm, services with fakes, UI components",
        11.6,
        ACCENT,
    ),
)
PYRAMID_TOP, PYRAMID_LAYER_HEIGHT, PYRAMID_GAP = 1.6, 1.15, 0.15
TEST_NOTE = (
    "Counts: tests/reports/{unit,integration,e2e}.xml of the last clean make test (2026-11-14; "
    "1 README xfail not counted) and Vitest. All suites force LLM_PROVIDER=mock, except the "
    "optional test_21_llm_ollama. p95: /insights/gaps 153 ms, all else under 70 ms."
)


def pyramid_layer(index: int, layer: tuple[str, str, float, str]) -> Elements:
    title, detail, width, colour = layer
    left = MARGIN_IN + (CONTENT_WIDTH_IN - width) / 2
    box = Box(
        left,
        PYRAMID_TOP + index * (PYRAMID_LAYER_HEIGHT + PYRAMID_GAP),
        width,
        PYRAMID_LAYER_HEIGHT,
    )
    return (Node(box, title, detail, colour, title_size=18),)


def tests_slide() -> Elements:
    layers = itertools.chain.from_iterable(itertools.starmap(pyramid_layer, enumerate(PYRAMID)))
    return (*layers, note(5.6, TEST_NOTE, 1.1))


# --- current data state, data sources, next steps, questions --------------------------------

STATS = (
    ("25", "investigations"),
    ("2,003", "test runs"),
    ("355", "publications"),
    ("40", "findings"),
    ("215", "indexed chunks"),
    ("6", "hardware"),
)
DATA_REAL = (
    ("What is in the catalog", LABEL),
    (
        "Fuel phases gas 9, liquid 6, solid 8. Catalog oxygen 0.12-0.85, pressure "
        "25.3-506.6 kPa, flow 0-85.3 cm/s.",
        BODY,
    ),
    (
        "1,989 runs at 0 g, 11 at 1 g (9 SAFFIRE-II reference burns, 2 PSI-142), 3 without a "
        "stated gravity; 25 runs are aggregate ranges.",
        BODY,
    ),
)
DATA_OPEN = (
    ("What is still open", LABEL),
    (
        "Every card is reviewed: false - curated from sources, not yet signed off by a person "
        "(OI-06). The 375 criterion ratings come from the scorer at seed time.",
        BODY,
    ),
    (
        "No run between 0 g and 1 g; 116 of 162 oxygen-pressure cells untested. Canadian Space "
        "Agency sources were checked and hold no usable combustion data.",
        BODY,
    ),
)
STAT_GAP_IN = 0.2


def stat_tile(index: int, stat: tuple[str, str]) -> Elements:
    value, label = stat
    width = (CONTENT_WIDTH_IN - (len(STATS) - 1) * STAT_GAP_IN) / len(STATS)
    box = Box(MARGIN_IN + index * (width + STAT_GAP_IN), CONTENT_TOP_IN, width, 1.4)
    return (
        Card(box),
        Text(
            Box(box.left + 0.2, box.top + 0.15, width - 0.3, 0.7),
            value,
            TextStyle(32, ACCENT, True, MONO),
        ),
        Text(Box(box.left + 0.2, box.top + 0.9, width - 0.3, 0.35), label, TextStyle(13, MUTED)),
    )


def data_state_slide() -> Elements:
    tiles = itertools.chain.from_iterable(itertools.starmap(stat_tile, enumerate(STATS)))
    half = (CONTENT_WIDTH_IN - 0.3) / 2
    return (
        *tiles,
        Text(
            Box(MARGIN_IN, 3.0, CONTENT_WIDTH_IN, 0.3),
            "Live GET /api/v1/meta/stats and the database, 2026-11-14 (ingest_mode seed)",
            SMALL_MUTED,
        ),
        *card_with_text(Box(MARGIN_IN, 3.45, half, 3.25), DATA_REAL, SURFACE),
        *card_with_text(Box(MARGIN_IN + half + 0.3, 3.45, half, 3.25), DATA_OPEN, SURFACE),
    )


SOURCE_NODES = (
    ("PSI repository records", "geode-py JSON API", COOL),
    ("PSI experimental tables", "PSI-<n>_Experimental table_*.csv", COOL),
    ("NTRS, DOIs, NASA pages", "publications, findings", MUTED),
)
SEED_NODE = ("25 seed files", "src/data/seed/investigations/", AMBER)
LOAD_NODE = ("make deploy: seed mode", "normalize → link → score → index", ROSE)
SOURCE_RULES = (
    ("Coverage: 25 files for 24 PSI records", LABEL),
    (
        "All 24 PSI Combustion Science records: 20 flight investigations (PSI-47 holds DAFT and "
        "DAFT-2, seeded as two files) and 5 ground studies keyed PSI-60, -62, -115, -117, -142.",
        BODY,
    ),
    ("Runs", LABEL),
    (
        "One run per table row or stated test point for 16 flight investigations. Ground "
        "studies list no tests; PSI-62, -115 and -142 carry 5 aggregate runs from their records.",
        BODY,
    ),
    ("Gravity and sourcing rules", LABEL),
    (
        "0 g where PSI labels a Microgravity Investigation; 1 g only where a source states a "
        "normal-gravity test. Every value cites its record, table row or paper; unknown is null.",
        BODY,
    ),
)
SOURCE_NODE_HEIGHT_IN = 0.85


def sources_slide() -> Elements:
    sources = [
        Box(MARGIN_IN, CONTENT_TOP_IN + index * 1.1, 3.4, SOURCE_NODE_HEIGHT_IN)
        for index in range(len(SOURCE_NODES))
    ]
    seed = Box(4.3, 2.6, 3.0, SOURCE_NODE_HEIGHT_IN)
    load = Box(4.3, 4.3, 3.0, SOURCE_NODE_HEIGHT_IN)
    nodes = (
        Node(box, title, detail, colour, 13)
        for box, (title, detail, colour) in zip(sources, SOURCE_NODES, strict=True)
    )
    return (
        *nodes,
        Node(seed, *SEED_NODE, 13),
        Node(load, *LOAD_NODE, 13),
        *(Link(source, seed) for source in sources),
        Link(seed, load),
        Text(
            Box(MARGIN_IN, 5.55, 6.7, 0.75),
            "Seed files hold each value with its source; make deploy loads them offline.",
            BODY_MUTED,
        ),
        *card_with_text(Box(7.6, CONTENT_TOP_IN, RIGHT_EDGE_IN - 7.6, 5.2), SOURCE_RULES),
    )


NEXT_STEPS = (
    (
        "Human review",
        "Have curators sign off each card and its ratings (reviewed: true); overrides already "
        "win over any computed value.",
    ),
    (
        "Harvest at scale",
        "Run make ingest-harvest on the nasa-psi bucket with a stronger model, then export-seed "
        "after review (OI-04).",
    ),
    (
        "Partial gravity",
        "Add LUCI and FM2 data when PSI publishes it; the bounding card then gives way to "
        "coverage.",
    ),
    (
        "Wider PSI",
        "Other PSI disciplines: the pipeline keeps discipline as a column (doc 01 section 5).",
    ),
)


def next_card(index: int, step: tuple[str, str]) -> Elements:
    head, text = step
    width = (CONTENT_WIDTH_IN - 0.3) / 2
    row, column = divmod(index, 2)
    box = Box(MARGIN_IN + column * (width + 0.3), CONTENT_TOP_IN + row * 2.7, width, 2.45)
    return card_with_text(
        box,
        ((f"{index + 1}", KICKER), (head, TextStyle(20, TEXT, True)), (text, BODY_MUTED)),
        SURFACE,
    )


def next_slide() -> Elements:
    return tuple(
        itertools.chain.from_iterable(itertools.starmap(next_card, enumerate(NEXT_STEPS)))
    )


REPO_URL = "https://github.com/AyaanAsish/flamescope"


def questions_slide() -> Elements:
    return (
        Card(Box(MARGIN_IN, 2.0, CONTENT_WIDTH_IN, 2.6), SURFACE_RAISED),
        Text(Box(1.0, 2.5, 3.0, 0.4), "Code", TextStyle(16, MUTED)),
        Text(Box(1.0, 2.95, 7.4, 0.5), REPO_URL, TextStyle(20, COOL, font=MONO)),
        Text(
            Box(8.6, 2.85, 3.8, 0.8),
            "Thank you",
            TextStyle(36, ACCENT, True, align=PP_ALIGN.RIGHT),
        ),
        Text(
            Box(MARGIN_IN, 5.0, CONTENT_WIDTH_IN, 1.0),
            "The 7-slide pitch deck is the Space Apps submission; this deck is its detailed "
            "companion.",
            BODY_MUTED,
        ),
    )


LOGIC_SLIDES: tuple[tuple[str, Elements], ...] = (
    ("Three lenses, fifteen criteria and five presets, all in YAML.", rubric_slide()),
    ("Scores are auditable arithmetic: 72.9 in the worked example.", formulas_slide()),
    ("Scenario similarity is a weighted distance: 0.696 in the example.", scenario_math_slide()),
    ("Ask fuses keyword and vector hits, then streams verified sentences.", retrieval_slide()),
    ("Gaps are computed, not hidden: partial gravity and 116 untested cells.", gaps_slide()),
    ("One dark token set keeps every view legible and consistent.", design_slide()),
    ("One Makefile builds, deploys, tests and tears down the stack.", deployment_slide()),
    ("1,716 tests pass across unit, Vitest, integration and end to end.", tests_slide()),
    ("The catalog holds real PSI data: 25 investigations, 2,003 runs.", data_state_slide()),
    ("The data comes from PSI records, experimental tables and NASA reports.", sources_slide()),
    ("Next: human review, a stronger harvest model, partial gravity.", next_slide()),
    ("Questions", questions_slide()),
)
