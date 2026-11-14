# 12 - Testing Strategy

Three levels. All run with `LLM_PROVIDER=mock` and seed data, so they are deterministic and need no network beyond pulling base images. The test harness sets `LLM_PROVIDER=mock` and `EMBED_PROVIDER=mock` when it runs `make deploy`, overriding the `ollama` default in `.env`. The one exception is the optional `ollama`-marked test below.

| Level | Location | Runner | Needs Docker | Scope |
|-------|----------|--------|--------------|-------|
| Unit | `tests/unit/`, `src/ui/**/*.test.ts(x)` | pytest, Vitest | No | Pure logic, schemas, agents with mock gateway, services with fake repositories, UI components |
| Integration | `tests/integration/` | pytest | Yes | Build, deploy, database, ingestion, every API endpoint |
| End-to-end | `tests/e2e/` | pytest + Playwright | Yes | Every UI route and the main user journeys, undeploy |

## 1. Unit tests

Layout mirrors `src/`:

```
tests/unit/
  common/   test_config.py test_units.py test_rubric.py test_sources.py test_schemas_card.py
            test_llm_gateway.py test_llm_mock_provider.py test_llm_ollama_provider.py test_llm_cache.py
  agents/   test_base_agent.py test_prompt_files.py test_orchestrator.py test_extractor.py test_scorer.py
            test_comparator.py test_scenario_interpreter.py test_insight_qa.py test_citation_verifier.py
  api/      test_ranking_aggregate.py test_scenario_distance.py test_scenario_coverage.py
            test_gravity_bounding.py test_compare_diff_matrix.py test_extract_table.py
            test_insight_fusion.py test_error_envelope.py test_sse_format.py test_routers_contract.py
            test_catalog_service.py test_safety_tech_gaps.py test_meta_service.py test_earth_service.py
  ingest/   test_seed_loader.py test_normalizer.py test_parser.py test_harvest_rules.py
            test_overrides.py test_quote_verification.py test_chunking.py test_cli.py
  architecture/ test_import_rules.py test_docs_conformance.py
```

Required cases (minimum):

- **Scoring**: the worked example in document 08 section 6 gives 72.9 and confidence 0.85; all-null criteria give a null score; weight normalization; preset override order; tie-breaking order.
- **Scenario**: the worked distance example gives similarity 0.696 (tolerance 0.001); aggregate-run range handling; unset dimensions dropped; coverage states; gravity bounding for 0, 1, 0.166 and 0.38 g.
- **Compare**: `same` flags; attribute order equals document 05 section 6.
- **Citation verifier**: supported, number-mismatch, no-marker and all-dropped cases.
- **Prompt files**: each runtime prompt has valid front matter, both sections, only declared variables, and resolves includes.
- **Mock provider**: same input gives same output; outputs validate against agent schemas; embeddings have length `EMBED_DIM` and unit norm.
- **Ollama provider**: `model()` returns an ADK `LiteLlm` for `ollama_chat/<LLM_MODEL>` with `api_base = OLLAMA_BASE_URL`; `embed` posts to `/api/embed` (mocked with `respx`); an unreachable server raises `LLMError`.
- **ADK runtime**: each agent builds an ADK `LlmAgent` with no tools and the right `output_schema`; the orchestrator runs it through a `Runner` on `MockLlm`.
- **Seed files**: every file under `src/data/seed/investigations/` validates as a `SeedInvestigation` (and therefore as an `InvestigationCard`, document 06 section 5), every fact has a source with an allowed URI scheme, tags are in the vocabulary.
- **Catalog, safety tech, meta and Earth services** (fake repositories): summaries, score sort and pagination, variables derivation, lineage graph with project edges (`test_catalog_service.py`); all six safety-tech categories in order, the `partial_gravity` presence rule and the document 08 section 5 region rules (grid, 4-connected regions, envelope-first order, `param_gap_<n>` IDs) (`test_safety_tech_gaps.py`); `ready()` states, stats and the `status()` component list (`test_meta_service.py`); Earth items and the sector filter (`test_earth_service.py`).
- **Routers contract** (FastAPI `TestClient` with fake services): status codes, error envelope, pagination limits, request validation for every endpoint in the inventory.
- **Import rules**: static check of the dependency table in document 03 section 10.
- **Docs conformance**: the endpoint inventory in document 05 section 11 equals the routes registered in the app; the Makefile declares every target in document 11 section 4; UI architecture JSON component IDs exist in document 03.

UI unit tests (Vitest + Testing Library): `format.ts` unit conversion, `sse.ts` frame parser, WeightSliders normalization, DiffMatrix same/different rendering, StatusBadge states, architecture content integrity (no overlapping node rectangles within a diagram, all edges reference existing nodes), each page renders its loading, empty and error states with a mocked API.

Coverage targets: 85% lines for `flamescope_common`, `flamescope_agents` and `flamescope_api.services`; 70% overall Python; UI logic in `lib/` 80% (enforced: `npm test` runs `vitest run --coverage` with the v8 provider over `lib/**` and a lines threshold of 80 in `vitest.config.ts`).

## 2. Integration tests

Run order is enforced by file naming and `pytest-order` (or explicit dependencies). A session fixture owns the stack lifecycle; `KEEP_STACK=1` leaves it running.

| File | Verifies |
|------|----------|
| `test_00_prereqs.py` | Docker daemon reachable, compose v2 present, required ports free (or stack already ours), `.env` exists. |
| `test_01_build.py` | `make build` exits 0; images `flamescope-api:local`, `flamescope-ingest:local`, `flamescope-ui:local` exist; each runs as non-root; image architecture matches the host; final images contain no compiler toolchain. |
| `test_02_deploy.py` | `make deploy` exits 0; `db`, `api`, `ui` containers are `running` and `healthy`; the ingest job exited 0; `/api/v1/health` and `/api/v1/ready` return 200; the UI returns 200 at `/`. |
| `test_03_database.py` | Alembic head applied; extensions `vector` and `pg_trgm` installed; all tables of document 04 exist with key columns and indexes; `chunk.embedding` dimension equals `EMBED_DIM`. |
| `test_04_ingestion.py` | Seed counts: investigations equals number of seed files; every investigation has scores for 3 lenses, at least one chunk, hardware links; `ingest_run` rows `ok`; re-running `make ingest-seed` is idempotent (row counts unchanged, `card_version` unchanged). |
| `test_10_api_health_meta.py` | `/health`, `/ready`, `/meta/stats`, `/meta/status`, `/meta/rubric`, `/meta/presets`. |
| `test_11_api_catalog.py` | `/investigations` (pagination, each filter, sort, search), `/investigations/{id}` (by acronym, case-insensitive, 404), `/runs`, `/variables`, `/publications`, `/facets`, `/hardware`, `/projects`. |
| `test_12_api_rank.py` | Each lens and `overall`; presets change order; custom weights; determinism; breakdown contributions sum to the score; evidence present for non-null values; disclaimer present. |
| `test_13_api_compare.py` | 2, 3 and 4 investigations; 1 and 5 give 400; matrix attribute order; narrative `ok` in mock mode with citations; `narrative=false` gives `skipped`. |
| `test_14_api_scenario.py` | Each preset; explicit values; coverage states; gravity bounding for lunar gravity names E-FIELD Flames and states the gap; `explain=true` returns verified sentences; `scenario_id` stable. |
| `test_15_api_extract.py` | Dictionary; preview with filters; CSV export parses, has provenance columns and header block; JSON export; `scenario_id` filter. |
| `test_16_api_insights_earth.py` | Safety-tech groups cover all categories present; gaps include `partial_gravity`; Earth applications list and sector filter. |
| `test_17_api_ask.py` | SSE event order `meta`, `token`+, `citations`, `related`, `done`; every final sentence has a citation; out-of-corpus question returns the fixed sentence; request ID echoed. |
| `test_18_api_contract.py` | OpenAPI document lists exactly the 24 endpoints; error envelope on 404 and 422; `X-Request-ID` on every response; CORS header for the configured origin. |
| `test_19_performance.py` | p95 under 300 ms over 30 calls for each non-LLM GET endpoint and `POST /rank` (NFR-04). |
| `test_20_ui_smoke.py` | The UI container serves every route with HTTP 200 and proxies `/api/v1/health` through the rewrite. |
| `test_21_llm_ollama.py` | Optional, marker `ollama`; skipped unless Ollama answers at `OLLAMA_BASE_URL` with both models pulled. Runs the comparator, scenario interpreter and insight QA agents in-process through the orchestrator on `qwen2.5:0.5b` and checks schema-valid output and citation verification (or the documented `unavailable` state); checks `nomic-embed-text` embeddings have `EMBED_DIM` dimensions. |

## 3. End-to-end tests

Playwright for Python (Chromium), against `http://localhost:3000`. Viewport 1440x900 plus one pass at 1024x768. Tests use `data-testid` selectors from document 10 section 5.

| File | Journey |
|------|---------|
| `test_e2e_00_shell.py` | Dark theme applied (`html.dark`, background token), sidebar lists the ten views in order, top-bar badges show `mock` and dataset count, footer disclaimer, no console errors on any route. |
| `test_e2e_01_overview.py` | Stat tiles match `/meta/stats`; scatter renders points; top-5 links open detail. |
| `test_e2e_02_explorer.py` | Filter by fuel phase changes the card count to match the API; search; open a card; detail tabs show runs and variables; PSI link present; a source link on the detail page opens in a new tab with `noopener` (the detail route has no evidence drawer; that belongs to `/ranking`). |
| `test_e2e_03_ranking.py` | Switch lens; choose `lunar_habitat` preset and see order change; move a slider and see scores update; open the evidence drawer and see a source link; URL reflects state. |
| `test_e2e_04_compare.py` | Pick three investigations; matrix shows same/different markers; narrative appears with citation chips; lineage graph renders. |
| `test_e2e_05_scenario.py` | Lunar preset fills the form; coverage panel shows gravity `no data`; gravity-bounding card text mentions partial gravity; Explain shows text; export downloads a CSV. |
| `test_e2e_06_extract.py` | Build a query, preview rows, toggle a column, download CSV and JSON and validate contents. |
| `test_e2e_07_safety_earth.py` | Safety-tech groups render with findings; Earth cards render and filter by sector. |
| `test_e2e_08_ask.py` | Ask a question; tokens stream; final answer shows citation chips; clicking a chip opens the source panel; out-of-corpus question shows the fixed sentence. |
| `test_e2e_09_architecture.py` | All seven tabs render; nodes exist for every component ID; clicking a node opens the panel with files and flows; status badges reflect `/meta/status`; call-flow selector renders an SVG for each CF; draw.io download returns 200. |
| `test_e2e_10_visual.py` | Screenshot each route to `tests/e2e/artifacts/`; automated contrast check (axe-core) reports no serious or critical violations. |
| `test_e2e_99_undeploy.py` | `make undeploy` exits 0; no `flamescope` containers, network or volumes remain; ports are free. Runs last; skipped when `KEEP_STACK=1`. |

## 4. Fixtures and helpers

`tests/conftest.py`: `repo_root`, `run_make(target, env)`, `compose(*args)`, `api` (httpx client with base URL), `wait_for(url, timeout)`, `seed_acronyms` (read from `src/data/seed/investigations/`). `tests/e2e/conftest.py`: Playwright `page` with console-error capture and failure screenshots.

Markers: `unit`, `integration`, `e2e`, `lifecycle` (build, deploy, undeploy), `slow`, `ollama` (needs a live Ollama on the host). `pytest.ini` options in `pyproject.toml`.

## 5. Definition of done for the test suite

`make test` on a clean Mac checkout with Docker running: builds the images, deploys, passes all three levels, undeploys, and leaves nothing behind. A JUnit XML and an HTML report are written to `tests/reports/`.
