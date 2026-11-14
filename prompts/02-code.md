# Prompt 02 - Generate the application code under `src/`

Build the complete FlameScope application. The architecture documents are the bible: implement exactly what they specify, with the exact names they specify, and nothing they do not.

## Non-negotiable contract

1. **Read first.** Before writing any file, read all of `docs/architecture/` (00 to 13) in full. Before each phase below, re-read the documents listed for that phase.
2. **Names are contracts.** Paths, packages, modules, classes, methods, endpoint paths, JSON field names, table and column names, environment variables, component IDs and `data-testid` values come from the documents verbatim.
3. **No extra surface.** No endpoint, table, route, service, dependency or configuration variable that the documents do not describe.
4. **Conflict procedure.** If something in the documents is contradictory, missing or cannot work, stop that item, write the issue to `docs/architecture/DESIGN-CONFLICTS.md` (document, section, problem, proposed resolution), choose the most conservative reading to continue with, and list it in your final report. Do not silently improvise.
5. **Scope of this prompt.** Create application code and data under `src/`, plus `pyproject.toml` and `.env.example` at the root. Do **not** create tests (prompt 03), Dockerfiles or compose (prompt 04), the Makefile (prompt 05) or the README (prompt 10).
6. **Working rules.** All source code under `src/`. Python 3.12. No state-changing git commands. No AI or tool attribution in any file. No invented scientific facts.
7. Use the project's subagents and skills if they exist (`.claude/agents`, `.claude/skills`): delegate each phase to its owning agent and run `arch-lookup` before and `conformance-check` after each phase.

## Phase 0 - Plan (no code)

Produce a build plan as a checklist that maps every component in document 03 and every endpoint in document 05 section 11 to the file that will implement it. Confirm the plan covers the whole repository layout in document 02 section 4. Then proceed without waiting.

## Phase 1 - Scaffold and common library

Read: 02, 03 section 2, 04, 11 section 3.

- `pyproject.toml`: one project, packages discovered from `src/common`, `src/agents`, `src/api`, `src/ingest`; runtime dependencies from document 02 section 3; `[project.optional-dependencies] dev` with pytest, pytest-asyncio, pytest-order, respx, httpx, playwright, ruff, mypy, radon, xenon; console script `flamescope-ingest = flamescope_ingest.cli:app`; ruff (including the `C90` and `PLR` complexity rules in `.claude/rules/15-complexity.md`), mypy and pytest configuration (markers from document 12 section 4).
- `.env.example` with every variable and default from document 11 section 3.
- `src/common/flamescope_common/`: every module in document 03 section 2. ORM models for every table and column in document 04. Alembic environment and revision `0001_initial` (creates extensions `vector` and `pg_trgm`, all tables, indexes; reads `EMBED_DIM`). Pydantic schemas: `InvestigationCard` (document 04 section 4), `SourceRef`, all API request and response models (document 05), all agent input and output models (document 07 section 3).
- LLM gateway and the two providers `mock` and `ollama` built on Google ADK model classes (document 07 section 6). The mock provider (`MockLlm`) must be fully deterministic and produce schema-valid output for every agent with no fixtures present.

Gate: `python -c "import flamescope_common"` works; `ruff check` and `mypy` pass on `src/common`.

## Phase 2 - Data files

Read: 01 section 6, 04 section 5, 06 section 5, 08.

Create under `src/data/`:

- `rubric.yaml` exactly as document 08 section 1 (IDs, labels, weights, anchors), with `rubric_version`.
- `presets.yaml` with ranking presets, scenario presets and `texts.gravity_bounding` (document 08 sections 3 and 4).
- `seed/hardware.yaml`, `seed/fuel_taxonomy.yaml`, `seed/earth_applications.yaml`, `seed/s3_map.yaml`.
- `seed/investigations/<acronym>.yaml` for each PSI combustion investigation.

Rules for seed content (strict):
- Start with the investigations named in document 01 section 6. Use the PSI website and the public bucket listing to identify the full combustion list and add a file for each one you can confirm.
- Fill fields only from sources you actually retrieved in this session (PSI overview pages, PSI documents, publication abstracts). Each fact carries a `source` with a real URI you opened.
- If you cannot retrieve a source for a value, set it to `null`, add a line to `open_questions`, and keep `reviewed: false`. A sparse but true card is correct; a rich but invented card is a defect.
- Do not fabricate DOIs, numeric conditions, sample dimensions or findings. Do not copy the illustrative numbers from document 04 section 4.
- If network access to PSI is unavailable, create the files with the structural facts stated in document 01 section 6 (cited to the challenge page URL as `curated`), nulls elsewhere, and say so in the final report.
- `overrides/` exists with a `.gitkeep` and a commented example.

Gate: every seed file validates against `InvestigationCard` and the vocabulary.

## Phase 3 - Agents

Read: 07 (all), 08 section 1.

- `src/agents/flamescope_agents/`: every module in document 03 section 3.
- Runtime prompt files in `prompts/` inside that package, one per agent plus `shared/grounding_rules.md` and `shared/domain_primer.md`, in the file format of document 07 section 2. Write complete, production-quality prompts: role, task, input description, output schema, grounding rules include, two short examples of the expected JSON shape using placeholder content, refusal behaviour.
- `CitationVerifier` exactly as document 07 section 4.
- Optional fixtures directory for the mock provider.

Gate: each agent runs end to end with `LLM_PROVIDER=mock` and returns schema-valid output.

## Phase 4 - Ingestion

Read: 06 (all), 03 section 7, 09 CF-02 and CF-03.

- `src/ingest/flamescope_ingest/`: every module and every CLI command in document 06 section 4.
- Seed mode must work with no network and no real LLM.
- Harvest mode: unsigned S3 access, download rules of document 06 section 3.2, quote verification, overrides merge.
- Idempotent upserts; `ingest_run` audit rows; derived columns recomputed.

Gate (if a local PostgreSQL with pgvector is available; otherwise defer to prompt 06): `flamescope-ingest migrate && flamescope-ingest seed` twice gives identical row counts.

## Phase 5 - API

Read: 05 (all), 03 sections 4 to 6, 08, 09 CF-04 to CF-12.

- `src/api/flamescope_api/`: app factory, middleware, error envelope, SSE helper, all routers, services and repositories with the public methods listed in document 03.
- Implement the pure functions named in document 03 section 5 as standalone, importable functions and make them reproduce the worked examples in document 08 section 6.
- Exactly the 24 endpoints of document 05 section 11 under `/api/v1`, with the response shapes shown.
- Hybrid retrieval with reciprocal rank fusion; SSE event order of document 05 section 10; fallbacks of document 07 section 7.

Gate: the app imports and `create_app()` builds; the OpenAPI document lists exactly the 24 paths.

## Phase 6 - UI (Next.js, dark, very professional)

Read: 10 (all), 05, 09.

- `src/ui/` as specified in document 10 section 3: Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, TanStack Query, Zustand, Recharts, `@xyflow/react`, Mermaid. `output: 'standalone'` and the `/api` rewrite to `API_INTERNAL_URL`.
- Implement the design system exactly: tokens, typography, spacing and the eight quality rules in section 2. Dark theme only. The result must look like a polished commercial analytics product: consistent spacing, restrained colour, crisp tables, real loading skeletons, no default-looking components, no placeholder lorem text, no emoji.
- All eleven routes in section 5 with the listed components, API calls and `data-testid` values. URL-mirrored state.
- The Architecture page per section 6: seven tabs; React Flow diagrams from JSON in `content/architecture/` with hand-set positions (no node overlaps, no edge passing through a node, minimum 40 px gaps); custom node types; legend, minimap, fit view; node side panel; hover highlighting; live status badges from `/meta/status`; Mermaid call-flow viewer for CF-01 to CF-13 using the diagrams in document 09; draw.io download. Copy `docs/design-diagrams/flamescope-architecture-v2.drawio` to `src/ui/public/flamescope-architecture.drawio`.
- Every node's `componentId`, files and flows must match document 03 and document 09.

Gate: `npm run build`, `npm run lint` and `tsc --noEmit` pass.

## Phase 7 - Self-verification and report

1. Run ruff and mypy over all Python packages, and the `complexity-check` skill (radon, xenon, ESLint complexity rules); fix all findings.
2. Check the import rules of document 03 section 10 by inspection.
3. Walk the conformance checklist in document 13 section 4 line by line and state pass or fail with evidence (file paths). Items that depend on later prompts (containers, Makefile, tests) are marked "pending prompt N".
4. Final report: files created per package, any entries in `DESIGN-CONFLICTS.md`, seed coverage (how many investigations, how many reviewed, what was left null and why), and anything that could not be verified in this environment.

Do not create tests, Dockerfiles, a Makefile or a README in this session. Do not run state-changing git commands. Do not add attribution anywhere.
