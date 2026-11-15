"""Backend slides of the FlameScope demo deck, part 1: context, containers, API, data,
ingestion, agents, gateway and the citation verifier (docs 02 to 07)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from deck_style import (
    ACCENT,
    AMBER,
    BODY,
    BODY_MUTED,
    CODE,
    CONTENT_TOP_IN,
    CONTENT_WIDTH_IN,
    COOL,
    EDGE,
    KICKER,
    LABEL,
    MARGIN_IN,
    MUTED,
    RIGHT_EDGE_IN,
    ROSE,
    SMALL_MUTED,
    SUCCESS,
    SURFACE_RAISED,
    VIOLET,
    Box,
    Card,
    Line,
    Node,
    Paragraphs,
    Table,
    Text,
    TextStyle,
)

Elements = tuple[object, ...]
FULL_WIDTH_BOX = Box(MARGIN_IN, 0, CONTENT_WIDTH_IN, 0)
LABEL_WIDTH_IN, LABEL_HEIGHT_IN = 1.8, 0.3


def right(box: Box) -> float:
    return box.left + box.width


def middle(box: Box) -> float:
    return box.top + box.height / 2


def centre(box: Box) -> float:
    return box.left + box.width / 2


@dataclass(frozen=True)
class Link:
    """An arrow between two diagram boxes, chosen by their relative position."""

    source: Box
    target: Box
    colour: str = EDGE
    is_dashed: bool = False

    def endpoints(self) -> tuple[tuple[float, float], tuple[float, float]]:
        if self.target.left >= right(self.source):
            return (right(self.source), middle(self.source)), (
                self.target.left,
                middle(self.target),
            )
        if right(self.target) <= self.source.left:
            return (self.source.left, middle(self.source)), (
                right(self.target),
                middle(self.target),
            )
        if self.target.top >= self.source.bottom:
            return (centre(self.source), self.source.bottom), (
                centre(self.source),
                self.target.top,
            )
        return (centre(self.source), self.source.top), (centre(self.source), self.target.bottom)

    def draw(self, slide: object) -> None:
        start, end = self.endpoints()
        Line(start, end, self.colour, has_head=True, is_dashed=self.is_dashed).draw(slide)


def llm_link(source: Box, target: Box) -> Link:
    return Link(source, target, VIOLET, is_dashed=True)


def card_with_text(box: Box, lines: tuple, fill: str = SURFACE_RAISED) -> Elements:
    inner = Box(box.left + 0.2, box.top + 0.15, box.width - 0.4, box.height - 0.25)
    return (Card(box, fill), Paragraphs(inner, lines))


def note(top: float, text: str, height: float = 0.75) -> Text:
    return Text(Box(MARGIN_IN, top, CONTENT_WIDTH_IN, height), text, BODY_MUTED)


# --- system context (doc 02 section 1) --------------------------------------------------------

USERS = (
    "Professors and students",
    "Aerospace researchers",
    "Habitat and spacecraft engineers",
    "Earth fire-safety practitioners",
)
EXTERNALS = (
    ("NASA PSI website", "links to investigation pages"),
    ("s3://nasa-psi", "harvest metadata and documents"),
    ("DOI resolvers, journals, NTRS", "abstracts and citations"),
    ("Ollama on the Mac host", "extract, score, answer"),
)
ROW_TOPS = (1.6, 2.6, 3.6, 4.6)
CONTEXT_NOTE = (
    "FlameScope reads from PSI and never writes to it. At request time only Ask, the compare "
    "narrative and the scenario explanation leave the containers, and only to Ollama on the "
    "host; in mock mode nothing leaves at all."
)


def context_slide() -> Elements:
    hub = Box(4.95, 2.6, 3.3, 1.75)
    users = [Box(MARGIN_IN, top, 3.6, 0.8) for top in ROW_TOPS]
    externals = [Box(9.1, top, 3.63, 0.8) for top in ROW_TOPS]
    return (
        *(Node(box, name, "user", COOL) for box, name in zip(users, USERS, strict=True)),
        *(
            Node(box, name, detail, MUTED)
            for box, (name, detail) in zip(externals, EXTERNALS, strict=True)
        ),
        Node(hub, "FlameScope", "dashboard + API + agents", ACCENT, title_size=20),
        *(
            Line((right(box), middle(box)), (hub.left, middle(hub)), has_head=True)
            for box in users
        ),
        *(
            Line((right(hub), middle(hub)), (box.left, middle(box)), has_head=True)
            for box in externals[:3]
        ),
        Line(
            (right(hub), middle(hub)),
            (externals[3].left, middle(externals[3])),
            VIOLET,
            True,
            True,
        ),
        note(5.75, CONTEXT_NOTE, 0.9),
    )


# --- containers (doc 02 section 5, doc 11 sections 1-2) -------------------------------------

BROWSER = Box(MARGIN_IN, 1.65, 2.0, 0.95)
UI = Box(3.2, 1.65, 2.6, 0.95)
API = Box(6.4, 1.65, 2.6, 0.95)
DB = Box(9.6, 1.65, 3.13, 0.95)
INGEST = Box(6.4, 3.15, 2.6, 0.95)
PGDATA = Box(9.6, 3.15, 3.13, 0.8)
RAW = Box(9.6, 4.15, 3.13, 0.8)
OLLAMA = Box(3.2, 3.15, 2.6, 0.95)
BUCKET = Box(3.2, 4.3, 2.6, 0.8)
CONTAINER_NOTES = (
    (
        "Compose project flamescope: ui waits for api healthy, api for db healthy; ingest is a "
        "one-shot job (profile job) that runs migrate, then seed.",
        BODY_MUTED,
    ),
    (
        "Images flamescope-api|ingest|ui:local: multi-stage, non-root uid 10001, host "
        "architecture. API_INTERNAL_URL is a build argument of Dockerfile.ui.",
        BODY_MUTED,
    ),
    ("Health checks: pg_isready · GET /api/v1/health · GET /", BODY_MUTED),
)


def containers_slide() -> Elements:
    nodes = (
        Node(BROWSER, "Browser", "localhost:3000", MUTED),
        Node(UI, "ui :3000", "Next.js standalone", COOL),
        Node(API, "api :8000", "FastAPI, uvicorn", SUCCESS),
        Node(DB, "db :5432", "pgvector/pgvector:pg16", AMBER),
        Node(INGEST, "ingest", "one-shot: migrate + seed", ROSE),
        Node(PGDATA, "flamescope_pgdata", "database volume", AMBER),
        Node(RAW, "flamescope_raw", "/data/raw (api read-only)", AMBER),
        Node(OLLAMA, "Ollama on host :11434", "host.docker.internal", VIOLET),
        Node(BUCKET, "s3://nasa-psi", "harvest mode only", MUTED),
    )
    links = (
        Link(BROWSER, UI),
        Link(UI, API),
        Link(API, DB),
        Link(DB, PGDATA),
        Link(INGEST, RAW),
        llm_link(INGEST, OLLAMA),
        Link(INGEST, BUCKET, MUTED, is_dashed=True),
    )
    labels = (
        Text(Box(5.85, 1.3, 1.6, 0.3), "/api/* rewrite", SMALL_MUTED),
        Text(Box(9.05, 1.3, 0.8, 0.3), "SQL", SMALL_MUTED),
    )
    ingest_to_db = Line(
        (right(INGEST), INGEST.top + 0.2), (DB.left, DB.bottom - 0.1), has_head=True
    )
    api_to_ollama = Line((API.left, API.bottom), (right(OLLAMA), OLLAMA.top), VIOLET, True, True)
    notes = Paragraphs(Box(MARGIN_IN, 5.3, CONTENT_WIDTH_IN, 1.4), CONTAINER_NOTES)
    return (*nodes, *links, ingest_to_db, api_to_ollama, *labels, notes)


# --- API layering and errors (doc 02 section 2, doc 05 section 2) ---------------------------

LAYERS = (
    ("Routers · routers/*.py", "validate, call one service, shape", SUCCESS),
    ("Services · services/*.py", "deterministic; nine services", ACCENT),
    ("Repositories · repositories/*.py", "the only code that runs SQL", AMBER),
    ("PostgreSQL + pgvector", "C-DB", AMBER),
)
LAYER_TOPS = (1.6, 2.8, 4.0, 5.2)
ERROR_ROWS = (
    ("HTTP", "code", "When"),
    ("400", "bad_request", "invalid input (ValidationError)"),
    ("404", "not_found", "unknown resource (NotFoundError)"),
    ("422", "validation_error", "schema failure, fields in details"),
    ("502", "llm_unavailable", "provider failed after retries"),
    ("500", "internal_error", "anything else"),
)
API_NOTES = (
    ("Request IDs (NFR-11)", LABEL),
    (
        "X-Request-ID accepted and returned on every response; structlog JSON with ts, level, "
        "logger, request_id, event; passed on to the LLM gateway.",
        BODY,
    ),
    ("A Ranking slider, end to end", LABEL),
    (
        "POST /rank → RankingService.rank → ScoreRepo.all_scores → aggregate() → JSON. No LLM; "
        "test_19 holds p95 under 300 ms.",
        BODY,
    ),
)


def api_slide() -> Elements:
    boxes = [Box(MARGIN_IN, top, 3.7, 0.85) for top in LAYER_TOPS]
    orchestrator = Box(4.6, 2.8, 2.1, 0.85)
    layers = (
        Node(box, title, detail, colour)
        for box, (title, detail, colour) in zip(boxes, LAYERS, strict=True)
    )
    arrows = (Link(source, target) for source, target in itertools.pairwise(boxes))
    envelope = '{"error": {"code", "message", "details", "request_id"}}'
    return (
        *layers,
        *arrows,
        Node(orchestrator, "AgentOrchestrator", "compare, scenario, ask", VIOLET),
        llm_link(boxes[1], orchestrator),
        Table(Box(7.0, CONTENT_TOP_IN, 5.73, 2.2), ERROR_ROWS, (0.6, 1.65, 3.48), 13, 0.36),
        Text(Box(7.0, 3.82, 5.73, 0.3), envelope, CODE),
        Paragraphs(Box(7.0, 4.25, 5.73, 2.45), API_NOTES),
    )


# --- the 24 endpoints (doc 05 section 11) -----------------------------------------------------

ENDPOINT_GROUPS = (
    (
        "Catalog · 8",
        (
            "GET /investigations",
            "GET /investigations/{id}",
            "GET /investigations/{id}/runs",
            "GET /investigations/{id}/variables",
            "GET /investigations/{id}/publications",
            "GET /facets",
            "GET /hardware",
            "GET /projects",
        ),
    ),
    (
        "Health and meta · 6",
        (
            "GET /health",
            "GET /ready",
            "GET /meta/stats",
            "GET /meta/status",
            "GET /meta/rubric",
            "GET /meta/presets",
        ),
    ),
    (
        "Insights and Earth · 3",
        (
            "GET /insights/safety-tech",
            "GET /insights/gaps",
            "GET /earth-applications",
        ),
    ),
    ("Extract · 3", ("POST /extract/preview", "POST /extract/export", "GET /extract/dictionary")),
    (
        "Rank, compare, scenario · 3",
        (
            "POST /rank",
            "POST /compare  (LLM optional)",
            "POST /scenario  (LLM optional)",
        ),
    ),
    ("Ask · 1", ("POST /ask  (SSE, LLM)", "meta, token, citations,", "related, done | error")),
)
ENDPOINT_COLUMNS = ((MARGIN_IN, 4.5), (5.4, 3.6), (9.3, 3.43))
ENDPOINT_ROWS = ((CONTENT_TOP_IN, 2.6), (4.3, 1.75))
ENDPOINT_FOOTER = (
    "Base /api/v1 · OpenAPI /api/v1/openapi.json · Swagger /api/v1/docs · test_18 asserts the "
    "OpenAPI document lists exactly these 24."
)


def endpoint_card(index: int, group: tuple[str, tuple[str, ...]]) -> Elements:
    row, column = divmod(index, len(ENDPOINT_COLUMNS))
    left, width = ENDPOINT_COLUMNS[column]
    top, height = ENDPOINT_ROWS[row]
    title, paths = group
    lines = ((title, LABEL), *((path, CODE) for path in paths))
    return card_with_text(Box(left, top, width, height), lines)


def endpoints_slide() -> Elements:
    order = (0, 1, 2, 3, 4, 5)
    cards = (endpoint_card(slot, ENDPOINT_GROUPS[group]) for slot, group in enumerate(order))
    return (*itertools.chain.from_iterable(cards), note(6.15, ENDPOINT_FOOTER, 0.5))


# --- data model (doc 04) ----------------------------------------------------------------------

CATALOG_ROWS = (
    ("Catalog table", "Holds"),
    ("project", "groupings such as ACME"),
    ("hardware", "CIR, MSG, MDCA, inserts, instruments"),
    ("investigation", "card jsonb, derived ranges, search_tsv"),
    ("investigation_hardware", "role: host, apparatus, instrument"),
    ("fuel", "name, phase, material_class"),
    ("test_run", "geometry, varied, fixed, outcome"),
    ("condition", "o2_fraction, pressure_kpa, gravity_g"),
    ("measurement", "instrument, quantity, units"),
    ("publication", "doi, title, authors, key_findings"),
    ("finding", "statement, category, source"),
)
TABLE_GROUPS = (
    (
        "relevance_score",
        "Key: investigation, lens, criterion, rubric_version. Value 0-5 or null, "
        "evidence, origin.",
    ),
    (
        "chunk",
        "800-1200 characters, 150 overlap; vector(768) HNSW cosine; tsv GIN; 215 rows now.",
    ),
    (
        "earth_application, finding_earth_application, earth_application_investigation",
        "Rows only from the curated earth_applications.yaml.",
    ),
    ("ingest_run, llm_cache", "Audit report per ingestion run; SHA-256-keyed model replies."),
)
GROUP_STEP_IN, GROUP_HEIGHT_IN = 1.1, 0.97
DATA_FOOTER = (
    "Extensions vector and pg_trgm · migration 0001_initial · every fact carries a SourceRef "
    "{kind, uri, title, locator, quote, chunk_id}"
)


def data_model_slide() -> Elements:
    groups = (
        card_with_text(
            Box(7.0, CONTENT_TOP_IN + index * GROUP_STEP_IN, 5.73, GROUP_HEIGHT_IN),
            ((names, CODE), (detail, BODY_MUTED)),
        )
        for index, (names, detail) in enumerate(TABLE_GROUPS)
    )
    catalog = Table(Box(MARGIN_IN, CONTENT_TOP_IN, 6.1, 4.4), CATALOG_ROWS, (2.45, 3.65), 13, 0.4)
    return (catalog, *itertools.chain.from_iterable(groups), note(6.05, DATA_FOOTER, 0.6))


# --- ingestion stages (doc 06) ----------------------------------------------------------------

STAGES = (
    ("discover", "S3 listing", ROSE),
    ("harvest", "allowed files", ROSE),
    ("parse", "ParsedDoc", ROSE),
    ("extract", "LLM agent", VIOLET),
    ("normalize", "taxonomy, tags", ROSE),
    ("link", "upserts", ROSE),
    ("score", "LLM agent", VIOLET),
    ("index", "chunks, embed", ROSE),
    ("review", "report", ROSE),
)
STAGE_GAP_IN = 0.12
STAGE_TOP_IN, STAGE_HEIGHT_IN = 1.6, 1.0
NORMALIZE_INDEX, EXTRACT_INDEX = 4, 3
MODE_ROWS = (
    ("Mode", "Network", "LLM", "Input", "Started by"),
    ("seed", "none", "only for missing scores", "src/data/seed/**", "make deploy, ingest-seed"),
    (
        "harvest",
        "S3 unsigned, DOIs",
        "required: ollama",
        "s3://nasa-psi/<PSI_PREFIX>",
        "make ingest-harvest",
    ),
)
EXPORT_NOTE = (
    "flamescope-ingest export-seed writes reviewed cards back to src/data/seed/investigations/, "
    "so a curated harvest becomes the offline dataset."
)


def stage_box(index: int) -> Box:
    width = (CONTENT_WIDTH_IN - (len(STAGES) - 1) * STAGE_GAP_IN) / len(STAGES)
    return Box(MARGIN_IN + index * (width + STAGE_GAP_IN), STAGE_TOP_IN, width, STAGE_HEIGHT_IN)


def ingestion_slide() -> Elements:
    boxes = [stage_box(index) for index in range(len(STAGES))]
    stages = (
        Node(box, f"{number} {name}", detail, colour, title_size=13)
        for number, (box, (name, detail, colour)) in enumerate(zip(boxes, STAGES, strict=True), 1)
    )
    seed = Box(boxes[NORMALIZE_INDEX].left - 0.4, 3.0, 2.2, 0.75)
    overrides = Box(boxes[EXTRACT_INDEX].left - 2.0, 3.0, 2.3, 0.75)
    return (
        *stages,
        *(Link(source, target) for source, target in itertools.pairwise(boxes)),
        Node(seed, "seed files", "enter at normalize", AMBER),
        Line(
            (centre(seed), seed.top),
            (centre(boxes[NORMALIZE_INDEX]), STAGE_TOP_IN + STAGE_HEIGHT_IN),
            AMBER,
            True,
            True,
        ),
        Node(overrides, "overrides/*.yaml", "after extract, normalize", ACCENT),
        Line(
            (right(overrides), overrides.top),
            (centre(boxes[EXTRACT_INDEX]), STAGE_TOP_IN + STAGE_HEIGHT_IN),
            ACCENT,
            True,
            True,
        ),
        Table(
            Box(MARGIN_IN, 4.05, CONTENT_WIDTH_IN, 1.5),
            MODE_ROWS,
            (1.3, 2.3, 2.6, 3.2, 2.73),
            13,
            0.4,
        ),
        note(5.75, EXPORT_NOTE, 0.75),
    )


IDEMPOTENCY_ROWS = (
    ("Stage", "Skipped while this key is unchanged"),
    ("1 discover", "bucket listing ETag set"),
    ("2 harvest", "S3 ETag per key"),
    ("3 parse", "SHA-256 of the raw file"),
    ("4 extract", "hash of parsed docs + prompt version"),
    ("5 normalize", "hash of the input card"),
    ("6 link", "upsert on natural keys"),
    ("7 score", "investigation, lens, criterion, rubric_version"),
    ("8 index", "doc_ref, char_start, char_end + chunk text"),
    ("9 review", "earth candidates: prompt version + input"),
)
INGEST_RULES = (
    ("Overrides always win", LABEL),
    (
        "src/data/overrides/<acronym>.yaml is deep-merged after extract and again after "
        "normalize; overridden scores are stored with origin override.",
        BODY,
    ),
    ("Never bulk-downloaded", LABEL),
    (
        "Documents up to 25 MB, tables up to 5 MB (20 max), 300 MB per investigation; video, "
        "images and archives stay in the manifest.",
        BODY,
    ),
    ("Failures", LABEL),
    (
        "One investigation failing leaves the others running (status partial); a database "
        "error rolls back and stops (failed). --force reruns a stage.",
        BODY,
    ),
)


def idempotency_slide() -> Elements:
    table = Table(Box(MARGIN_IN, CONTENT_TOP_IN, 6.9, 4.2), IDEMPOTENCY_ROWS, (1.7, 5.2), 14, 0.42)
    rules = card_with_text(Box(7.8, CONTENT_TOP_IN, RIGHT_EDGE_IN - 7.8, 5.2), INGEST_RULES)
    return (table, *rules)


# --- agents, orchestrator, gateway, verifier (doc 07) ---------------------------------------

AGENT_ROWS = (
    ("Agent", "Prompt", "Runs in", "Output (Pydantic-validated)"),
    ("ExtractorAgent", "extractor@1", "harvest: extract", "card draft; quotes must be substrings"),
    ("ScorerAgent", "scorer@1", "ingest: score", "0-5 or null per criterion, with evidence"),
    ("ComparatorAgent", "comparator@1", "POST /compare", "4 to 7 sentences with fact_ids"),
    (
        "ScenarioInterpreterAgent",
        "scenario_interpreter@1",
        "POST /scenario",
        "sentences with fact_ids, caveats",
    ),
    (
        "InsightQAAgent",
        "insight_qa@2",
        "POST /ask, streamed",
        "sentences ending in [c:ID] / [f:ID]",
    ),
    ("EarthAppsAgent", "earth_apps@1", "harvest: review", "candidates to earth_candidates.json"),
)
ORCHESTRATOR_TEXT = (
    "AgentOrchestrator.run(name, payload, *, stream): validate the input → render the prompt file "
    "(front matter, ## System, ## User) → run the ADK LlmAgent through a Runner with an "
    "InMemorySessionService, one throwaway session → validate the output, retrying up to 2 "
    "times with {{validation_feedback}} → log agent, prompt_version, provider, model, latency_ms, "
    "cache_hit, retries → raise LLMError so the caller's fallback applies."
)


def agents_slide() -> Elements:
    table = Table(
        Box(MARGIN_IN, CONTENT_TOP_IN, CONTENT_WIDTH_IN, 3.4),
        AGENT_ROWS,
        (2.75, 2.45, 2.4, 4.53),
        13,
        0.45,
    )
    return (
        table,
        Paragraphs(
            Box(MARGIN_IN, 5.0, CONTENT_WIDTH_IN, 1.7),
            (
                ("No tools, no database access, one prompt file each", LABEL),
                (ORCHESTRATOR_TEXT, BODY),
            ),
        ),
    )


GATEWAY_FEATURES = (
    ("LLMGateway (doc 07 section 6)", KICKER),
    (
        "Provider by LLM_PROVIDER and EMBED_PROVIDER: mock or ollama; nothing else knows the "
        "model.",
        BODY,
    ),
    ("Timeout LLM_TIMEOUT_S (default 60, this stack 120); 3 retries with backoff.", BODY),
    (
        "llm_cache through ADK before/after model callbacks; skipped while streaming; only valid "
        "replies are cached, so a schema retry always reaches the model.",
        BODY,
    ),
    (
        "think=False on every chat call: a reasoning model would otherwise spend max_tokens on "
        "hidden reasoning.",
        BODY,
    ),
    ("Request-time budget", LABEL),
    (
        "Ask: 1 embedding + 1 streamed completion. Compare narrative: 1. Scenario explanation: 1. "
        "Everything else: 0.",
        BODY,
    ),
)


def gateway_slide() -> Elements:
    agents = Box(MARGIN_IN, CONTENT_TOP_IN, 5.6, 0.8)
    gateway = Box(MARGIN_IN, 2.7, 5.6, 0.85)
    mock = Box(MARGIN_IN, 3.95, 2.65, 1.05)
    ollama = Box(3.55, 3.95, 2.65, 1.05)
    host = Box(3.55, 5.5, 2.65, 1.0)
    offline = Box(MARGIN_IN, 5.5, 2.65, 1.0)
    return (
        Node(agents, "Six ADK LlmAgents", "model only from LLMGateway.model()", VIOLET),
        Node(gateway, "LLMGateway", "model() · embed() · callbacks()", VIOLET),
        Node(mock, "mock", "MockLlm, hashed embeddings", SUCCESS),
        Node(ollama, "ollama", "LiteLlm ollama_chat/<LLM_MODEL>", VIOLET),
        Node(offline, "No network", "deterministic; every test", SUCCESS),
        Node(host, "Ollama on the host", "deepseek-v4-pro:cloud now", VIOLET),
        Link(agents, gateway),
        Line((centre(gateway) - 1.4, gateway.bottom), (centre(mock), mock.top), has_head=True),
        Line((centre(gateway) + 1.4, gateway.bottom), (centre(ollama), ollama.top), has_head=True),
        Link(mock, offline),
        llm_link(ollama, host),
        *card_with_text(Box(6.6, CONTENT_TOP_IN, RIGHT_EDGE_IN - 6.6, 5.2), GATEWAY_FEATURES),
    )


VERIFIER_STEPS = (
    (
        "1  Parse markers",
        "[c:ID] cites a chunk, [f:ID] a card fact; a sentence without one is unsupported.",
    ),
    (
        "2  Numbers must match",
        "Every number in the sentence must appear in the cited text, after unit normalization.",
    ),
    (
        "3  Words must overlap",
        "Content-word overlap with the pooled cited text at least 0.35 (VERIFY_MIN_OVERLAP).",
    ),
    (
        "4  Drop, count, fall back",
        "Unsupported sentences are removed and counted; if none survive, the fixed sentence is "
        "returned.",
    ),
)
FIXED_SENTENCE = "The curated PSI corpus does not contain enough information to answer that."
LIVE_CHECK = (
    ("On this stack (live model, 2026-11-14)", LABEL),
    (
        "The prepared smoke-detection question kept all five sentences, each with a chip. "
        '"Which experiments tested solids above 30% oxygen?" kept two and dropped two.',
        BODY,
    ),
    ("The fixed sentence", LABEL),
    (FIXED_SENTENCE, TextStyle(14, COOL)),
    ("Scenario explanations", LABEL),
    (
        "After the verified sentences, the service appends deterministic, uncited caveats for "
        "each "
        "extrapolated or no_data dimension, then the gravity statement.",
        BODY,
    ),
)


def verifier_slide() -> Elements:
    lines = itertools.chain.from_iterable(
        ((head, LABEL), (text, BODY)) for head, text in VERIFIER_STEPS
    )
    steps = card_with_text(
        Box(MARGIN_IN, CONTENT_TOP_IN, 6.0, 5.2),
        (("CitationVerifier.verify - deterministic, no LLM", KICKER), *lines),
    )
    live = card_with_text(Box(6.9, CONTENT_TOP_IN, RIGHT_EDGE_IN - 6.9, 5.2), LIVE_CHECK)
    return (*steps, *live)


SYSTEM_SLIDES: tuple[tuple[str, Elements], ...] = (
    ("FlameScope only reads PSI; request-time AI stays on the Mac.", context_slide()),
    ("Four containers; the browser only ever talks to the UI origin.", containers_slide()),
    ("Routers validate, services decide, repositories alone touch SQL.", api_slide()),
    ("Twenty-four endpoints; only three can call a language model.", endpoints_slide()),
    ("Seventeen tables hold cards, runs, scores, chunks and an audit trail.", data_model_slide()),
    ("Ingestion runs offline in nine stages; seed mode enters at normalize.", ingestion_slide()),
    ("Every stage is idempotent, and curator overrides always win.", idempotency_slide()),
    ("Six Google ADK agents, each with one prompt file and one schema.", agents_slide()),
    ("One gateway hides the provider: mock for tests, Ollama live.", gateway_slide()),
    ("The citation verifier deletes sentences their sources do not support.", verifier_slide()),
)
