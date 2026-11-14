# FlameScope, explained

A guide for team members: what the app does, what each tab shows, and how the backend works. The binding design lives in `docs/architecture/`; this page is the plain-language tour.

## 1. What the app is for

NASA's **Physical Sciences Informatics (PSI)** repository holds data from about 24 combustion experiments run in microgravity, mostly on the ISS: roughly 12 TB of videos, sensor files, reports and papers. Nobody can read all of it to answer a practical question like:

> *"We're designing a lunar habitat with 34% oxygen at 8.2 psi. Which past fire experiments tell us anything about how a fire would behave there?"*

FlameScope reads the experiments once, turns each into a structured summary, scores it for relevance, and gives you tools to search, rank, compare and query them. It serves the four challenge goals of NASA Space Apps 2026, "Flame in Freefall":

| Goal | Plain meaning | Main tabs |
|---|---|---|
| O1 | Which experiments matter for crew fire safety? | Overview, Ranking, Scenario Lab |
| O2 | Get numbers out for fire models | Data Extract, Ranking (modeling lens) |
| O3 | What informs detectors, extinguishers and materials? | Safety Tech, Ranking (controls lens) |
| O4 | Earth spin-offs | Earth Apps |

## 2. Why the UI looks sparse right now

The data is placeholder, so much of what you see is an empty state.

- **14 "stub" cards.** The PSI website renders in the browser and could not be read automatically, so each card only has facts that could actually be sourced: the acronym, platform, and some hardware. Titles are just acronyms, and objectives, fuels, findings and publications are empty (`null`). The project rule is "unknown is null, never invent", so the cards are sparse but true.
- **No test runs.** No experiment has individual tests recorded yet. That is why the Overview scatter, the Scenario Lab matches, Data Extract rows, Safety Tech findings and the investigation "Runs" tab are mostly empty.
- **Scores are fake in mock mode.** In mock mode (badge `mock` in the top bar), a deterministic stand-in replaces the AI so the system works offline and tests are repeatable. The mock scorer produces rule-based numbers, not real scientific judgements. Treat every number on the Ranking page as a demo of the mechanics, not a verdict about an experiment.
- **One real number.** CFI-G's "up to 85% oxygen" comes from the challenge text.

The machinery is all built and tested. It needs real content, either from people curating the seed files or from running harvest mode with a real model.

## 3. Concepts you will see everywhere

- **Investigation card.** A one-page structured summary of one experiment:
  - objectives and approach
  - fuels: phase (solid, liquid or gas), material, shape and size
  - test conditions: oxygen fraction, pressure, flow speed, gravity
  - what was varied versus held fixed
  - measurements and hardware
  - publications and findings

  Every fact carries a **source**, a link to the PSI page, file or DOI it came from.
- **Test run.** One burn inside an experiment, with its own conditions and outcomes. An *aggregate run* stands for a stated range ("oxygen from 0.2 to 0.4") rather than one test.
- **Lens.** One point of view for scoring. There are three, each with five **criteria** rated 0 to 5:
  - **Habitat relevance:** fuel realism, atmosphere match, flow regime, phenomenon, gravity bounding.
  - **Modeling value:** quantitative outputs, parameter sweep, geometry, data accessibility, model validation.
  - **Controls value:** detection, suppression, material screening, post-fire hazards, hardware heritage.
- **Score.** For one lens: `20 × weighted average of the criterion ratings`, giving 0 to 100. Criteria with no evidence (`null`) are left out rather than counted as zero.
- **Overall score.** A weighted mix of the three lenses, by default habitat 40%, modeling 30%, controls 30%.
- **Confidence.** The share of the weight that actually had evidence. An 85% confidence means 15% of the criteria weight was unknown.
- **Evidence.** Every non-null rating has a rationale and a quoted source. "Evidence" buttons open these.
- **Scenario.** A hypothetical environment: oxygen %, pressure, gravity, airflow, and optionally a fuel.
- **Similarity.** 0 to 1, how close a past run's conditions are to your scenario.
- **Coverage.** Per dimension, whether your scenario value falls inside what the catalog tested:
  - **covered:** inside the tested range.
  - **extrapolated:** outside the tested range.
  - **no data:** nothing was tested on that dimension.
- **Partial-gravity gap.** PSI has fire data at 0 g (orbit) and 1 g (Earth), but nothing in between, such as the Moon at 0.166 g or Mars at 0.38 g.
  - The app never invents a number for those gravities.
  - It states the gap, uses 0 g and 1 g results as the lower and upper bounds, and names E-FIELD Flames as the closest analogue.
  - Gravity is deliberately not part of similarity.
- **Mock versus live mode.**
  - **Mock** (`LLM_PROVIDER=mock`): fake but deterministic AI, works offline. Used by all tests.
  - **Live** (`LLM_PROVIDER=ollama`): a real model through Ollama on the host Mac. The model is set by `LLM_MODEL` in `.env`.

## 4. Tab by tab

### Overview (`/`)

This is the landing dashboard.

- **Stat tiles:** counts of investigations, runs, publications and findings, plus the oxygen and pressure ranges in the catalog.
- **Parameter-space scatter:** every test run plotted as oxygen against pressure, coloured by fuel phase, with the lunar-habitat envelope (oxygen at least 30%, pressure at most 10.2 psi) drawn as a box. It stays empty until runs exist.
- **Top five:** the five best overall-ranked investigations.
- **Gaps card:** what the data doesn't cover, always including the partial-gravity gap.

The page makes four API calls at once: `/meta/stats`, `/rank`, `/insights/gaps` and `/extract/preview`. None of them uses an LLM.

### Explorer and investigation detail (`/explorer`, `/investigations/[id]`)

This is the searchable catalog.

- Filter by fuel phase, material, hardware, project, oxygen or pressure range, or tags; free-text search; sort. The filters are mirrored in the URL, so links are shareable.
- Click a card to open the detail page:
  - The header has a link to the PSI page.
  - **Overview:** objectives and approach.
  - **Conditions:** the condition ranges.
  - **Runs:** a table of the individual tests.
  - **Variables:** what was varied versus fixed across runs.
  - **Scores:** the per-lens breakdown with source links.
  - **Publications.**
  - **Data:** where the raw files sit in the S3 bucket, with sizes and types. FlameScope never downloads videos.

Backend: `CatalogService` reads the `investigation`, `test_run`, `condition` and `publication` tables. Search combines PostgreSQL full-text search with filters.

### Ranking (`/ranking`)

This answers "which experiments matter most for my purpose?"

- **Lens tabs:** habitat, modeling, controls or overall.
- **Presets:** one-click weightings, for example:
  - `lunar_habitat` emphasizes atmosphere match.
  - `equipment_designer` emphasizes detection and suppression.
  - `modeler` emphasizes data quality.
- **Sliders:** adjust any lens or criterion weight. Scores recompute almost instantly, because this is pure arithmetic with no AI. That's a deliberate design choice: the stored ratings come from AI at ingestion time, but the ranking you see is transparent maths you can audit and tune.
- **Stacked bar per row:** how much each criterion contributed to the score.
- **Evidence drawer:** why each criterion got its rating, with the quote and source.
- **Disclaimer:** scores are decision aids, not safety certifications.

### Compare (`/compare`)

Pick 2 to 4 investigations side by side.

- **Diff matrix:** one row per attribute (platform, fuels, oxygen range, pressure, hardware and so on), marking same or different with an icon, not just colour.
- **Narrative:** a short AI-written comparison. Each sentence cites the facts it relies on. A **citation verifier** deletes any sentence its cited facts don't support, so nothing uncited survives. This is one of only three places the app calls an LLM while you use it.
- **Lineage graph:** which investigations share hardware or instruments. For example, two experiments might use the same rack, or a smoke instrument reused from SAME in DAFT.

### Scenario Lab (`/scenario`)

This answers "what evidence exists for *my* environment?"

- Enter oxygen, pressure, gravity, airflow and an optional fuel, or pick a preset:

  | Preset | O₂ | Pressure | Gravity |
  |---|---|---|---|
  | Lunar habitat | 34% | 8.2 psi | 0.166 g |
  | ISS cabin | 21% | 14.7 psi | 0 g |
  | Spacesuit | 100% | 4.3 psi | 0 g |
  | Mars habitat | 34% | 8.2 psi | 0.38 g |
  | Lunar threshold | 30% | 10.2 psi | 0.166 g |

  Lunar habitat and Mars habitat are labelled "assumed default" in the UI: their atmospheres are design assumptions, not values from the challenge.
- **Match list:** experiments ranked by how close their runs are to your scenario. It is empty until runs exist.
- **Coverage panel:** covered, extrapolated or no data for each dimension.
- **Gravity-bounding card:** the partial-gravity statement. It disappears at 0 g or 1 g, because those are the bounds themselves.
- **Explain:** an AI-written interpretation, citation-checked like Compare. Coverage caveats are appended automatically.
- **Export matching runs:** downloads the matched runs as CSV.

### Data Extract (`/extract`)

This is for modelers.

- Build a table of test runs with chosen columns (conditions, outcomes) and filters.
- Every row carries **provenance columns**: where each value came from.
- Export as CSV (with a commented header block describing the export) or JSON.
- The **dictionary** explains every column and its unit.

### Safety Tech (`/safety-tech`)

Findings grouped by what they inform:

- detection
- suppression
- material screening
- post-fire and cleanup
- atmosphere design
- partial gravity

Each finding links to its experiment and source. It also lists **gaps**:

- the partial-gravity gap;
- regions of the oxygen–pressure grid that no experiment covers, with regions inside the lunar envelope listed first.

It stays empty until the cards have findings.

### Earth Apps (`/earth`)

Terrestrial spin-offs: fine water mist extinguishers, smoke detection and firefighter gear. Filter by sector. People curate these entries in `src/data/seed/earth_applications.yaml`. In harvest mode an AI proposes candidates to a file for review, never straight into the app.

### Ask (`/ask`)

A chat over the curated content. The backend steps are:

1. Embed your question as a vector.
2. Find matching text chunks two ways, by keyword and by vector similarity, and merge the two rankings.
3. Send the top chunks to the AI.
4. Stream the answer word by word.
5. Run the citation verifier, which drops unsupported sentences and leaves chips linking to sources.

An off-topic question such as "What is the capital of France?" scores too low on relevance, so you get a fixed "not enough information" sentence instead of a made-up answer.

### Architecture (`/architecture`)

How FlameScope itself is built, for judges and developers. It has seven tabs:

- **Context:** who uses the system and what it talks to.
- **Layers:** UI, API, services, agents, data.
- **Components:** the 12 parts, clickable for responsibilities, files and related flows.
- **Data flow:** the ingestion stages.
- **Data model:** the tables.
- **Deployment:** the containers.
- **Call flows:** 13 sequence diagrams, CF-01 to CF-13.

The status badges are live from `/meta/status`, and there's a draw.io download.

## 5. How the backend works

### The containers (`make deploy`)

```
Browser ──> ui (Next.js, :3000) ──/api/* rewrite──> api (FastAPI, :8000) ──> db (PostgreSQL + pgvector)
                                                          │
                                                          └─> Ollama on the Mac (only for Ask, Compare narrative, Scenario explain)
ingest (one-shot job at deploy) ──> fills db from seed files
```

The browser only ever talks to the UI server, which forwards `/api/*` to the API. The UI never touches the database or the AI directly.

### Inside the API, for every request

1. **Router:** checks the request shape and rejects bad input with a standard error envelope, using 400, 404 or 422.
2. **Service:** does the logic. Nine services:
   - Catalog, Ranking, Compare, Scenario, Extract, Insight (Ask), SafetyTech, Earth, Meta.
   - All of them are deterministic Python.
3. **Repository:** the only code that runs SQL.
4. **Orchestrator:** only Compare, Scenario and Insight call it, to run an AI agent. Its output is validated against a strict schema, retried up to 2 times, then passed through the citation verifier.

Example: when you move a Ranking slider, the API runs `POST /rank`, which goes to `RankingService`. That service reads the stored criterion ratings from the `relevance_score` table, applies the formula with your weights, and returns the scores, the breakdown and the evidence. This takes a few milliseconds with no AI involved.

### The database (17 tables)

| Group | Tables |
|---|---|
| Catalog | `project`, `hardware`, `investigation`, `investigation_hardware` (which experiment used which rack), `fuel`, `test_run`, `condition`, `measurement`, `publication`, `finding` |
| Earth | `earth_application`, `finding_earth_application`, `earth_application_investigation` |
| Scoring | `relevance_score`: one row per investigation per criterion, with value, rationale and evidence |
| Search | `chunk`: text passages, each with a 768-number vector for similarity search and a full-text index |
| Operations | `ingest_run` (audit log of each ingestion), `llm_cache` (saved AI replies so identical calls aren't repeated) |

### The AI agents (Google ADK)

| Agent | When it runs | What it does |
|---|---|---|
| Extractor | ingestion (harvest mode) | Reads parsed documents and drafts a card; every quote is checked against the source text |
| Scorer | ingestion | Rates the 15 criteria from 0 to 5, with evidence |
| Earth apps | ingestion review (harvest mode) | Proposes Earth applications for human review |
| Comparator | Compare, when narrative is requested | Writes the cited comparison |
| Scenario interpreter | Scenario Lab, Explain | Writes the cited interpretation |
| Insight QA | Ask | Answers from retrieved chunks with citations |

All of them go through one **LLM gateway**, which picks `mock` or `ollama` from `.env`. Nothing else in the code knows which model is in use.

### Ingestion (how data gets in)

There are two modes:

- **Seed** (what runs at deploy): loads the YAML files in `src/data/seed/`. It needs no network. If a card has no scores, the scorer agent rates it.
- **Harvest** (`make ingest-harvest`, which needs live mode). Its stages:
  1. **discover:** list the public `nasa-psi` S3 bucket.
  2. **harvest:** download the overview pages, documents and small tables, skipping video and huge files.
  3. **parse:** extract text and tables from HTML, PDF, CSV and XLSX.
  4. **extract:** the AI drafts the card.
  5. **normalize:** standardize units and vocabulary.
  6. **link:** connect hardware, projects and DOIs.
  7. **score:** the AI rates the criteria.
  8. **index:** split the text into chunks and embed them.
  9. **review:** flag low-confidence fields.

  Human **overrides** in `src/data/overrides/` always win over AI output. Re-running is safe: unchanged inputs are skipped.

## 6. Running it

| Command | What it does |
|---|---|
| `make deploy` | Builds if needed, starts the database, seeds it, starts the API and UI |
| `make status` | Container health plus readiness and dataset counts |
| `make open` | Opens the UI at http://localhost:3000 (API docs at http://localhost:8000/api/v1/docs) |
| `make restart` | Picks up `.env` changes (for example switching between mock and live mode) |
| `make undeploy` | Stops everything and removes the containers and volumes |
| `make test` | Unit, integration and end-to-end tests, then undeploy |

## 7. Acronyms you will see

- **PSI:** Physical Sciences Informatics, NASA's repository.
- **ISS:** International Space Station.
- **CIR:** Combustion Integrated Rack.
- **MSG:** Microgravity Science Glovebox.
- **MDCA:** Multi-user Droplet Combustion Apparatus.
- **ACME:** Advanced Combustion via Microgravity Experiments.
- **Experiment acronyms:**
  - FLEX / FLEX-2: droplet flame extinguishment
  - BASS / BASS-II: burning and suppression of solids
  - SAME / SAME-R: smoke aerosol measurement
  - DAFT / DAFT-2: dust and aerosol measurement feasibility
  - CFI / CFI-G: cool flames
  - SPICE: smoke point in co-flow
  - SLICE: lifted flames
  - BRE: burning rate emulator
  - E-FIELD Flames: flames in electric fields, the partial-gravity analogue

These expansions are general orientation, not sourced facts; the app itself only shows titles it could source, which is why the cards currently display bare acronyms.

## 8. What would make the app meaningful

Real content. Seed cards filled from PSI pages and publications, with test runs, findings and fuels, are what populate the scatter, the scenario matches, the extract table, the Safety Tech findings and evidence-based scores. Each fact needs a source reference; unknown values stay `null`.
