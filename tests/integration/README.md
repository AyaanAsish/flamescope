# Integration tests

Build, deploy, database, ingestion and every API endpoint of the running Docker Compose stack
(document 12 section 2). The harness passes `LLM_PROVIDER=mock` and `EMBED_PROVIDER=mock` to
every `make` and compose call, so results do not depend on the provider chosen in `.env`.
Only `test_21_llm_ollama.py` (marker `ollama`) talks to a live model.

## Files and requirements

Requirement IDs and call flows from document 13 section 1; every test names its IDs in its
name or docstring.

| File | Verifies | Requirements | Call flows |
|------|----------|--------------|------------|
| `test_00_prereqs.py` | Docker daemon, compose v2, ports free or ours, `.env` | NFR-01, NFR-06 | CF-01 |
| `test_01_build.py` | `make build`; three tags, uid 10001, host architecture, no compiler, OCI labels | NFR-01 | CF-01 |
| `test_02_deploy.py` | `make deploy` (twice), container health, ingest job, `/health`, `/ready`, UI root, `make status` | NFR-01, NFR-02, NFR-05 | CF-01, CF-02 |
| `test_03_database.py` | Alembic head, extensions, tables and columns of document 04, indexes, unique keys, `vector(EMBED_DIM)` | FR-01, FR-11, NFR-04 | CF-01, CF-02 |
| `test_04_ingestion.py` | Rows per seed file, 3 lenses of scores, chunks, hardware links, `ingest_run`, provenance, idempotent `make ingest-seed` | FR-01, FR-03, FR-11, FR-12, FR-15, NFR-05 | CF-01, CF-02 |
| `test_10_api_health_meta.py` | `/health`, `/ready`, `/meta/stats`, `/meta/status`, `/meta/rubric`, `/meta/presets` | FR-03, FR-04, FR-13, FR-14, NFR-02 | CF-01, CF-11, CF-12 |
| `test_11_api_catalog.py` | `/investigations` (pagination, filters, search, sort), detail, `/runs`, `/variables`, `/publications`, `/facets`, `/hardware`, `/projects` | FR-01, FR-02, FR-06, FR-12 | CF-04, CF-06 |
| `test_12_api_rank.py` | `POST /rank`: lenses, order, formulas, presets, explicit weights, filters, limit, determinism, evidence, disclaimer | FR-03, FR-04, FR-15, NFR-09 | CF-05 |
| `test_13_api_compare.py` | `POST /compare`: 2 to 4 IDs, 400 and 404, attribute order, `same`, `shared`, narrative `ok` / `skipped` | FR-05, FR-15, NFR-02 | CF-06 |
| `test_14_api_scenario.py` | `POST /scenario`: presets, overrides, coverage, gravity bounding, similarity, explanation, `scenario_id` | FR-07, FR-16 | CF-07 |
| `test_15_api_extract.py` | `/extract/dictionary`, `/extract/preview`, `/extract/export` (CSV, JSON), `scenario_id` filter | FR-08, FR-15 | CF-08 |
| `test_16_api_insights_earth.py` | `/insights/safety-tech`, `/insights/gaps` (partial gravity, grid regions), `/earth-applications` | FR-09, FR-10, FR-14, FR-15, FR-16 | CF-10, CF-11 |
| `test_17_api_ask.py` | `POST /ask` SSE: event order, citations, out-of-corpus sentence, request ID, 422 envelope | FR-11, FR-15, NFR-11 | CF-09 |
| `test_18_api_contract.py` | OpenAPI equals the 24 documented endpoints and fields; error envelopes; `X-Request-ID`; CORS | NFR-08, NFR-11, FR-15 | CF-04 to CF-12 |
| `test_19_performance.py` | p95 under 300 ms over 30 calls for every non-LLM GET and `POST /rank` (printed in the summary) | NFR-04 | CF-05 |
| `test_20_ui_smoke.py` | Every UI route of document 10 section 5, `/api/v1/health` through the UI, 404 page, draw.io file | FR-13, NFR-01, NFR-08 | CF-01, CF-04 to CF-12 |
| `test_21_llm_ollama.py` | Optional (`ollama`): comparator, scenario interpreter and insight QA in-process on `LLM_MODEL`; embeddings of `EMBED_DIM` | NFR-07 | CF-06, CF-07, CF-09 |

## Running

The whole suite, from an undeployed or a running stack (it builds, deploys in mock mode and
leaves the stack running for the end-to-end tests):

```
make test-integration
```

One file against an already running stack (the session `stack` fixture redeploys in mock mode
only when the API is not ready or not in mock mode):

```
.venv/bin/python -m pytest tests/integration/test_12_api_rank.py
```

Skip the live-model test, or run only it:

```
.venv/bin/python -m pytest tests/integration -m "not ollama"
.venv/bin/python -m pytest tests/integration/test_21_llm_ollama.py
```

Ports and database credentials come from the environment, then `.env`, then the defaults of
document 11 section 3. Reports: `tests/reports/integration.xml` and `integration.html`.
