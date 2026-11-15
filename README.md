# FlameScope

An AI-powered web dashboard that summarizes, ranks and interprets the combustion investigations in NASA's Physical Sciences Informatics (PSI) repository to deliver fire-safety insights. Built for the NASA Space Apps Challenge 2026 challenge "Flame in Freefall".

![FlameScope Overview page: stat tiles and the oxygen versus pressure coverage map with the lunar-habitat envelope](docs/images/overview.png)

## What it does

FlameScope holds 25 curated investigation cards covering all 24 PSI Combustion Science records, with 2,003 test runs, 355 publications and 40 categorized findings. Every fact links to its source.

- **O1, identify relevant investigations**: **Ranking** scores every investigation under a habitat, modeling or controls lens with adjustable weights and the evidence behind each rating; **Scenario Lab** finds the tests closest to a target habitat atmosphere.
- **O2, extract data for modeling**: **Data Extract** builds a table of test runs with conditions, outcomes and provenance columns, and exports CSV or JSON with a data dictionary.
- **O3, inform controls and equipment**: **Safety Tech** groups findings by detection, suppression, material screening, post-fire hazards and atmosphere design, linked to their investigations.
- **O4, Earth applications**: **Earth Apps** lists terrestrial applications (for example smoke detection and fine water mist) linked to findings and investigations.

Partial gravity is treated as a bounded gap: PSI holds no partial-gravity combustion data, so FlameScope shows microgravity and normal-gravity evidence as bounds and names E-FIELD Flames as the analogue. It never interpolates a number.

## Screens

| View | What you see |
|------|--------------|
| [Ranking](docs/images/ranking.png) | Lunar-habitat preset, weight sliders and stacked per-criterion score bars. |
| [Scenario Lab](docs/images/scenario.png) | Lunar-habitat atmosphere, catalog coverage per dimension and the gravity-bounding statement. |
| [Data Extract](docs/images/extract.png) | Filtered preview of FLEX test runs with a source URI on every row. |
| [Ask](docs/images/ask.png) | A streamed answer with citation chips and the retrieved sources. |
| [Architecture](docs/images/architecture.png) | Interactive component diagram with live status badges and a detail panel. |

All screenshots are from the running stack with the curated seed data in live mode, at 1440x900.

## Quick start (macOS)

Prerequisites, with the versions this README was verified on (Apple Silicon):

| Tool | Required | Verified |
|------|----------|----------|
| Docker Desktop or Colima | running daemon | Docker 29.1.3 |
| Docker Compose v2 | `docker compose` | 2.40.3 |
| GNU Make | stock macOS make works | 3.81 |
| Python | 3.12, for `make doctor`, `make venv` and the test suites | 3.12.14 |
| Node | 20 or newer, for local UI work and Vitest | 25.6.1 |
| Ollama | installed natively, for live LLM mode | 0.40.15 |

For the default live mode, pull the two models once:

```bash
make ollama-pull
```

Then:

```bash
make doctor
make build
make deploy
make open
```

| Step | What it does | Time on the verification run |
|------|--------------|------------------------------|
| `make doctor` | Checks docker, compose, Python 3.12, node, free ports 8000, 3000 and 5432 and, in live mode, that Ollama answers with `LLM_MODEL` and `EMBED_MODEL` pulled. | 2 s |
| `make build` | Creates `.env` from `.env.example` if missing and builds `flamescope-api:local`, `flamescope-ingest:local` and `flamescope-ui:local`. | 151 s without layer cache, 6 s with cache |
| `make deploy` | Starts PostgreSQL, runs the ingest job (migrate and seed), starts the API and UI, waits for readiness and prints the URLs. | 33 s in mock mode; 233 s with a hosted Ollama model; 953 s with `qwen2.5:0.5b` |
| `make open` | Opens http://localhost:3000 in the default browser. | instant |

`make doctor` looks for `python3.12` on the `PATH`. If your 3.12 interpreter lives elsewhere, pass it: `make doctor PYTHON=/path/to/python3.12` (the same variable is used by `make venv`).

Deploy time in live mode is mostly seed-time scoring: the seed files carry no scores, so the scorer agent rates each investigation under each of the three lenses (75 calls) with the configured model during the ingest job. In mock mode the ratings come from a deterministic rule-based mock.

With the default `qwen2.5:0.5b` the deploy completes and the stack is fully usable, but the small model is a weak rater: on the verification run 32 of the 75 scoring calls failed (the ingest reports `pipeline status: partial`) and 13 of 25 investigations had no overall score. The hosted model run had no failures. For complete rankings use a larger `LLM_MODEL` or mock mode (see [LLM modes](#llm-modes)).

When the stack is up:

| What | URL |
|------|-----|
| UI | http://localhost:3000 |
| API docs (Swagger UI) | http://localhost:8000/api/v1/docs |
| Architecture page | http://localhost:3000/architecture |

The default configuration (`.env.example`) runs the curated seed data with `qwen2.5:0.5b` and `nomic-embed-text` on the host's Ollama. A fully offline, deterministic mock mode needs no Ollama at all:

```bash
LLM_PROVIDER=mock EMBED_PROVIDER=mock make deploy
```

Stop everything and remove the containers, network and volumes:

```bash
make undeploy
```

`make undeploy` took 2 s.

## LLM modes

Runtime agents are Google ADK `LlmAgent`s. Their model comes from the LLM gateway, which has two providers.

| Mode | Settings in `.env` | Network | Use |
|------|--------------------|---------|-----|
| Live, local model (default) | `LLM_PROVIDER=ollama`, `LLM_MODEL=qwen2.5:0.5b`, `EMBED_MODEL=nomic-embed-text` | None after `make ollama-pull` | Default; free and offline. A 0.5B model gives short narratives, more sentences dropped by the citation checker and incomplete seed-time ratings (see Quick start). |
| Live, hosted Ollama model | `LLM_PROVIDER=ollama`, `LLM_MODEL=<model>:cloud` | Internet and an ollama.com sign-in | Stronger narratives and seed-time ratings; any Ollama chat model can be named without code change. |
| Mock | `LLM_PROVIDER=mock`, `EMBED_PROVIDER=mock` | None | Tests, offline fallback. Deterministic output. |

Ranking, scenario matching, export and browsing are deterministic Python and never call a model or the network. The configured model is used only by Ask, the compare narrative, the scenario explanation, and seed-time scoring. If the model fails at request time, the deterministic part of each response is still returned and the narrative or explanation is marked `unavailable`.

To switch mode, edit `.env` and restart the API and UI:

```bash
make restart
```

The top bar shows the active mode: `mock`, or `ollama` with the model name, read from `/api/v1/meta/status`. A restart does not re-score: ratings stored at deploy time stay until the next `make undeploy && make deploy`. Because live-mode ratings come from the configured model, they can differ between models and between deploys; mock-mode ratings are reproducible.

Embeddings: `EMBED_DIM` is 768, the dimension of `nomic-embed-text`, fixed in the database at migration time. After changing `EMBED_MODEL` or `EMBED_PROVIDER`, re-embed every chunk:

```bash
docker compose -p flamescope -f deploy/docker/compose.yaml --env-file .env --profile job run --rm ingest index --force
```

This took 13 s for the 215 chunks with `nomic-embed-text`. A model with a different dimension also needs a new migration (document 04 section 6). The Ask retrieval threshold (`MIN_VECTOR_SIMILARITY`, 0.55 for `ollama`) is calibrated for `nomic-embed-text`; another embedding model needs a new calibration ([document 05 section 10](docs/architecture/05-api-specification.md)).

## Harvesting from PSI

`make ingest-harvest` runs `flamescope-ingest harvest` in the ingest container: the full harvest-mode pipeline, discover, harvest, parse, extract, normalize, link, score, index and review ([document 06](docs/architecture/06-ingestion-pipeline.md)). It requires `LLM_PROVIDER=ollama`.

- **Source**: the public bucket `PSI_BUCKET=nasa-psi` in `PSI_REGION=us-west-2`, read with unsigned requests under `PSI_PREFIX` (empty by default). Folders can be pinned to acronyms in `src/data/seed/s3_map.yaml`.
- **Download limits**: documents up to `HARVEST_MAX_DOC_MB` (25), tables up to `HARVEST_MAX_TABLE_MB` (5) and at most `HARVEST_MAX_TABLES` (20) per investigation, `HARVEST_MAX_TOTAL_MB` (300) in total. Video, images, archives and binaries are never downloaded; they are listed in the manifest by key, size and type.
- **Review and overrides**: the review stage reports null required fields, low-confidence fields, failed quote checks and runs without data. Curator corrections go in `src/data/overrides/<acronym>.yaml` and always win over model output.
- **Export to seed files**: `flamescope-ingest export-seed` writes reviewed cards to `src/data/seed/investigations/` so the curated result becomes the offline dataset. Run it from the host (`make venv`, then `DATABASE_URL=postgresql+psycopg://flamescope:flamescope@localhost:5432/flamescope DATA_DIR=src/data .venv/bin/flamescope-ingest export-seed`), because inside the ingest container the seed directory is part of the image, not the repository.

What was verified: the harvest pipeline is covered by unit tests and was exercised end to end in development against a stub S3 client. A live harvest of the real bucket was not verified: the `nasa-psi` bucket has no Combustion Science prefix at its root (open item OI-01). The shipped seed data was curated instead from the PSI public data service (the PSI repository records and experimental tables), NTRS records and NASA pages.

## Architecture at a glance

```mermaid
flowchart TB
  UI[Next.js UI, dark theme] -->|REST and SSE via /api rewrite| API[FastAPI routers /api/v1]
  API --> SVC[Deterministic domain services]
  SVC --> REPO[Repositories]
  SVC -->|Ask, compare narrative, scenario explanation| ORCH[Agent orchestrator, Google ADK]
  ORCH --> GW[LLM gateway: mock or Ollama]
  REPO --> DB[(PostgreSQL 16 + pgvector)]
  ING[Ingestion job: seed or harvest] --> DB
  ING --> GW
  GW --> OLL[Ollama on the Mac host]
```

A Next.js UI calls a FastAPI service over REST and Server-Sent Events. The API reads PostgreSQL with pgvector, which holds the investigation cards, test runs, relevance scores and document chunks. An offline ingestion job fills the database from curated seed files or by harvesting PSI with LLM agents. Four containers (`db`, `api`, `ingest`, `ui`) run under Docker Compose with project name `flamescope`.

Three design principles:

1. **Curate and link.** The archive is about 12 TB; FlameScope curates metadata, documents and test tables and links to the raw data instead of moving it.
2. **AI offline, arithmetic online.** Extraction and scoring happen at ingestion; ranking, matching and export are deterministic, tunable arithmetic. Only three request-time features call a model.
3. **Provenance everywhere.** Every extracted field, score and generated sentence carries a source reference; a citation checker removes unsupported sentences.

| Document | What it settles |
|----------|-----------------|
| [00 Index](docs/architecture/00-README.md) | Reading order and conventions |
| [01 Requirements and scope](docs/architecture/01-requirements-and-scope.md) | Challenge objectives, requirement IDs, open items |
| [02 System architecture](docs/architecture/02-system-architecture.md) | Context, layers, technology, layout, decisions |
| [03 Component design](docs/architecture/03-component-design.md) | Every component and its interface |
| [04 Data model](docs/architecture/04-data-model.md) | Tables, JSON shapes, the investigation card |
| [05 API specification](docs/architecture/05-api-specification.md) | Every REST and SSE endpoint |
| [06 Ingestion pipeline](docs/architecture/06-ingestion-pipeline.md) | Seed and harvest modes, stages, CLI |
| [07 Agents and LLM](docs/architecture/07-agents-and-llm.md) | Agents, prompts, gateway, mock provider |
| [08 Scoring and scenario](docs/architecture/08-scoring-and-scenario.md) | Rubric, formulas, presets, gravity bounding |
| [09 Call flows](docs/architecture/09-call-flows.md) | Sequence diagrams for every flow |
| [10 UI architecture](docs/architecture/10-ui-architecture.md) | Routes, design system, components |
| [11 Deployment and operations](docs/architecture/11-deployment-and-operations.md) | Containers, configuration, Makefile, Helm |
| [12 Testing strategy](docs/architecture/12-testing-strategy.md) | Unit, integration, end-to-end |
| [13 Traceability and conformance](docs/architecture/13-traceability-and-conformance.md) | Requirement-to-test mapping, change log |

The same design is inside the product: the Architecture page (http://localhost:3000/architecture) has seven tabs (system context, layers, components, data flow, data model, call flows, deployment) with live component status. The draw.io source is [docs/design-diagrams/flamescope-architecture-v2.drawio](docs/design-diagrams/flamescope-architecture-v2.drawio); the page also offers it as a download.

## Repository layout

```
Makefile  pyproject.toml  .env.example  .gitignore  README.md
docs/
  architecture/            # the binding design documents 00 to 13
  design-diagrams/         # draw.io files
  decks/                   # pitch and demo decks, their build scripts
  images/                  # screenshots used in this README
prompts/                   # numbered build prompts
src/
  common/flamescope_common/        # settings, db, models, schemas, LLM gateway, rubric
  agents/flamescope_agents/        # agents, orchestrator, runtime prompt files
  api/flamescope_api/              # FastAPI app: routers, services, repositories
  ingest/flamescope_ingest/        # pipeline and CLI (flamescope-ingest)
  ui/                              # Next.js application
  data/                            # seed files, rubric.yaml, presets.yaml, overrides/
tests/
  unit/  integration/  e2e/
deploy/
  docker/                  # Dockerfile.api, Dockerfile.ingest, Dockerfile.ui, compose.yaml
  helm/flamescope/         # optional Kubernetes / OpenShift chart
  scripts/                 # doctor, wait and check scripts used by the Makefile
```

## Makefile targets

Run `make` or `make help` for this list. 26 targets.

| Target | Description |
|--------|-------------|
| `help` | List targets with descriptions (default) |
| `doctor` | Check docker, compose, python3.12, node, free ports and Ollama with its models |
| `ollama-pull` | Pull `LLM_MODEL` and `EMBED_MODEL` into Ollama on the host |
| `env` | Create `.env` from `.env.example` if missing |
| `venv` | Create `.venv` and install `-e ".[dev]"` |
| `ui-install` | `npm ci` in `src/ui` |
| `build` | `docker compose build` for api, ingest and ui |
| `deploy` | Bring up db, ingest job (migrate + seed), api and ui; wait for readiness; print URLs |
| `ingest-seed` | Re-run seed ingestion |
| `ingest-harvest` | Run harvest ingestion (requires `LLM_PROVIDER=ollama`) |
| `undeploy` | `docker compose down -v --remove-orphans` |
| `status` | `docker compose ps` plus `/ready` and `/meta/stats` summary |
| `logs` | Tail logs (`SERVICE=api` optional) |
| `restart` | Restart api and ui (re-reads `.env`) |
| `clean` | `undeploy` plus remove local images, `.venv`, `node_modules` and caches |
| `open` | Open the UI in the browser |
| `lint` | ruff, mypy, xenon, eslint, tsc |
| `fmt` | ruff format, prettier |
| `test-unit` | pytest `tests/unit` and `npm test` (Vitest); no Docker needed |
| `test-integration` | pytest `tests/integration` (builds, deploys, verifies APIs; leaves the stack running) |
| `test-e2e` | pytest `tests/e2e` with Playwright against the running stack |
| `test` | `test-unit`, `test-integration`, `test-e2e`, then undeploy verification (`KEEP_STACK=1` keeps the stack) |
| `all` | `build`, `deploy`, `test` |
| `helm-template` | Render the optional Helm chart |
| `helm-deploy` | Install or upgrade the Helm release |
| `helm-undeploy` | Uninstall the Helm release |

## Configuration

`make env` copies `.env.example` to `.env` (git-ignored). The Makefile and compose read `.env`; variables set in the shell win.

| Variable | Default | Meaning |
|----------|---------|---------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `flamescope` / `flamescope` / `flamescope` | Database bootstrap |
| `DATABASE_URL` | `postgresql+psycopg://flamescope:flamescope@db:5432/flamescope` | SQLAlchemy URL (use `localhost` outside containers) |
| `LLM_PROVIDER` | `ollama` | `mock` or `ollama` (unset means `mock`) |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama on the Mac host, seen from the containers |
| `LLM_MODEL` | `qwen2.5:0.5b` | Ollama chat model |
| `LLM_TIMEOUT_S` | `60` | Model call timeout in seconds |
| `EMBED_PROVIDER` | empty (follows `LLM_PROVIDER`) | `mock` or `ollama` |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model; its dimension must equal `EMBED_DIM` |
| `EMBED_DIM` | `768` | Vector dimension, fixed at migration |
| `PSI_BUCKET` / `PSI_REGION` / `PSI_PREFIX` | `nasa-psi` / `us-west-2` / empty | Harvest source |
| `HARVEST_MAX_DOC_MB` / `HARVEST_MAX_TABLE_MB` / `HARVEST_MAX_TABLES` / `HARVEST_MAX_TOTAL_MB` | `25` / `5` / `20` / `300` | Harvest download limits |
| `INGEST_COMMAND` | `seed` | Command the ingest container runs after `migrate` |
| `RAW_DIR` | `/data/raw` | Raw document volume inside the containers |
| `DATA_DIR` | `/app/src/data` | Seed files, rubric and presets inside the containers |
| `VERIFY_MIN_OVERLAP` | `0.35` | Citation checker threshold |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed browser origin for the API |
| `LOG_LEVEL` | `INFO` | Log level (JSON logs on stdout) |
| `API_INTERNAL_URL` | `http://api:8000` | UI rewrite target (a build argument of the UI image) |
| `API_PORT` / `UI_PORT` / `DB_PORT` | `8000` / `3000` / `5432` | Host ports |

## API

Base path `/api/v1`; JSON over HTTP, `POST /ask` streams Server-Sent Events. No authentication. OpenAPI at http://localhost:8000/api/v1/openapi.json, Swagger UI at http://localhost:8000/api/v1/docs. The running API registers exactly these 24 endpoints ([document 05](docs/architecture/05-api-specification.md)).

| Area | Endpoints |
|------|-----------|
| Health and meta | `GET /health`, `GET /ready`, `GET /meta/stats`, `GET /meta/status`, `GET /meta/rubric`, `GET /meta/presets` |
| Catalog | `GET /investigations`, `GET /investigations/{id}`, `GET /investigations/{id}/runs`, `GET /investigations/{id}/variables`, `GET /investigations/{id}/publications`, `GET /facets`, `GET /hardware`, `GET /projects` |
| Ranking | `POST /rank` |
| Compare | `POST /compare` |
| Scenario | `POST /scenario` |
| Extract | `POST /extract/preview`, `POST /extract/export`, `GET /extract/dictionary` |
| Insights and Earth | `GET /insights/safety-tech`, `GET /insights/gaps`, `GET /earth-applications` |
| Ask | `POST /ask` (SSE: `meta`, `token`, `citations`, `related`, `done`, `error`) |

Ranking with the lunar-habitat preset (no model call):

```bash
curl -s -X POST http://localhost:8000/api/v1/rank -H 'Content-Type: application/json' -d '{"lens": "habitat", "preset": "lunar_habitat", "limit": 3}'
```

```text
{"lens":"habitat","rubric_version":"2026.11-1","weights_used":{"lens_weights":{"habitat":0.6,"modeling":0.2,"controls":0.2},
 "criterion_weights":{"habitat":{"fuel_realism":0.25,"atmosphere_match":0.35,"flow_regime":0.05,"phenomenon":0.15,"gravity_bounding":0.2},...}},
 "items":[{"rank":1,"acronym":"FLEX-2","title":"Flame Extinguishment Experiment - 2","score":81.0,"confidence":1.0,
           "lens_scores":{"habitat":81.0,"modeling":81.3,"controls":70.9},"breakdown":[...]},
          {"rank":2,"acronym":"SAME-R",...,"score":78.5,"confidence":0.65,...},
          {"rank":3,"acronym":"SAME",...,"score":75.4,"confidence":0.65,...}],
 "disclaimer":"Scores are relative decision aids, not safety certifications."}
```

Scenario Lab with the lunar-habitat preset (34 % oxygen, 56.5 kPa, 0.166 g, 10 cm/s), without the model-written explanation:

```bash
curl -s -X POST http://localhost:8000/api/v1/scenario -H 'Content-Type: application/json' -d '{"preset": "lunar_habitat", "explain": false, "limit": 3}'
```

```text
{"scenario":{"preset":"lunar_habitat","o2_fraction":0.34,"pressure_kpa":56.5,"gravity_g":0.166,"flow_speed_cm_s":10.0,...,"assumed_default":true},
 "coverage":{"o2_fraction":{"state":"covered","catalog_range":[0.12,0.85],...},
             "pressure_kpa":{"state":"covered","catalog_range":[25.331,506.625],...},
             "flow_speed_cm_s":{"state":"covered","catalog_range":[0.0,85.28],...},
             "gravity_g":{"state":"no_data","catalog_range":null,"catalog_values":[0.0,1.0]}},
 "matches":[{"acronym":"FLEX-2","similarity":0.9627...,"matching_runs":8,...},
            {"acronym":"BASS-II","similarity":0.8858...,"matching_runs":4,...},
            {"acronym":"CFI-G","similarity":0.7954...,"matching_runs":217,...}],
 "gravity_bounding":{"partial_gravity_data":false,
   "lower_bound":{"gravity_g":0.0,"investigations":["BASS-II","CFI-G","FLEX-2"]},
   "upper_bound":{"gravity_g":1.0,"investigations":[]},
   "analogue":{"acronym":"E-FIELD-Flames",...},
   "statement":"The scenario gravity is 0.166 g. PSI holds no partial-gravity combustion data yet. Microgravity (0 g) and normal-gravity (1 g) results bound the behaviour at this gravity. LUCI and FM2 are expected to add partial-gravity data."},
 "explanation":{"text":"","sentences":[],"status":"skipped"},"scenario_id":"eyJhc3N1bWVkX2RlZmF1bHQiOnRydWUs..."}
```

Ranking order reflects the ratings stored at deploy time, so it can differ on your stack (see [LLM modes](#llm-modes)).

## Scoring method

Each investigation is rated 0 to 5, with evidence, on five criteria in each of three lenses: **habitat** relevance (O1), **modeling** value (O2) and **controls** and equipment value (O3). A criterion without evidence is null and is left out rather than counted as zero.

```text
lens_score     = 20 * sum(w_i * v_i) / sum(w_i)          over criteria with a value; 0..100
confidence     = sum(w_i)                                 share of weight that has evidence; 0..1
overall        = sum(W_l * lens_score_l) / sum(W_l)       default W: habitat 0.4, modeling 0.3, controls 0.3
```

Weights are normalized, so only their ratios matter. Presets (`balanced`, `lunar_habitat`, `spacecraft_cabin`, `modeler`, `equipment_designer`) set lens and criterion weights; the user can move any slider and re-rank without a model call.

Scores are relative decision aids, not safety certifications. The UI states this wherever scores appear. Full rubric, presets, scenario distance and worked examples: [document 08](docs/architecture/08-scoring-and-scenario.md).

## Data and provenance

An investigation card holds objectives, approach, fuels (phase, material, geometry), test conditions (oxygen fraction, pressure, flow speed, gravity), varied and fixed parameters, measurements, hardware, findings, publications, fire-safety tags and PSI links ([document 04](docs/architecture/04-data-model.md)).

- **Seed files**: `src/data/seed/investigations/` holds 25 YAML files covering all 24 PSI Combustion Science records (PSI-47 holds DAFT and DAFT-2, seeded as two files): 20 flight investigations and 5 ground investigations under their PSI accession keys. Hardware, fuel taxonomy, Earth applications and the S3 map sit next to them in `src/data/seed/`; the rubric and presets in `src/data/`.
- **Sources**: curated from the PSI public data service (repository records and experimental tables), NTRS records and NASA pages. Test runs are individual where a PSI experimental table lists them, aggregate ranges where only a range is stated, and absent where no source states conditions.
- **Rules**: every fact carries a source reference (kind, URI, locator, quote); unknown values stay `null` and are never guessed. All 25 cards are marked `reviewed: false` (not yet human-reviewed).
- **Partial-gravity gap**: PSI holds no partial-gravity combustion data. The Scenario Lab shows gravity coverage as "no data", lists the 0 g and 1 g investigations as lower and upper bounds, names E-FIELD Flames as the analogue and states that LUCI and FM2 are expected to add data. The Overview gaps card repeats it.

## Testing

All test levels force mock mode and seed data, so they are deterministic and need no model; the one exception is the optional `ollama`-marked integration test, which runs only when Ollama answers with both models pulled.

| Level | Location | Covers | Command |
|-------|----------|--------|---------|
| Unit | `tests/unit/`, `src/ui/**/*.test.ts(x)` | Logic, schemas, agents on the mock gateway, services with fakes, UI components, docs conformance | `make test-unit` |
| Integration | `tests/integration/` | Build, deploy, database, ingestion, every API endpoint, performance, UI smoke | `make test-integration` |
| End-to-end | `tests/e2e/` | Every UI route with Playwright, accessibility, screenshots, undeploy | `make test-e2e` |

`make test` runs all three levels and then verifies that undeploy leaves no containers, networks or volumes. `KEEP_STACK=1 make test` leaves the stack running. JUnit XML and HTML reports go to `tests/reports/`; end-to-end screenshots go to `tests/e2e/artifacts/`.

Last full `make test` on this machine (Apple Silicon):

| Suite | Result | Time |
|-------|--------|------|
| pytest unit | 1,136 passed, 1 expected failure (this README, now present) | 29 s |
| Vitest | 225 passed | 5 s |
| pytest integration | 247 passed | 88 s |
| pytest end-to-end | 108 passed | 147 s |
| Undeploy check | no containers, networks or volumes remain | - |

With this README in place, `pytest tests/unit` reports 1,137 passed and no expected failures (44 s).

## Optional: Kubernetes and OpenShift

`deploy/helm/flamescope/` holds a chart with Deployments `api` and `ui`, a StatefulSet `db` with a PVC, an `ingest` Job (post-install and post-upgrade hook), a `raw` PVC, ConfigMap, Secret, Services, optional Ingress or OpenShift Route and a NetworkPolicy.

```bash
make helm-template
make helm-deploy
make helm-undeploy
```

Key values: `llm.provider` (defaults to `mock`, because a cluster has no host Ollama), `llm.ollamaBaseUrl`, `llm.model`, `embed.dim`, `ingest.command`, `image.registry` and `image.*.tag`, `route.enabled` and `route.host`, `ingress.enabled`. Override them with `helm` directly or edit `values.yaml`.

The Helm path was not verified for this README: `helm` is not installed on the verification machine, and the targets stop with an install hint when it is missing.

## Troubleshooting

| Problem | What to do |
|---------|------------|
| Docker not running | Start Docker Desktop (`open -a Docker`) or `colima start`, then `make doctor`. |
| Port in use | `lsof -nP -iTCP:3000 -sTCP:LISTEN` (or 8000, 5432) to find the process; or set `UI_PORT`, `API_PORT` or `DB_PORT` in `.env`. |
| `python3.12 not found` in `make doctor` | `make doctor PYTHON=/path/to/python3.12` |
| Ollama check fails | Start Ollama, then `make ollama-pull`; or deploy offline with `LLM_PROVIDER=mock EMBED_PROVIDER=mock make deploy`. |
| Stack not ready | `make status`, then `make logs SERVICE=api` (or `ui`, `db`, `ingest`). With a slow model, give readiness more time: `make deploy WAIT_TIMEOUT=900`. |
| Reset the data | `make undeploy && make deploy` |
| Apple Silicon | Images build natively for `linux/arm64` with no architecture pins. Ollama runs natively on the host so it can use the GPU; containers reach it at `host.docker.internal:11434`. |

## Project decks

| File | Content |
|------|---------|
| [docs/decks/flamescope-pitch.pptx](docs/decks/flamescope-pitch.pptx) | The Space Apps submission deck, 7 slides ([source](docs/decks/flamescope-pitch.md)) |
| [docs/decks/flamescope-demo.pptx](docs/decks/flamescope-demo.pptx) | Detailed companion deck, 43 slides ([source](docs/decks/flamescope-demo.md)) |
| [docs/decks/flamescope-demo-script.md](docs/decks/flamescope-demo-script.md) | Three-minute live demo script |
| [docs/decks/demo-checklist.md](docs/decks/demo-checklist.md) | Pre-demo checklist |

The decks are built by the Python scripts next to them (`pip install -e ".[docs]"`, then `python docs/decks/build_pitch.py`). Their screenshots live in `docs/decks/screens/`, which is git-ignored: recapture them from the running stack before rebuilding a deck.

## Data source and acknowledgements

- Data: NASA Physical Sciences Informatics (PSI), Combustion Science (https://psi.nasa.gov), with NASA Technical Reports Server records and NASA pages cited per fact.
- Built for the NASA Space Apps Challenge 2026, challenge "Flame in Freefall".
- This project is not affiliated with or endorsed by NASA.

## Team

Dragonator: Ayaan, Mujtaba, Amudhan

Repository: https://github.com/AyaanAsish/flamescope
