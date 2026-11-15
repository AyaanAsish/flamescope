# FlameScope - live demo script

Presenter script for the 3-minute live path. It goes with the detailed companion deck `flamescope-demo.pptx` (slides 4 to 21 are the fallback captures of each step). This is not the Space Apps submission; that is the separate 7-slide pitch deck.

Verified on 2026-11-14: every click below was executed with Playwright (Chromium, 1440x900) against the live stack, using the visible labels only: `LLM_PROVIDER=ollama`, model `deepseek-v4-pro:cloud`, seed data with 25 investigations and 2,003 test runs. Labels and numbers are the ones the UI showed.

## Timed path (180 s)

| Step | Time (cumulative) | Route | Clicks | Words to say |
|------|-------------------|-------|--------|--------------|
| 1 | 0:00-0:20 (20 s) | `/` | Open http://localhost:3000. Point at the top-bar badge "ollama · deepseek-v4-pro:cloud", the stat tiles and the coverage scatter, then scroll to "Evidence gaps". | "This is every PSI combustion investigation, 2,003 test runs on one map, and the shaded box is her lunar habitat." |
| 2 | 0:20-0:45 (25 s) | `/ranking` | Sidebar "Ranking". PRESET select: "Lunar habitat". Tab "Habitat". Click "Evidence" on row 1 (FLEX, 80). Press Esc. | "Her priorities re-rank all 25 investigations instantly: pure arithmetic over stored, cited ratings, no AI at query time. Every rating shows its rationale and source." |
| 3 | 0:45-1:00 (15 s) | `/investigations/FLEX` | Click the "FLEX" name in row 1. Tab "Test runs". Scroll down; click "Next". | "One card per investigation, every fact linked to its PSI source - and all 274 FLEX tests, one row of the PSI experimental table each." |
| 4 | 1:00-1:20 (20 s) | `/compare?ids=FLEX,SPICE,SAFFIRE-II` | Sidebar "Compare". ADD INVESTIGATION: "FLEX - Flame Extinguishment Experiment", "SPICE - Smoke Point In Co-flow Experiment", "SAFFIRE-II - Spacecraft Fire Experiment-II". Scroll to "Narrative" and "Hardware lineage". | "A droplet study, a gas-jet study and a solid-materials study side by side. Each narrative sentence is checked against its source." |
| 5 | 1:20-1:45 (25 s) | `/scenario?preset=lunar_habitat` | Sidebar "Scenario Lab". PRESET: "Lunar habitat (assumed default)". Point at "Catalog coverage" and "Gravity bounding". Scroll to "Closest matching investigations". Click "Explain". Click "Export matching runs (CSV)". | "Oxygen, pressure and flow are inside tested ground, partial gravity is not, and FlameScope says so. Seven investigations have 840 runs close to her habitat." |
| 6 | 1:45-2:00 (15 s) | `/extract` | Sidebar "Data Extract". Click "Export CSV". Optional: "Data dictionary", Esc. | "A model-ready table: conditions, outcomes and provenance on every row, with the filters in the file header." |
| 7 | 2:00-2:10 (10 s) | `/safety-tech` | Sidebar "Safety Tech". | "Forty sourced findings, grouped by the equipment decision they inform; detection alone has nine." |
| 8 | 2:10-2:35 (25 s) | `/ask` | Sidebar "Ask". Type the prepared question (below) in the Question box. Click "Ask". When the box is enabled again, click citation chip "1". | "The answer streams, then every sentence without a supporting source is removed; the chips open the sources." |
| 9 | 2:35-2:45 (10 s) | `/earth?sector=detection` | Sidebar "Earth Apps". Click sector "Detection". | "The challenge's Earth spin-offs, curated by people; harvest-mode AI only proposes candidates for review." |
| 10 | 2:45-3:00 (15 s) | `/architecture?tab=flows&cf=CF-05` | Sidebar "Architecture". Tab "Components". Click node "Domain services". In the panel click "CF-05". | "The design documents are inside the product, with live status from the running stack." |

What each step shows on screen (seen in the verification run):

1. Tiles: 25 investigations ("9 gas, 6 liquid, 8 solid"), 2,003 test runs, 355 publications, 40 findings, 215 indexed chunks, 6 hardware. "Catalog covers oxygen 12 % – 85 % and pressure 25.3 kPa – 506.6 kPa." Scatter of the runs by oxygen and pressure, coloured by fuel phase, with the shaded "Lunar habitat envelope". Top 5 overall: PSI-115 84 (45 %), FLEX 80.7, BASS 75.1, BASS-II 74.8, SAME-R 74.7. Gaps: "No partial-gravity data" (Related: E-FIELD-Flames, Expected: LUCI, FM2) and "Untested oxygen and pressure region" (116 grid cells).
2. Lunar habitat preset, Habitat tab: lens shares Habitat 60 %, Modeling 20 %, Controls 20 %; FLEX 80, BASS 78.5, SAME-R 78.5, FLEX-2 74, BASS-II 73. Drawer "FLEX evidence": fuel realism 3 / 5, atmosphere match 5 / 5 ("weight 35 %, contributes 35 points"), flow regime 3 / 5, phenomenon relevance 5 / 5, gravity bounding value 3 / 5, each with links to card fields and the "llm" origin chip.
3. Badges Liquid, ISS, Microgravity, Unreviewed, 274 test runs; conditions 12 % – 34 % oxygen, 70.2 – 309.3 kPa; sources "PSI investigation PSI-69, Flame Extinguishment Experiment (... geode-py API)". Test runs: "274 total, page 1 of 3", then "page 2 of 3"; "Showing 100 of 274 runs. Missing values are unknown, not zero."; each row links to "PSI-69 Experimental table".
4. Same: Project, Platform (ISS). Different: Gravity level, Hardware, Fuel phase, Fuel materials, oxygen and flow ranges. Six cited narrative sentences, for example "FLEX covered oxygen fractions from 0.12 to 0.34 and pressures from 70.168 to 309.295 kPa, while SAFFIRE-II covered only 0.215 to 0.221 oxygen fraction."; lineage FLEX - MDCA - CIR, SPICE - SPICE flow duct - MSG, SAFFIRE-II without hardware.
5. Form 34 %, 56.5 kPa, 10 cm/s, 0.166 g with the "assumed default" chip; coverage Covered for oxygen, pressure and flow, No data for gravity ("Catalog values: 0 g, 1 g"); lower bound 0 g (10 investigations), upper bound 1 g SAFFIRE-II, analogue E-FIELD-Flames. Matches: FLEX-2 96.3 % (8 runs at 60 % or better), BASS-II 88.6 %, CFI-G 79.5 %, FLEX 79 %, Flame-Design 78.8 %, s-Flame 74.3 %, CFI 71.3 %. Explain (live wording varies): "FLEX has an oxygen fraction of 0.34 and pressure of 71.234 kPa, matching the scenario oxygen fraction exactly." cited to the PSI-69 table row 37, plus "Gravity (g) 0.166 has no catalog data (no_data)." CSV: header with the `scenario_id` filter, 840 rows.
6. Preview rows from BASS with source locators; download `flamescope-extract-<timestamp>.csv` with `# exported_at`, `# filters: {}`, `# rubric_version: 2026.11-1`, the 19 default columns and 2,003 rows.
7. Detection 9 findings from 6 investigations, Suppression 2, Material screening 4, Post-fire hazards 1, Atmosphere design 4, Fundamental combustion 20; each finding with confidence and publication.
8. See the prepared answer below; the Sources panel highlights the selected citation.
9. Detection leaves one card: Smoke detection, linked to PSI-115, SAME, SAME-R (four applications under All sectors).
10. NodePanel "Domain services", C-SVC, service, "up"; Call flows tab shows "CF-05 Ranking" and its failure behaviour.

## Prepared inputs

- **Investigation to open**: FLEX (top of the lunar_habitat ranking on the Habitat lens with 80, confidence 100 %; 274 runs, 3 pages).
- **Investigations to compare**: FLEX (liquid droplets; CIR and MDCA), SPICE (gas jets; MSG and the SPICE flow duct), SAFFIRE-II (solid materials; flight and 1-g reference burns). In the ADD INVESTIGATION select the options read "FLEX - Flame Extinguishment Experiment", "SPICE - Smoke Point In Co-flow Experiment", "SAFFIRE-II - Spacecraft Fire Experiment-II". Verified narrative: six sentences, all cited.
- **Scenario values**: preset `lunar_habitat`: oxygen 34 %, pressure 56.5 kPa (8.2 psi), flow 10 cm/s, gravity 0.166 g, no fuel. Labelled "assumed default": a design assumption inside the challenge envelope (30 % oxygen or more, 10.2 psi or less). Verified: 7 investigations, 840 runs at 60 % similarity or better.
- **Ask question** (type exactly): `What is known about smoke detection in microgravity?`
  Verified answer in the browser: five sentences, each with chip "1", none removed, for example "SAME reports that when it was planned, all spacecraft smoke detectors had been designed from normal-gravity smoke data because microgravity smoke data were absent." Related: SAME. Three more runs through the API returned four or five sentences, all cited, none dropped. The wording varies between runs.
  Backup question, verified with a cited answer: `What did SAFFIRE-II measure?` (two sentences, none dropped, related SAFFIRE-II). Avoid "Which experiments tested solids above 30% oxygen?": it returned a cited answer about BRE (gaseous fuels emulating solids) with two sentences dropped.
- **Data Extract**: no filters; "Export CSV" writes all 2,003 rows.

## Measured timings (Playwright, 2026-11-14, live stack)

Machine response per step, from the first click to the expected element, with visible labels only (the 180 s budget is talking time):

| Step | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Total |
|------|---|---|---|---|---|---|---|---|---|----|-------|
| Seconds | 1.08 | 0.56 | 0.38 | 0.30 | 1.73 | 0.26 | 0.08 | 1.74 | 0.08 | 0.48 | 6.69 |

- Step 4 and step 5 include the compare narrative and the scenario explanation; both were already in the response cache from the capture run. Uncached on `deepseek-v4-pro:cloud`: a compare narrative took 2.8 s (POST /compare, another set of three), the first lunar Explain 3.4 s. The rehearsal warms the cache for the prepared set.
- Ask (streamed, never cached): 1.4 to 1.7 s for the full answer in the browser, 1.0 to 1.3 s through the API for the three candidate questions.
- Deploy (not re-run for this script, to keep the live stack): last measured on this Mac, live mode about 2 to 3 minutes including scoring, mock mode about 25 seconds. The last seed ingest_run of the current stack took 6.4 s.

## Recovery lines

- **A panel is slow** (spinner over 5 s): "While that loads, here is the same view from this morning." Switch to the fallback slide for the step (slides 4 to 21), keep talking, return to the browser at the next step.
- **Explain shows something else**: live output varies. If it shows different sentences, read the first one and its citation. If it shows "No written summary was generated for this selection." or "The language model is unavailable, so no written summary was generated.", say: "The verifier only lets through sentences it can trace to a test row, and it found none this time; the coverage, the gravity bounds and the 840 matching runs are computed without a model." Then show slide 14.
- **Ask shows only the fixed sentence** ("The curated PSI corpus does not contain enough information to answer that."): say "When the verifier cannot trace a sentence to a source it removes it - that is the safety net." Ask the backup question "What did SAFFIRE-II measure?", or show slide 18.
- **The live model is slow or unavailable** (Ollama down, cloud model timing out after LLM_TIMEOUT_S = 120 s): only three things need it - the Compare narrative, Scenario Explain and Ask. Compare and Scenario stay usable (documented behaviour of CF-06, CF-07 and CF-09): the narrative panel shows the unavailable notice while the matrix, lineage, coverage, bounds and matches still render. Ask shows an error but keeps the retrieved sources. Say: "Only three features call a model at request time; everything else is deterministic, as you can see." Show slide 18 for Ask.
- **Switch to mock mode** (between talks, not live): set `LLM_PROVIDER=mock` and `EMBED_PROVIDER=mock` in `.env`, then `make undeploy && make deploy` (about 25 s in mock mode). The top-bar badge then reads "mock". Mock answers are deterministic but synthetic; say so if asked.
- **The stack is down**: run `make deploy` (live mode about 2 to 3 minutes including scoring; mock about 25 s), then `make status`. Meanwhile present from the fallback slides 4 to 21. Say: "The deck is built from captures of this exact stack; let me walk you through them while it comes back."
- **The browser or laptop fails**: present slides 4 to 21 in order; the speaker notes hold the same clicks and words.

## 60-second short version (steps 2, 5, 6, 8)

| Time | Route | Clicks | Words |
|------|-------|--------|-------|
| 0:00-0:15 | `/ranking` | Sidebar "Ranking"; PRESET "Lunar habitat"; tab "Habitat"; "Evidence" on row 1 (FLEX); Esc. | "Pick the lunar-habitat priorities and the ranking changes instantly; every score opens its rationale and source." |
| 0:15-0:30 | `/scenario` | Sidebar "Scenario Lab"; PRESET "Lunar habitat (assumed default)". | "Seven investigations hold 840 runs close to her habitat, and partial gravity is bounded by 0 g and 1 g instead of invented." |
| 0:30-0:40 | `/extract` | Sidebar "Data Extract"; "Export CSV". | "Modelers get all 2,003 runs with provenance columns and the filters in the header." |
| 0:40-1:00 | `/ask` | Sidebar "Ask"; type "What is known about smoke detection in microgravity?"; "Ask"; chip "1". | "And any question gets a streamed answer where every sentence is cited or removed." |
