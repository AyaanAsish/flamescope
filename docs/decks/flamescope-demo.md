# FlameScope - live demo (detailed companion deck)

**This is the detailed companion deck for the live demo. It is not the Space Apps submission: the submission is the separate 7-slide pitch deck (`flamescope-pitch.pptx`).** This deck has no slide limit. Slides 4 to 21 replay the three-minute live path with real captures and serve as the fallback if the network or laptop fails; slides 22 to 43 explain the backend and the data in detail.

- Build: `.venv/bin/python docs/decks/build_demo.py` (reads the speaker notes below, writes `flamescope-demo.pptx`, then runs `verify_demo.py`).
- Screens: `docs/decks/screens/demo/`, 1440x900 captures of the live stack (`LLM_PROVIDER=ollama`, model `deepseek-v4-pro:cloud`, seed data: 25 investigations, 2,003 test runs) on 2026-11-14.
- Script and timings: `flamescope-demo-script.md`. Checklist: `demo-checklist.md`.
- Facts come only from `docs/architecture/`, the repository (including the seed files and their sources), the running stack (`/api/v1/meta/stats`, `/meta/status` and the other endpoints) and `tests/reports/`. NASA and PSI challenge facts come only from doc 01.
- Placeholders: `{{PRESENTER}}`, `{{DATE}}`.

Live steps carry a time window (0:00 to 3:00, 180 s in total). Reference slides carry no timing; skip them live.

## Slide 1 - FlameScope - live demo

On the slide: challenge line, one-sentence purpose, companion-deck note, presenter and date placeholders, the Overview stat tiles from the live stack.

### Speaker notes
Not timed. Open on this slide while the browser is ready on http://localhost:3000 in a second window. Say: "This is the live walkthrough of FlameScope. The 7-slide pitch is our submission; this deck is the detailed companion, and every product slide is a real capture of the running stack, so if anything fails I simply keep going on the slides." The tiles on the slide are the live catalog: 25 investigations, 2,003 test runs, 355 publications, 40 findings, 215 indexed chunks, 6 hardware. Then switch to the browser for step 1.

## Slide 2 - She needs PSI evidence for a lunar habitat in an afternoon.

On the slide: the user (habitat fire-safety engineer, doc 01 section 2), her question, the challenge facts of doc 01 section 6, the four objectives O1 to O4.

### Speaker notes
Not timed (20 seconds if used before the demo). Say: "Our user is a habitat fire-safety engineer choosing materials and detection for a lunar habitat. The challenge tells us lunar habitats will run at 30 percent oxygen or more and 10.2 psi or less, which makes materials more flammable, and that PSI has no partial-gravity combustion data yet. Her question: which PSI investigations tell her anything about that environment? She needs relevance, numbers for models, equipment insight, and Earth spin-offs - the four challenge objectives." The 34 percent and 8.2 psi values are the lunar_habitat preset, labelled "assumed default" in the product because they are a design assumption inside the challenge envelope.

## Slide 3 - Ten stops, three minutes, every challenge objective covered.

On the slide: the ten steps with route, seconds and objective.

### Speaker notes
Not timed. Walk the map in one breath: Overview, Ranking, a detail page, Compare, Scenario Lab, Data Extract, Safety Tech, Ask, Earth Apps, Architecture. Click targets throughout are the sidebar labels exactly as shown: "Overview", "Ranking", "Compare", "Scenario Lab", "Data Extract", "Safety Tech", "Ask", "Earth Apps", "Architecture". Budget: 20, 25, 15, 20, 25, 15, 10, 25, 10, 15 seconds = 180 seconds. Every step was executed with Playwright against the live stack on 2026-11-14 using the visible labels only; the machine response for the whole path was 6.7 seconds (with the compare narrative and the scenario explanation already cached by the rehearsal), so the budget is talking time.

## Slide 4 - Overview maps 2,003 PSI test runs against the lunar envelope.

On the slide: Overview capture with callouts 1 LLM badge, 2 dataset badge, 3 stat tiles, 4 catalog ranges, 5 the shaded lunar-habitat envelope on the coverage scatter.

### Speaker notes
Step 1, 0:00 to 0:20 (20 s). Click: browser on http://localhost:3000 (sidebar "Overview"). Point at the top-bar LLM badge: it reads "ollama · deepseek-v4-pro:cloud", the live model; in mock mode it reads "mock". The dataset badge reads "seed · 25 investigations". Tiles straight from GET /api/v1/meta/stats: 25 investigations (9 gas, 6 liquid, 8 solid), 2,003 test runs, 355 publications, 40 findings, 215 indexed chunks, 6 hardware; "Catalog covers oxygen 12 % – 85 % and pressure 25.3 kPa – 506.6 kPa." Say: "This is every PSI combustion investigation, 2,003 test runs on one map, and the shaded box is her lunar habitat." The scatter plots every run with oxygen and pressure values, coloured by fuel phase (gas blue, liquid violet diamonds, solid orange): the gas-jet runs reach into the envelope (30 % oxygen or more, 70.3 kPa or less), and most liquid and solid runs sit near air at about one atmosphere. Scroll on to "Evidence gaps": "No partial-gravity data" (Related: E-FIELD-Flames, Expected: LUCI, FM2) and "Untested oxygen and pressure region" of 116 grid cells. The page makes four parallel calls (CF-11): /meta/stats, /rank, /insights/gaps and /extract/preview with limit 5000, so one request carries every run; none uses an LLM. Top 5 overall with default weights: PSI-115 84 (confidence 45 %), FLEX 80.7, BASS 75.1, BASS-II 74.8, SAME-R 74.7.

## Slide 5 - The lunar preset re-ranks instantly, with no AI at query time.

On the slide: Ranking capture with callouts 1 preset select, 2 Habitat tab, 3 weights panel, 4 top row FLEX 80.

### Speaker notes
Step 2, 0:20 to 0:45 (25 s, shared with slide 6). Click: sidebar "Ranking"; PRESET select: "Lunar habitat"; lens tab "Habitat". Say: "Her priorities re-rank all 25 investigations instantly: pure arithmetic over stored, cited ratings, no AI at query time." Point at the lens weights (Habitat 60 % share, Modeling 20, Controls 20) and the habitat criterion sliders (fuel realism 25 %, atmosphere match 35, flow regime 5, phenomenon 15, gravity bounding 20). The Habitat order: FLEX 80, BASS 78.5, SAME-R 78.5, FLEX-2 74, BASS-II 73, PSI-62 70, SAFFIRE-III 69.2, BRE 68. BASS and SAME-R tie on the rounded score and confidence (65 %), so the acronym decides, case-insensitively. The page asks for up to 100 rows, so every investigation is ranked. Optional: drag any slider; the UI debounces 250 ms and keeps the previous rows while refetching. The disclaimer "Scores are relative decision aids, not safety certifications." sits under the title.

## Slide 6 - Every score opens its rationale, its source and its origin.

On the slide: the FLEX evidence drawer with callouts on atmosphere match 5 / 5, its weight and contribution, the source links, the origin chip.

### Speaker notes
Step 2 continued (inside 0:20 to 0:45). Click: "Evidence" on the first row (FLEX). Say: "Every rating shows its rationale and source; FLEX ran from 12 to 34 percent oxygen at reduced and raised pressure." Read one: "Atmosphere match, 5 / 5, weight 35 %, contributes 35 points: the oxygen fraction range is 0.12 to 0.34, covering 30%+ oxygen, and pressure ranges from 70.168 to 309.295 kPa, including reduced pressure." Each claim links to the card field it rests on (card.conditions.o2_fraction.min and so on). The "llm" chip is the origin: these ratings were produced by the scorer at seed time; ratings can also come from seed files or curator overrides. The five habitat ratings are fuel realism 3, atmosphere match 5, flow regime 3, phenomenon 5, gravity bounding 3, contributing 15 + 35 + 3 + 15 + 12 = 80. Press Esc to close the drawer.

## Slide 7 - The detail card links every stated fact to its PSI source.

On the slide: FLEX detail with callouts on the badges, the tabs, View in PSI, a source link, the Conditions panel.

### Speaker notes
Step 3, 0:45 to 1:00 (15 s, shared with slide 8). Click: the "FLEX" name in the first ranking row. Say: "One card per investigation: fuels, hardware and conditions, every statement linked to its PSI source." Badges: Liquid, ISS, Microgravity, Unreviewed, 274 test runs. Summary: FLEX burned single methanol and n-heptane droplets in the Multi-user Droplet Combustion Apparatus of the Combustion Integrated Rack; the approach cites "PSI investigation PSI-69, Flame Extinguishment Experiment (approach (PSI repository record, geode-py API))". Conditions: oxygen 12 % – 34 %, pressure 70.2 kPa – 309.3 kPa, flow n/a, microgravity; hardware CIR and MDCA. "View in PSI" opens the PSI-69 investigation page. "Unreviewed" means curated from sources but not yet signed off by a person. "Open questions" lists what the sources did not state.

## Slide 8 - Test runs page through every row of the PSI experimental table.

On the slide: the Test runs tab scrolled to the bottom of page 2, with callouts on a run, its conditions, its source link, the row count and the pager.

### Speaker notes
Step 3 continued (inside 0:45 to 1:00). Click: tab "Test runs"; scroll down; "Next". Say: "All 274 FLEX tests are here, one row of the PSI experimental table each, paged 100 at a time." The pager reads "274 total, page 1 of 3", then "page 2 of 3"; under the table: "Showing 100 of 274 runs. Missing values are unknown, not zero." Each run lists fuel and phase, oxygen, pressure, flow, direction, gravity, spread rate, ignition, confidence (90 % on these FLEX rows) and links to "PSI-69 Experimental table", with the row in the locator. Pressure was converted from mmHg at 101.325 kPa per 760 mmHg, as each locator states. The table is keyboard-focusable, so it scrolls without a mouse. Reference, not live: the Variables tab lists the varied oxygen fractions (12 % to 34 %) and pressures and the fixed gravity 0 g; the Scores tab shows Overall 80.7 / 100 and the Habitat lens at 78 with rubric defaults; the Data tab shows the S3 prefix. FlameScope references raw data by key and never bulk-downloads it (NFR-10). Endpoints: GET /investigations/{id}, /runs (page and page_size, max 100), /variables, /publications (CF-04).

## Slide 9 - Explorer filters the catalog by fuel, atmosphere, hardware, phenomenon.

On the slide: Explorer capture with callouts on facet filters, sort, Compare tray, per-lens scores.

### Speaker notes
Reference slide, optional detour (not timed). Click: sidebar "Explorer". Facets: search, fuel phase (Gas 9, Solid 8, Liquid 6), gravity (Microgravity 20, Mixed 4, Normal 1), project (ACME 6), O2 and pressure ranges, hardware (CIR 9, ACME insert 6, MSG 6, Smoke and dust instrument 4, SPICE flow duct 4, MDCA 3) and phenomena with counts (Extinction 12, Flow effects 10, Gaseous fuel 9 and more). Filters are mirrored in the URL, so a filtered view is shareable. Each card shows acronym, title, badges, the oxygen, pressure and flow ranges and the four scores, plus "Add to compare"; the Compare tray carries that selection to the Compare page. Backend: GET /investigations and GET /facets in parallel; PostgreSQL full-text search plus filters (CF-04).

## Slide 10 - Compare marks same and different with icons, not colour alone.

On the slide: diff matrix with callouts on the picker, the selected chips, the Different hardware row, a Same marker.

### Speaker notes
Step 4, 1:00 to 1:20 (20 s, shared with slide 11). Click: sidebar "Compare"; ADD INVESTIGATION select: "FLEX - Flame Extinguishment Experiment", then "SPICE - Smoke Point In Co-flow Experiment", then "SAFFIRE-II - Spacecraft Fire Experiment-II". Say: "A droplet study, a gas-jet study and a solid-materials study side by side: same and different at a glance." Same: Project n/a, Platform ISS. Different: Gravity level (microgravity, microgravity, mixed - SAFFIRE-II includes 1-g reference burns), Hardware (CIR, MDCA / MSG, SPICE flow duct / none), Fuel phase (liquid / gas / solid), oxygen range (12 % – 34 % / n/a / 21.5 % – 22.1 %), flow range (n/a / 5.4 – 65 cm/s / 20 – 30 cm/s). Every row carries an icon and a word, never colour alone. Attribute order is fixed by doc 05 section 6; the matrix is deterministic. The URL becomes /compare?ids=FLEX,SPICE,SAFFIRE-II; ids are matched case-insensitively and replaced by the exact acronyms. If the visitor picked investigations in Explorer first, Compare opens with that selection.

## Slide 11 - The narrative is cited and verified; lineage shows shared hardware.

On the slide: the end of the narrative with citation links, and the hardware lineage graph.

### Speaker notes
Step 4 continued (inside 1:00 to 1:20). Scroll to "Narrative" and "Hardware lineage". On the live model the narrative had six verified sentences, for example "FLEX covered oxygen fractions from 0.12 to 0.34 and pressures from 70.168 to 309.295 kPa, while SAFFIRE-II covered only 0.215 to 0.221 oxygen fraction." - cited to the PSI-69 and PSI-99 experimental tables with the column and rows - and "For fire safety, FLEX maps flammability limits and suppression of liquid fuels, SPICE quantifies sooting propensity of gaseous fuels, and SAFFIRE-II compares low-gravity flammability limits of solid materials with normal-gravity screening." The citation verifier removed anything unsupported. Timing: a first, uncached narrative took 2.8 s on deepseek-v4-pro:cloud (measured on another set); repeats come from the response cache. Lineage (FR-12, GET /hardware): FLEX - apparatus MDCA - hosted in CIR; SPICE - apparatus SPICE flow duct - hosted in MSG; SAFFIRE-II lists no PSI hardware. If the LLM fails, the panel says "The language model is unavailable, so no written summary was generated. The matrix above is unaffected."

## Slide 12 - Scenario Lab measures coverage and bounds gravity instead of guessing.

On the slide: Scenario Lab at the lunar preset with callouts on the preset, the assumed-default chip, a Covered chip, the gravity No data chip, the 1 g upper bound.

### Speaker notes
Step 5, 1:20 to 1:45 (25 s, shared with slides 13 and 14). Click: sidebar "Scenario Lab"; PRESET select: "Lunar habitat (assumed default)". The form fills OXYGEN 34, PRESSURE 56.5 kPa (8.2 psi with the psi toggle), FLOW SPEED 10, GRAVITY 0.166. Say: "She types her habitat; oxygen, pressure and flow are inside tested ground, partial gravity is not, and FlameScope says so." Catalog coverage: Oxygen Covered (catalog 12 % to 85 %), Pressure Covered (25.3 to 506.6 kPa), Flow speed Covered (0 to 85.3 cm/s), Gravity No data ("Catalog values: 0 g, 1 g"). The gravity-bounding card: "The scenario gravity is 0.166 g. PSI holds no partial-gravity combustion data yet. Microgravity (0 g) and normal-gravity (1 g) results bound the behaviour at this gravity. LUCI and FM2 are expected to add partial-gravity data." Lower bound 0 g: BASS-II, BRE, CFI, CFI-G, FLEX, FLEX-2, Flame-Design, SAFFIRE-I, SAFFIRE-II, s-Flame. Upper bound 1 g: SAFFIRE-II, from its 1-g reference burns. Analogue: E-FIELD-Flames.

## Slide 13 - Seven investigations hold 840 runs close to her habitat.

On the slide: the match list with callouts on the export buttons, the first match, its best-run similarity, the per-dimension bars, the best run.

### Speaker notes
Step 5 continued (inside 1:20 to 1:45). Scroll to "Closest matching investigations". Say: "Seven investigations have runs at 60 percent similarity or better: 840 runs she can model from." The list: FLEX-2 96.3 % best-run similarity (8 runs at 60 % or better), BASS-II 88.6 % (4), CFI-G 79.5 % (217), FLEX 79 % (266), Flame-Design 78.8 % (260), s-Flame 74.3 % (23), CFI 71.3 % (62); SAFFIRE-II, SAFFIRE-I and BRE follow with no run at 60 %. Each card shows oxygen, pressure, flow and fuel similarity and the best run with its source label, for example FLEX test 37: 34 % O2, 71.2 kPa, 0 g. Gravity never enters the distance (ADR-08). Similarity measures closeness of test conditions, not safety - the disclaimer says so above the form.

## Slide 14 - Explain cites exact test rows; the export carries the same runs.

On the slide: the Interpretation panel after Explain with callouts on a cited sentence, its citation, the gravity caveat, the CSV export button.

### Speaker notes
Step 5 continued (ends at 1:45). Click "Explain", then "Export matching runs (CSV)". Say: "The written reading cites the exact test rows; anything uncovered, like gravity, gets a fixed caveat." On the live model: "FLEX has an oxygen fraction of 0.34 and pressure of 71.234 kPa, matching the scenario oxygen fraction exactly." (cited to the PSI-69 experimental table, row 37) and "Flame-Design has an oxygen fraction of 0.327365 and pressure of 51.228 kPa, close to the scenario values." (PSI-10 table, row 83), then the deterministic caveat "Gravity (g) 0.166 has no catalog data (no_data)." and the gravity statement. Live output varies between runs; the first Explain took 3.4 s, a repeat 0.2 s from the cache. If the panel shows "No written summary was generated for this selection." or the unavailable notice, the verifier or the model left nothing to show; coverage, bounds and matches are deterministic and unaffected. The CSV has the commented header with the scenario_id filter and rubric 2026.11-1, then the 840 matching runs; the scenario_id is stateless URL-safe base64 of the resolved scenario, decoded again by /extract/export.

## Slide 15 - Data Extract builds model-ready tables with provenance columns.

On the slide: Data Extract with callouts on the export buttons, query filters, column picker, Data dictionary, the preview.

### Speaker notes
Step 6, 1:45 to 2:00 (15 s). Click: sidebar "Data Extract"; then "Export CSV". Say: "A model-ready table: conditions, outcomes and provenance on every row, with the filters in the file header." With no filter the export holds all 2,003 runs. The query offers fuel phase, O2 and pressure ranges, recorded outcomes (ignited, flame spread rate, burn rate, extinction, smoke point, cool flame) and investigations; the column picker offers the 19 default columns. The preview shows the first rows, starting with BASS, each with its source locator, for example "Experimental table PSI-26_Experimental table_BASS.csv, row 1". Downloaded file name: flamescope-extract-20261115T011705Z.csv (pattern flamescope-extract-<timestamp>.csv). Endpoints: GET /extract/dictionary, POST /extract/preview, POST /extract/export (CF-08), no LLM.

## Slide 16 - Every column is defined; every export records filters and rubric.

On the slide: the Data dictionary drawer and the real CSV header exported from the live stack.

### Speaker notes
Step 6 continued, optional (inside 1:45 to 2:00). Click: "Data dictionary". Each column has a name, label, unit and description, for example o2_fraction in fraction ("Oxygen mole fraction, 0 to 1."), pressure_kpa in kPa ("Total pressure."), flow_speed_cm_s in cm/s, gravity_g in g ("0 for microgravity, 1 for normal gravity."). The export header is exactly what the stack wrote: exported_at, filters, rubric_version 2026.11-1, then the 19 columns ending with confidence, source_uri and source_locator - the provenance columns - and 2,003 data rows. Esc closes the drawer.

## Slide 17 - Safety Tech maps forty sourced findings to equipment decisions.

On the slide: the Detection and Suppression groups with findings, confidences and sources.

### Speaker notes
Step 7, 2:00 to 2:10 (10 s). Click: sidebar "Safety Tech". Say: "Forty sourced findings, grouped by the equipment decision they inform; detection alone has nine." Groups: Detection 9 findings from 6 investigations (BASS, BASS-II, DAFT, DAFT-2, SAME, SAME-R), Suppression 2 from 2, Material screening 4 from 3, Post-fire hazards 1 from 1, Atmosphere design 4 from 3, Fundamental combustion 20 from 10. Read the first: "A tiny flame might go undetected for a long time and could flare up if the air flow increases, which matters for spacecraft fire detection." - BASS, confidence 75 %, citing Ferkul et al., 2013. Below the groups, the gaps panel repeats the two gaps from the Overview (CF-10).

## Slide 18 - Ask streams a cited answer and removes unsupported sentences.

On the slide: the prepared question, its cited answer, the related chip, the selected source.

### Speaker notes
Step 8, 2:10 to 2:35 (25 s). Click: sidebar "Ask"; type exactly "What is known about smoke detection in microgravity?" in the Question box; click "Ask"; when the input is enabled again click citation chip "1". Say: "The answer streams, then every sentence without a supporting source is removed; the chips open the sources." On the live stack the answer had five sentences, each with a chip, none removed, for example "SAME reports that when it was planned, all spacecraft smoke detectors had been designed from normal-gravity smoke data because microgravity smoke data were absent." and the SAME-R finding that most average smoke particle sizes were in the 200 nm to 400 nm range. Related: SAME. The selected citation is the SAME abstract (Urban et al., 2007, NTRS). The full answer took 1.4 to 1.7 s in the browser and 1.3 s through the API. The live wording varies between runs. Backup questions, both verified with cited answers: "What did SAFFIRE-II measure?" (two sentences: nine 5 cm x 29 cm samples burned in the Cygnus module, and the pressure, CO2 and O2 sensors). The Sources panel shows "relevance 0" because it rounds the fused scores, which are about 0.03. An off-corpus question such as "What is the capital of France?" gets the fixed sentence "The curated PSI corpus does not contain enough information to answer that."

## Slide 19 - Earth Apps lists curated terrestrial spin-offs by sector.

On the slide: sector filter and the Smoke detection card.

### Speaker notes
Step 9, 2:35 to 2:45 (10 s). Click: sidebar "Earth Apps"; then the sector button "Detection" (one card remains). Say: "The challenge's Earth spin-offs, curated by people; harvest-mode AI only proposes candidates for review." The card: Smoke detection, linked to PSI-115, SAME and SAME-R; "PSI states that smoke detectors developed from the SAME results can also be useful in other extreme environments on Earth", citing the challenge statement (doc 01 section 1, O4) and the PSI-101 and PSI-115 records. All sectors: Smoke detection (Detection), Fine water mist extinguishers and Firefighter gear (Firefighting), Electric-field control of flames to reduce pollutant emissions (Industrial, E-FIELD-Flames). Rows come only from src/data/seed/earth_applications.yaml; EarthAppsAgent candidates go to earth_candidates.json for a curator, never into the database.

## Slide 20 - The Architecture page renders the design with live status.

On the slide: Components tab with the Domain services node selected and its NodePanel.

### Speaker notes
Step 10, 2:45 to 3:00 (15 s, shared with slide 21). Click: sidebar "Architecture"; tab "Components"; click the "Domain services" node; in the panel click "CF-05". Say: "The design documents are inside the product, with live status from the running stack." The panel shows C-SVC, kind service, a green "up" badge from GET /meta/status (polled every 10 s), the responsibility, the interfaces (RankingService.rank(lens, weights, preset, filters) and the other services), the source files and related flows. The minimap is dark and the canvas fits with padding. Close on: "That is the whole product: ranked, cited, honest about gaps, and the architecture is part of it."

## Slide 21 - All thirteen call flows are browsable, with LLM usage marked.

On the slide: Call flows tab with CF-05 Ranking selected.

### Speaker notes
Step 10 continued (ends at 3:00). Clicking "CF-05" switches to the Call flows tab: the list shows CF-01 to CF-13 with chips "LLM: none", "LLM: optional" or "LLM: yes"; the right pane renders the Mermaid sequence from doc 09 and the failure behaviour ("The UI debounces slider changes (250 ms) and keeps previous data while refetching. Ranking is deterministic for identical input and makes no LLM call."). The seven tabs are System context, Layers, Components, Data flow, Data model, Call flows and Deployment; "Download draw.io" returns the diagram file. The diagram content is static JSON mirroring docs 03 and 09 (the static Ollama node names the documented default qwen2.5:0.5b; the live model is in the top bar). End of the live path; the remaining slides are the backend and data deep dive.

## Slide 22 - FlameScope only reads PSI; request-time AI stays on the Mac.

On the slide: system context diagram of doc 02 section 1.

### Speaker notes
Backend section starts. Four user groups use one system. FlameScope reads from three public sources - the PSI website (links and repository records), the public s3://nasa-psi bucket in us-west-2 (harvest of metadata and documents) and DOI resolvers (abstracts and citations) - and never writes to them. The dashed violet edge is the only request-time call leaving the containers: to Ollama on the Mac host, for Ask, the compare narrative and the scenario explanation. In mock mode there are no such calls. On this stack Ollama routes the configured model deepseek-v4-pro:cloud; the documented default is qwen2.5:0.5b.

## Slide 23 - Four containers; the browser only ever talks to the UI origin.

On the slide: compose topology with ports, volumes, Ollama and the bucket.

### Speaker notes
The browser talks only to ui on port 3000. Next.js rewrites /api/* to api:8000 (API_INTERNAL_URL, fixed at build time), so there is one origin and no CORS in the browser path. api reads db (PostgreSQL 16 with pgvector) and mounts flamescope_raw read-only; ingest is a one-shot job that runs migrate then seed and writes the raw volume. api and ingest reach Ollama on the host through host.docker.internal (extra_hosts host-gateway), so Docker Desktop and Colima both work. Ollama is not a compose service. db publishes 5432 on localhost only.

## Slide 24 - Routers validate, services decide, repositories alone touch SQL.

On the slide: the layer stack, the orchestrator side path, the error envelope table, request IDs and an end-to-end example.

### Speaker notes
Layer rules of doc 02 section 2, enforced by test_import_rules: routers never import repositories or agents; services never import routers; services are deterministic and call the orchestrator only for the compare narrative, scenario explanation and ask. Domain errors derive from FlameScopeError and map to one envelope with code, message, details and request_id: 400 bad_request, 404 not_found, 422 validation_error from FastAPI request validation, 502 llm_unavailable, 500 internal_error. Compare and Scenario still answer 200 with the narrative or explanation marked unavailable when the model fails. Every response carries X-Request-ID.

## Slide 25 - Twenty-four endpoints; only three can call a language model.

On the slide: the 24 endpoints of doc 05 section 11 in six groups.

### Speaker notes
Catalog 8, health and meta 6, insights and Earth 3, extract 3, rank-compare-scenario 3, ask 1: 24. POST /compare calls the comparator only with narrative true; POST /scenario calls the interpreter only with explain true and at least one match; POST /ask always uses the model unless retrieval finds nothing above threshold. IDs in paths are acronyms, case-insensitive. Lists paginate with page and page_size (default 24, max 100); POST /extract/preview takes a limit up to 5000 so the Overview scatter gets every run in one call. test_18_api_contract asserts the OpenAPI document lists exactly these 24 - nothing extra. Measured p95 over 30 sequential calls in the last integration run: GET /insights/gaps 152.5 ms, GET /investigations/{id} 67.9 ms, every other measured endpoint under 15 ms.

## Slide 26 - Seventeen tables hold cards, runs, scores, chunks and an audit trail.

On the slide: catalog tables, scoring, search, Earth and operations groups.

### Speaker notes
Ten catalog tables, three Earth tables, relevance_score, chunk, ingest_run and llm_cache: 17. investigation.card stores the full InvestigationCard as JSON; derived columns such as o2_min and o2_max are recomputed after runs are loaded, and a null endpoint stays null (open). test_run plus condition hold one row per run - 2,003 on this stack; gravity_g 0 means microgravity, 1 normal gravity. relevance_score holds 375 ratings (25 investigations x 15 criteria), chunk 215 rows. chunk.embedding has EMBED_DIM 768; changing it needs a new migration. Every fact carries a SourceRef with kind and uri required.

## Slide 27 - Ingestion runs offline in nine stages; seed mode enters at normalize.

On the slide: the nine stages, seed and override entry points, the two modes.

### Speaker notes
Harvest mode runs discover, harvest, parse, extract, normalize, link, score, index, review. The two violet stages call agents (ExtractorAgent, ScorerAgent); review also calls EarthAppsAgent in harvest mode. Seed mode (make deploy) starts at normalize from src/data/seed/**, needs no network, and calls the scorer only when a seed file has no scores - which is the case for all 25 files today, so the scorer rated them at seed time. Overrides are deep-merged after extract and again after normalize, so they always win. LLM extraction and scoring happen offline (ADR-02): the UI stays fast and reproducible, and the results can be reviewed.

## Slide 28 - Every stage is idempotent, and curator overrides always win.

On the slide: idempotency keys per stage, overrides, download limits, failure handling.

### Speaker notes
Each stage is skipped while its key is unchanged; --force reruns it. After changing EMBED_MODEL run index --force to re-embed; chunk ids stay stable so score evidence keeps valid chunk_id references. Download rules protect the 12 TB: HTML and text up to 5 MB, documents up to HARVEST_MAX_DOC_MB 25, tables up to 5 MB and 20 per investigation, 300 MB total per investigation; video, images, archives and binaries are listed in the manifest only (NFR-10). S3 and network errors retry three times with backoff. The quote of every extracted field must be a substring of its source text, or the field is nulled and reported.

## Slide 29 - Six Google ADK agents, each with one prompt file and one schema.

On the slide: the six agents with prompt versions, callers and outputs; the orchestrator steps.

### Speaker notes
One agent, one job, one runtime prompt file in src/agents/flamescope_agents/prompts/, one input and one output schema. Prompt files have YAML front matter (name, version, output_schema, temperature, max_tokens) and ## System and ## User sections, and include shared grounding rules and a domain primer; no prompt text lives in Python. Agents have no tools and no database access; every output is Pydantic-validated, and versions are stored with results. Three agents run at request time (comparator, scenario interpreter, insight QA); three at ingestion (extractor, scorer, Earth apps).

## Slide 30 - One gateway hides the provider: mock for tests, Ollama live.

On the slide: agents to gateway to the mock and ollama providers; gateway features; request-time budget.

### Speaker notes
Only flamescope_common/llm/providers/ imports LiteLLM or calls Ollama. The mock provider is an ADK BaseLlm that finds the agent input in the rendered prompt and synthesizes schema-valid output deterministically; its embeddings hash content words into a 768-length unit vector. The ollama provider uses LiteLlm with ollama_chat/<LLM_MODEL> and POST /api/embed with nomic-embed-text, and sends think false on chat calls so a reasoning model does not spend max_tokens on hidden reasoning. Only valid replies are cached, so a schema retry always reaches the model. This stack runs LLM_MODEL=deepseek-v4-pro:cloud with LLM_TIMEOUT_S=120 (from .env); the defaults are qwen2.5:0.5b and 60 s. The cache keys are SHA-256 of provider, model, prompt and parameters.

## Slide 31 - The citation verifier deletes sentences their sources do not support.

On the slide: the four verification steps, the live examples, the fixed sentence, scenario caveats.

### Speaker notes
CitationVerifier is deterministic Python in flamescope_agents. Insight QA drafts cite with [c:123] for chunks and [f:45] for card facts; the comparator and scenario interpreter return sentences with fact_ids. Cited texts are pooled for the number and overlap checks, and markers are stripped from kept sentences. Live examples from this stack: the prepared smoke-detection question kept all five sentences; "Which experiments tested solids above 30% oxygen?" kept two and dropped two (the answer is about BRE, which emulated burning solids with gaseous fuels, so it is not used in the demo). With a weak model this fails safe: fewer sentences, never invented facts.

## Slide 32 - Three lenses, fifteen criteria and five presets, all in YAML.

On the slide: rubric.yaml lenses and criteria with weights; presets.yaml ranking presets.

### Speaker notes
Rubric version 2026.11-1 in src/data/rubric.yaml: three lenses (habitat for O1, modeling for O2, controls for O3), five criteria each, weights summing to 1 within a lens, and lens weights 0.4, 0.3, 0.3. Each criterion has 0, 3 and 5 anchors and is rated 0 to 5 by the scorer agent, a seed file or an override, or null when there is no evidence. Changing any ID, label, weight, anchor or lens weight requires a new rubric version and a re-run of the score stage. Presets live in src/data/presets.yaml; explicit weights override a preset, which overrides the rubric defaults.

## Slide 33 - Scores are auditable arithmetic: 72.9 in the worked example.

On the slide: the formulas of doc 08 section 2, the worked example of section 6, the live FLEX check.

### Speaker notes
Null criteria leave both the numerator and denominator, so missing evidence lowers confidence instead of dragging the score to zero. Worked example: weights 0.25, 0.25, 0.20, 0.15 have evidence (0.85); weighted sum 3.10; 20 × 3.10 / 0.85 = 72.94, shown as 72.9 with confidence 0.85 - asserted by test_ranking_aggregate. The live number on slide 5 checks out the same way: under lunar_habitat FLEX has all five habitat ratings (fuel realism 3 at 0.25, atmosphere match 5 at 0.35, flow regime 3 at 0.05, phenomenon 5 at 0.15, gravity bounding 3 at 0.20); weighted sum 4.0, 20 × 4.0 / 1.0 = 80, confidence 1.0. Scores are rounded to one decimal only in responses, and the ranking orders on the rounded score and confidence, then the acronym case-insensitively.

## Slide 34 - Scenario similarity is a weighted distance: 0.696 in the example.

On the slide: the distance formulas, the doc 08 section 6 scenario example, coverage and matching rules.

### Speaker notes
Each numeric dimension is normalized by the catalog range and capped at 1; a run without a value is the worst case. Fuel: 0 for the same material, 0.3 same material class, 0.6 same phase only, 1 otherwise; unset when the scenario names no fuel, as in the lunar preset. Worked example (ranges o2 0.10-0.85, pressure 50-101.3, flow 0-60; scenario 0.34, 56.5, 10, PMMA; run 0.21, 101.3, 20, PMMA): distance 0.0607 + 0.2183 + 0.0250 + 0 = 0.3040, similarity 0.696 - asserted by test_scenario_distance within 0.001. On the live stack the lunar preset finds 840 runs at 0.6 or more in seven investigations. Gravity bounding: no bounds or statement within 0.02 g of 0 or 1; otherwise lower bound from 0 g runs, upper bound from 1 g runs, analogue from the partial_gravity_analogue tag, and the statement template from presets.yaml.

## Slide 35 - Ask fuses keyword and vector hits, then streams verified sentences.

On the slide: the retrieval pipeline, the SSE event order, thresholds and fusion.

### Speaker notes
InsightService embeds the question through the gateway, runs keyword search (PostgreSQL tsvector) and vector search (pgvector cosine) in parallel, fuses the two rankings by reciprocal rank fusion with k = 60 and keeps the best top_k (default 8), then adds card facts. The SSE stream sends meta first (the retrieved sources, so the UI can show them even if the model fails), then tokens, then the verified final answer in citations - the UI replaces the streamed draft with it - then related and done, or a terminal error event. The ollama threshold was recalibrated from 0.5 to 0.55 on the 215-chunk, 25-investigation catalog (doc 05 section 10): the best chunk for ten corpus questions scored 0.694 to 0.838, for eight off-corpus questions 0.413 to 0.490. A different EMBED_MODEL needs a new calibration. For the prepared question the meta event's top fused score was 0.0325.

## Slide 36 - Gaps are computed, not hidden: partial gravity and 116 untested cells.

On the slide: the partial-gravity statement and the oxygen-pressure gap grid with tested cells and the lunar envelope.

### Speaker notes
The grid has oxygen bins of 0.05 from 0.10 to 1.00 (18 columns) and pressure bins of 10 kPa from 20 to 110 (9 rows): 162 cells. A run covers a cell when its oxygen and pressure spans both overlap the cell; on this stack the runs cover 46 cells (blue), mostly 0.15 to 0.35 oxygen near one atmosphere, plus gas-jet runs at reduced pressure and 0.30 to 0.85 oxygen. The 116 untested cells form one 4-connected region, which intersects the lunar-habitat envelope (oxygen at or above 0.30, pressure at or below 70.3 kPa; orange) - so GET /insights/gaps lists one param_gap_1 of 116 cells. The cell pattern is the live computation of services/safety_tech.py, copied into the deck. The partial_gravity gap disappears only when a run has a gravity strictly between 0 g and 1 g (more than 0.02 g from either); today 1,989 runs are at 0 g and 11 at 1 g.

## Slide 37 - One dark token set keeps every view legible and consistent.

On the slide: the colour tokens of doc 10 section 2.1 and the binding quality rules.

### Speaker notes
Tokens are CSS variables in src/ui/app/globals.css mapped in tailwind.config.ts; components never hard-code colours. --text-faint is #8391A7 so captions reach 4.5:1 on every surface. Every panel implements loading, empty, error-with-retry and data states. Scrollable tables are keyboard-focusable. The score disclaimer appears in Ranking, Scenario and the footer. Layout: 240 px sidebar, top bar with search, LLM badge, dataset badge and PSI link; responsive from 1280 px, usable at 1024 px. This deck reuses the same tokens.

## Slide 38 - One Makefile builds, deploys, tests and tears down the stack.

On the slide: the 26 Makefile targets by group, the deploy sequence, timings, switching to mock.

### Speaker notes
make deploy follows CF-01; any failing step stops with a make logs hint. make status shows compose ps plus /ready and /meta/stats; make undeploy runs compose down -v --remove-orphans and removes volumes (data reset is undeploy then deploy). Timings: live deploy about 2 to 3 minutes including scoring and mock deploy about 25 seconds are the last values measured on this Mac; this stack was not redeployed for the deck. Its last seed ingest_run took 6.4 s (01:09:46 to 01:09:53 UTC). Do not run make test or make deploy on the demo stack: the test targets deploy in mock mode and the undeploy check removes the data. An optional Helm chart deploys the same images to Kubernetes or OpenShift.

## Slide 39 - 1,716 tests pass across unit, Vitest, integration and end to end.

On the slide: the test pyramid with real counts.

### Speaker notes
From the last clean make test (exit 0, 2026-11-14): unit tests/reports/unit.xml lists 1137 tests with 1 skipped (the README xfail) and 0 failures, so 1136 passed; Vitest 225 tests in 24 files passed (re-run for the deck); integration 247 passed (tests/reports/integration.xml) - build, deploy, database, ingestion idempotency, every one of the 24 endpoints, the OpenAPI inventory, p95 latency under 300 ms (slowest GET /insights/gaps at 152.5 ms); end to end 108 passed (tests/reports/e2e.xml) - every route at 1440x900 plus a 1024x768 pass, axe-core contrast and the undeploy check. 1136 + 225 + 247 + 108 = 1716. Integration and end-to-end ran in mock mode, as doc 12 requires; the optional live check test_21_llm_ollama reached the live model.

## Slide 40 - The catalog holds real PSI data: 25 investigations, 2,003 runs.

On the slide: live /meta/stats tiles, what is in the catalog, what is still open.

### Speaker notes
Live GET /api/v1/meta/stats: investigations 25, test_runs 2003, publications 355, findings 40, chunks 215, hardware 6, fuel phases gas 9, liquid 6, solid 8, o2_range [0.12, 0.85], pressure_range_kpa [25.331, 506.625], rubric 2026.11-1, ingest_mode seed. From the database: 1,989 runs at 0 g, 11 at 1 g (nine SAFFIRE-II 1-g reference burns and two PSI-142 runs), 3 without a stated gravity; 25 runs are aggregate ranges, the rest individual tests. Say plainly what is still open: every card is reviewed false, curated from cited sources but not yet signed off by a person (OI-06); the 375 criterion ratings were produced by the scorer at seed time. There is still no partial-gravity run, and 116 of 162 oxygen-pressure cells are untested. Canadian Space Agency sources were checked and hold no usable combustion data, so no CSA data is claimed.

## Slide 41 - The data comes from PSI records, experimental tables and NASA reports.

On the slide: the source flow (PSI repository records, PSI experimental tables, NTRS and NASA pages to the seed files to seed ingestion) and the coverage, run and gravity rules.

### Speaker notes
Coverage: the 25 seed files cover all 24 PSI Combustion Science records (doc 01 OI-06). PSI-47 holds DAFT and DAFT-2 and is seeded as two files; the 20 flight investigations are the 14 named in the challenge plus CLD Flame, s-Flame, Flame Design and SAFFIRE-I to -III; the 5 ground investigations that re-analyse or model flight data are keyed by their PSI accession: PSI-60, PSI-62, PSI-115, PSI-117, PSI-142. Text fields cite the PSI repository record read through PSI's geode-py JSON API (locators such as "objective (PSI repository record, geode-py API)"). Runs: one per row or stated test point of the PSI experimental tables (files named PSI-<n>_Experimental table_*.csv) for 16 flight investigations, aggregate ranges where a source states only a range, none where no source states conditions; the largest are SPICE 435, CFI-G 333, Flame-Design 327, FLEX 274. Ground studies list no tests; PSI-62, PSI-115 and PSI-142 carry five aggregate runs from their records, and DAFT-2, PSI-60 and PSI-117 have none. Gravity: 0 g where PSI labels the project a Microgravity Investigation; 1 g only where a source states a normal-gravity test, such as the SAFFIRE-II table's "1-g Burn Length" columns - which is why the Scenario Lab now has a 1 g bound. Allowed sources are PSI pages, s3://nasa-psi keys, DOIs and NASA hosts (NTRS records as publications); unknown values stay null.

## Slide 42 - Next: human review, a stronger harvest model, partial gravity.

On the slide: four next steps.

### Speaker notes
First, human review: curators sign off each card and its ratings (reviewed true); overrides in src/data/overrides/ already win over any computed value. Second, run harvest mode against the nasa-psi bucket with a stronger model than the 0.5B default, review, then export-seed (OI-04). Third, partial gravity: LUCI and FM2 are expected to add data; when a run sits between 0 g and 1 g the gap closes by rule. Fourth, other PSI disciplines - discipline is already a column.

## Slide 43 - Questions

On the slide: the repository link and the companion note.

### Speaker notes
Leave this slide up for questions. The code is at https://github.com/AyaanAsish/flamescope. Likely questions and answers: "Is the score a safety rating?" - no, a relative decision aid; the disclaimer is on every scoring view. "What if the model invents something?" - the citation verifier removes unsupported sentences; with no support you get the fixed sentence. "Where do the numbers come from?" - PSI repository records and experimental tables, every run with its table and row (slide 41). "Does it work offline?" - yes, mock mode with seed data, which is how all tests run.
