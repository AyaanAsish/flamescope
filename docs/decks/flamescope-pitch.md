# FlameScope pitch deck - source outline

Judges' pitch for NASA Space Apps 2026, challenge "Flame in Freefall". The Space Apps rule for Global Award eligibility allows no more than **7 slides**; this deck has exactly seven and no backup slides. This file is the source outline; `build_pitch.py` reads the `## Slide N - ` headings and the speaker notes below and writes `flamescope-pitch.pptx`.

Structure: title (1), the problem (2), our creative process (3), the solution in two parts - what it does (4) and how it works and why to trust it (5), impact (6), roadmap and close (7).

Build: `.venv/bin/python docs/decks/build_pitch.py` (needs the `docs` extra: `python-pptx`). Modules: `pitch_style.py` (dark tokens, text styles, drawing elements; re-exported by `build_pitch.py` for the demo deck scripts), `pitch_slides.py` (the seven slides), `build_pitch.py` (assembly, notes, metadata), `verify_pitch.py` (checks). The build verifies the result: exactly 7 slides, each headline equal to its heading here, notes on every slide, headline at most 12 words, body at most 30 words (40 on the dense slides 3, 5 and 6), every shape inside the slide, a rough text-overflow estimate, screenshots present on slides 1 and 4, the repository link as the only URL in slide text and notes, and core and app properties free of tool names and of the template's 4:3 format.

Remember one idea: **FlameScope turns 12 TB of microgravity combustion data into ranked, cited fire-safety answers for the lunar habitat era.**

Spoken time: about 4 minutes (seven slides of 30 to 40 seconds).

Placeholders to fill before presenting: `{{TEAM_NAME}}` and `{{MEMBERS}}` (slide 1 and the file author). The only link is the repository, https://github.com/AyaanAsish/flamescope (slide 7).

Design: 16:9, dark theme of the product (background `#0A0E14`, surfaces `#10151D`, text `#E6EAF0`, muted `#94A3B8`, flame orange `#F97316`, cool blue `#38BDF8`), Inter for text (Helvetica Neue or Arial where Inter is not installed), JetBrains Mono for numbers. Diagrams are native shapes. Screenshots are real 1440 x 900 captures of the running stack (live mode: Ollama, real seed data of 25 investigations and 2,003 runs) in `screens/`, with a 1 px `#232B38` border and rounded corners.

## Slide 1 - FlameScope

**On the slide:** challenge chip "NASA Space Apps 2026 - Flame in Freefall"; title "FlameScope"; the one idea; `{{TEAM_NAME}}`; `{{MEMBERS}}`; the Overview parameter-space scatter (every test run by oxygen and pressure, coloured by fuel phase, lunar-habitat envelope shaded).

### Speaker notes

Say: We are {{TEAM_NAME}}, and our answer to Flame in Freefall is FlameScope. NASA's Physical Sciences Informatics repository, PSI, holds the combustion investigations flown in microgravity. FlameScope turns that archive into ranked, cited fire-safety answers for the people who will design lunar habitats. The picture behind me is real: every one of the 2,003 curated test runs, plotted by oxygen and pressure, with the lunar-habitat envelope shaded. Everything you will see is running, and every answer points back to its source.

Point to land: FlameScope turns 12 TB of microgravity combustion data into ranked, cited fire-safety answers for the lunar habitat era.

Transition: Why does this matter now? Look at the air a lunar habitat will breathe.

## Slide 2 - Lunar habitat air raises fire risk; the evidence is hard to use

**On the slide:** native oxygen-versus-pressure plane: Earth at sea level 21 % at 14.7 psi, spacesuit 100 % at 4.3 psi, the lunar-habitat envelope of 30 % oxygen or more at 10.2 psi or less (shaded). Right: "24 investigations", "~12 TB in PSI", "Hard to find and interpret for design."

### Speaker notes

Say: On Earth we breathe 21 percent oxygen at 14.7 psi. A spacesuit runs pure oxygen at 4.3 psi. Lunar habitats and rovers are expected at 30 percent oxygen or more and 10.2 psi or less, this shaded region, and the challenge tells us that makes materials more flammable. The evidence to design for it exists: 24 combustion investigations and about 12 terabytes in PSI. But it is stored investigation by investigation, as data folders, documents and publications, so answering one design question means reading across all of them.

Point to land: the risk is real, and the evidence exists but is hard to find and to interpret for design.

Transition: Before we wrote any code, we decided how to build something you could trust.

## Slide 3 - We wrote the design first, then built in tested phases

**On the slide:** stat cards "13 design documents", "11 decision records", "52 conflicts resolved". Build phases as chevrons: Design, Code, Unit tests, Containers, Makefile, Integration, End-to-end. Card "Design system": swatches of the dark tokens (background, two surfaces, text, flame orange, cool blue, success green, violet), "Flame-orange dark theme, WCAG AA, never colour alone, axe-checked." Card "Data curation": "25 seed files", "Each fact sourced: PSI API, experimental tables."

### Speaker notes

Say: Our process is recorded in the repository. First we wrote thirteen binding design documents and eleven architecture decision records, such as "partial gravity is a bounded gap, never a number". Then we built in phases, each with its own tests and a conformance check against the documents; all 52 design conflicts we logged along the way are resolved. The interface has its own design system: dark, flame orange, WCAG AA contrast, meaning never carried by colour alone, and an accessibility scan on every route. And the 25 seed files were curated from PSI's own repository API and experimental tables, with a source on every fact.

Point to land: design first, built and tested in phases, and every fact sourced.

Transition: Here is what that process produced.

## Slide 4 - Seven views answer every challenge objective, with sources

**On the slide:** seven live captures, each tagged with the objectives it serves: Ranking O1–O3 (lunar-habitat preset, evidence drawer open), Scenario Lab O1·O2 (lunar preset: coverage per dimension and the gravity-bounding card), Data Extract O2 (FLEX runs with a source column), Safety Tech O3 (detection and suppression findings), Ask O1–O4 (answer with a citation on every sentence), Compare O1 (FLEX, SPICE, SAFFIRE-II narrative, each sentence cited), Earth Apps O4. Key card: O1 relevant research, O2 model data, O3 safety equipment, O4 Earth uses.

### Speaker notes

Say: Seven views answer the challenge. Ranking orders all 25 investigations for a lunar habitat, and every score opens its evidence. Scenario Lab takes a design atmosphere, here the lunar preset, shows which dimensions the tests cover, and states the partial-gravity gap honestly, bounded by microgravity and normal-gravity results. Data Extract gives modelers test runs with a source on every row. Safety Tech groups findings for detection, suppression and material screening. Ask answers in plain language with a citation on every sentence; Compare does the same side by side. Earth Apps covers the Earth add-on.

Point to land: every challenge objective has a working view, and every view shows its sources.

Transition: How does it produce these answers? In plain words.

## Slide 5 - AI reads offline; every online answer is computed or cited

**On the slide:** native flow diagram. Top row: PSI archive to Ingestion ("AI offline") to PostgreSQL to Services ("deterministic") to Dashboard. Below Services: "3 AI calls" to "Citation check" up to the Dashboard. "Model: mock or Ollama". Card "Seeded catalog": 25 investigations, 2,003 test runs, 355 publications, 40 findings. Card "Tests passing": 1136 unit, 225 Vitest, 247 integration, 108 end-to-end.

### Speaker notes

Say: Ingestion reads the PSI archive once, offline: AI extracts test conditions and scores each investigation with evidence, and everything lands in one PostgreSQL database. When you click, ranking, scenario matching and export are plain arithmetic, with no AI. AI runs at request time in only three places, Ask, the compare narrative and the scenario explanation, and a citation check drops any sentence no source supports. A mock model runs everything in tests; the live model runs on Ollama. Today that is 25 investigations, 2,003 test runs, 355 publications, and over 1,700 passing tests.

Point to land: the AI does the reading offline; the answers you see are computed, and the few generated sentences are checked.

Transition: So who does this help?

## Slide 6 - Four groups get sourced fire-safety evidence they can act on

**On the slide:** four cards. O1 "Habitat engineers": "Scenario evidence, gaps stated", 25 ranked. O2 "Modelers": "Runs with provenance, as CSV", 2,003 test runs. O3 "Equipment designers": "Grouped by detection, suppression, materials", 40 findings. O4 "Earth practitioners": "Mist, smoke detection, firefighter gear", 4 applications.

### Speaker notes

Say: Four groups gain from this. Habitat fire-safety engineers enter a lunar or Mars atmosphere and get the matching tests in minutes, with the gaps stated rather than hidden. Modelers export 2,003 real test runs as CSV or JSON, each with its source. Equipment designers find 40 sourced findings, grouped by detection, suppression and material screening. And on Earth, four applications link the evidence to fine water mist extinguishers, smoke detection, firefighter gear and cleaner combustion. Every one of these is a click away, and every one points back to PSI.

Point to land: each challenge objective has a user who now gets sourced evidence instead of a search.

Transition: Here is where FlameScope goes next.

## Slide 7 - FlameScope turns 12 TB into cited fire-safety answers for lunar habitats

**On the slide:** roadmap cards 01 "Partial-gravity data from LUCI and FM2, when available", 02 "Human review of curated cards", 03 "More PSI disciplines", 04 "Per-run data where tables lacked conditions". Band: the repository link and "Thank you".

### Speaker notes

Say: Next, partial-gravity data from LUCI and FM2 when it becomes available; FlameScope already shows the gap it will fill. Second, a human review of the 25 curated cards, which are sourced but not yet reviewed. Third, the other PSI disciplines; discipline is already a column. Fourth, per-run data where the experimental tables gave only ranges. FlameScope turns 12 terabytes of microgravity combustion data into ranked, cited fire-safety answers for the lunar habitat era. The code is at this link. Thank you.

Point to land: the one idea, and that the path forward is concrete.

Transition: none; take questions.

## Numbers and sources

| Number | Where it appears | Source |
|--------|------------------|--------|
| 24 investigations, about 12 TB | slides 1 (idea), 2, 7 | Challenge text, `docs/architecture/01-requirements-and-scope.md` section 1 |
| Earth 14.7 psi; spacesuit 100 % O2 at 4.3 psi; lunar habitats 30 % O2 or more at 10.2 psi or less | slide 2 | Challenge text, doc 01 section 6 |
| Earth sea level 21 % O2 | slide 2 | `iss_cabin` preset "sea-level atmosphere" 0.21 at 101.3 kPa (14.7 psi), doc 08 section 4.1 |
| 13 design documents | slide 3 | `docs/architecture/01` to `13` (plus the index `00-README.md`) |
| 11 decision records | slide 3 | ADR-01 to ADR-11, doc 02 section 7 |
| 52 conflicts resolved | slide 3 | `docs/architecture/DESIGN-CONFLICTS.md`: "DC-01 to DC-52 were resolved on 2026-11-14 (doc 13 section 5)" |
| Build phases | slide 3 | `prompts/00-README.md` order: code, unit tests, containers, Makefile, integration, end-to-end |
| Design system: dark only, flame orange, WCAG AA, not colour alone, accessibility scan | slide 3 | Doc 10 sections 2, 2.1 and 2.3; NFR-03; `tests/reports/e2e.xml`: 11 `test_route_screenshot_and_axe` cases passed |
| PSI API records and experimental tables; every fact sourced | slide 3 | Doc 13 section 5 change log (2026-11-14 seed curation rows); seed source locators "PSI repository record, geode-py API" and "PSI-NN Experimental table" in `src/data/seed/investigations/*.yaml`; doc 01 OI-06 |
| Seven views and their objectives | slide 4 | Doc 01 section 3: FR-03 Ranking O1-O3, FR-07 Scenario O1-O2, FR-08 Extract O2, FR-09 Safety Tech O3, FR-11 Ask O1-O4, FR-05 Compare O1, FR-10 Earth O4 |
| Partial gravity bounded by 0 g and 1 g; LUCI and FM2 | slides 4 (notes), 7 | Doc 01 section 6 and FR-16; ADR-08; doc 08 section 4.4 |
| Ingestion with AI offline; three request-time AI calls; citation check; mock and live model | slide 5 | ADR-02, ADR-03, ADR-07, ADR-11 (doc 02 section 7); FR-11 ("unsupported claims are removed"); NFR-02, NFR-07 |
| 25 investigations, 2,003 test runs, 355 publications, 40 findings | slides 1 (notes), 4 (notes), 5, 6 | `GET http://localhost:8000/api/v1/meta/stats` on the live stack, 2026-11-14 (ingest of 2026-11-15T01:09:53Z, mode `seed`): `investigations` 25, `test_runs` 2003, `publications` 355, `findings` 40 (also `chunks` 215; fuel phases gas 9, liquid 6, solid 8; `o2_range` [0.12, 0.85]; `pressure_range_kpa` [25.331, 506.625]) |
| 25 seed files cover all 24 PSI Combustion Science records | slides 4 (notes), 7 (notes) | Doc 01 section 7, OI-06 (PSI-47 holds DAFT and DAFT-2, seeded as two files; cards `reviewed: false`) |
| 1136 unit tests passed | slide 5 | `tests/reports/unit.xml`, final clean `make test` of 2026-11-14 20:02: 1137 tests, 1 skipped (the expected `README.md` xfail), 0 failures |
| 225 Vitest tests passed | slide 5 | `npx vitest run` in `src/ui`, 2026-11-14 (24 files, 225 tests; Vitest writes no file to `tests/reports/`) |
| 247 integration tests passed | slide 5 | `tests/reports/integration.xml`, 2026-11-14 20:02: 247 tests, 0 failures |
| 108 end-to-end tests passed | slide 5 | `tests/reports/e2e.xml`, 2026-11-14 20:04: 108 tests, 0 failures |
| Over 1,700 tests | slide 5 (notes) | Sum of the four suites: 1136 + 225 + 247 + 108 = 1716 |
| 40 findings grouped by detection, suppression, material screening | slide 6 | `GET /api/v1/insights/safety-tech` on the live stack: Detection 9, Suppression 2, Material screening 4, Post-fire hazards 1, Atmosphere design 4, Fundamental combustion 20 |
| 4 Earth applications | slide 6 | `GET /api/v1/earth-applications` on the live stack: smoke detection, fine water mist extinguishers, firefighter gear, electric-field control of flames (`src/data/seed/earth_applications.yaml`) |
| Lunar and Mars presets | slide 6 (notes) | Doc 08 section 4.1 (`lunar_habitat`, `mars_habitat`, labelled "assumed default") |
| Roadmap: LUCI and FM2; human review; other disciplines; per-run data | slide 7 | Doc 01 section 6 (LUCI, FM2), section 5 (discipline is a column), section 7 OI-06 (`reviewed: false`; aggregate ranges where only a range is stated) |
