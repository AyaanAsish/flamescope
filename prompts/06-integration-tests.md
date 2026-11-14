# Prompt 06 - Integration tests: build, deploy, database, ingestion and every API

Write the integration test suite. It exercises the real stack through the Makefile: it builds the images, deploys, checks the database and the ingestion result, and verifies every API endpoint.

## Contract

1. Read `docs/architecture/12-testing-strategy.md` (section 2 is binding for file names and cases), then documents 05 (every endpoint and shape), 04, 06, 08, 09, 11 and 13.
2. Expected results come from the documents and from the seed files, never from copying what the running system returns.
3. If a test fails because the system deviates from the documents, fix the **system** (code, Dockerfiles, Makefile) and report the fix. If the documents are wrong, record it in `docs/architecture/DESIGN-CONFLICTS.md`. Never weaken, skip or delete a test to pass.
4. Deterministic: `LLM_PROVIDER=mock` and `EMBED_PROVIDER=mock` passed to `make deploy` (overriding the `ollama` default in `.env`), seed ingestion, no network beyond base-image pulls. Only `test_21_llm_ollama.py` (marker `ollama`, skipped when Ollama is not reachable) talks to a live model.
5. Scope: `tests/integration/**` and additions to `tests/conftest.py`. No end-to-end browser tests here (prompt 07).
6. No state-changing git commands. No attribution in any file.

## Harness (`tests/conftest.py`, `tests/integration/conftest.py`)

- `repo_root` fixture; `run_make(target, env=None, timeout=...)` returning exit code, stdout, stderr; `compose(*args)` using the same project name and compose file as the Makefile.
- Session-scoped `stack` fixture: if the stack is not already up and healthy, it is brought up by the lifecycle tests (which run first). At session end it leaves the stack running (end-to-end tests reuse it); teardown happens in prompt 07's final test or via `make undeploy`.
- `api` fixture: `httpx.Client(base_url="http://localhost:{API_PORT}/api/v1", timeout=30)`.
- `db` fixture: SQLAlchemy engine to `localhost:{DB_PORT}` built from `.env` values.
- `seed_acronyms`: read from `src/data/seed/investigations/*.yaml`. Tests must work for whatever set of seed files exists; pick sample investigations dynamically (for example "first seed with fuel phase solid") instead of hard-coding acronyms, except where the documents name one (E-FIELD Flames for the gravity analogue, if present in the seed set - skip with a clear reason if not).
- Ordering with `pytest-order`; all tests marked `integration`; build, deploy tests also marked `lifecycle`.
- Reports: JUnit XML and HTML to `tests/reports/`.

## Test files (create exactly these; cases from document 12 section 2)

**Lifecycle**
- `test_00_prereqs.py`
- `test_01_build.py` - calls `make build`; asserts the three image tags exist, non-root user, host architecture, no compiler in the final images (`gcc`, `make` absent), OCI labels present.
- `test_02_deploy.py` - calls `make deploy`; asserts exit 0, container states and health, ingest job exit 0, `/health`, `/ready`, UI root 200, `make deploy` again is idempotent, `make status` output mentions all services.
- `test_03_database.py` - Alembic head, extensions, every table and key column of document 04 (parametrized from a table-to-columns map written from the document), indexes (HNSW on `chunk.embedding`, GIN on `search_tsv`), vector dimension equals `EMBED_DIM`.
- `test_04_ingestion.py` - counts equal seed files; each investigation has three lenses of scores, chunks, hardware links; `ingest_run` statuses; provenance present on findings; `make ingest-seed` idempotent (row counts and `card_version` unchanged).

**API verification - every endpoint in document 05 section 11**
- `test_10_api_health_meta.py` - `/health`, `/ready` (fields), `/meta/stats` (counts equal database counts), `/meta/status` (component IDs `C-API`, `C-DB`, `C-LLM`, `C-ING`; LLM status `mock`), `/meta/rubric` (three lenses, fifteen criteria, weights), `/meta/presets` (all presets of document 08).
- `test_11_api_catalog.py` - list pagination (`page_size` bounds, `total`), each filter individually and combined (cross-check against database queries), `q` search, each `sort` value, summary shape; detail by acronym, by lower-case acronym, by numeric ID, 404 envelope; `/runs`, `/variables` (varied and fixed consistent with runs), `/publications`; `/facets` counts sum correctly; `/hardware` graph integrity (every edge endpoint exists; documented relationships present when their investigations are seeded); `/projects`.
- `test_12_api_rank.py` - each lens and `overall`; response shape; descending order with documented tie-breaks; recompute each score from the returned breakdown with the formulas of document 08 section 2 and compare (tolerance 0.05); presets change weights as documented; explicit weights override presets; filters; determinism (two identical calls give identical bodies); evidence for every non-null criterion; disclaimer text.
- `test_13_api_compare.py` - 2, 3, 4 investigations; 1 and 5 return 400 envelope; unknown acronym 404; attribute order; `same` flag recomputed from values; `shared` correct; `narrative=true` returns `ok` with at least one citation per sentence in mock mode; `narrative=false` returns `skipped`.
- `test_14_api_scenario.py` - each scenario preset; explicit values override preset; similarity in [0,1] and sorted; recompute the top match similarity from returned run and catalog ranges; coverage states for an in-range, out-of-range and gravity case; lunar gravity gives `partial_gravity_data=false` and the gap statement; gravity 0 has no gap statement; changing only gravity leaves similarities unchanged; `explain=true` returns sentences and caveats; `scenario_id` stable across calls.
- `test_15_api_extract.py` - dictionary lists all default columns with units; preview respects filters and `limit`, `total` matches database; column selection; CSV export parses with the `csv` module, header block present as comments, provenance columns filled, row count equals `total`; JSON export; `scenario_id` filter narrows rows.
- `test_16_api_insights_earth.py` - safety-tech groups, each finding has a source and an existing investigation; gaps contain `partial_gravity` with the future experiments named in document 01 section 6; Earth applications list and `sector` filter; items from `earth_applications.yaml` present.
- `test_17_api_ask.py` - stream with `httpx` and parse SSE: event order, at least one `token`, final `citations` sentences all `supported` with at least one citation resolving to a real chunk or card fact, `related` acronyms exist, `done` status; out-of-corpus question returns the fixed sentence and no citations; `X-Request-ID` echoed; malformed body returns 422 envelope (not a stream).
- `test_18_api_contract.py` - OpenAPI document contains exactly the 24 documented method-path pairs under `/api/v1` and no others (docs and openapi routes excluded); every documented response field appears in the schemas; 404 and 422 envelopes; `X-Request-ID` generated when absent and echoed when supplied; CORS header for the configured origin and absent for another origin.
- `test_19_performance.py` - p95 under 300 ms over 30 sequential calls for every non-LLM GET endpoint and `POST /rank`, after one warm-up call; report timings in the test output.
- `test_20_ui_smoke.py` - every UI route from document 10 section 5 returns 200 with `text/html` (use a seeded acronym for the detail route); `/api/v1/health` through the UI origin returns 200; unknown route returns the 404 page; the draw.io download returns 200.

## Traceability

Add a module docstring to every test file naming the requirement IDs and call flows it verifies (from document 13 section 1). Add `tests/integration/README.md` with the file-to-requirement table and how to run a single file against an already running stack.

## Run and report

1. From a fully undeployed state run `make test-integration`. Everything passes.
2. Run it a second time against the running stack; everything still passes.
3. Report: tests per file, pass counts, timings from the performance test, every system fix made (with document reference), conflicts recorded, anything skipped and why.
