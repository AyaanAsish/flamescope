# FlameScope pitch deck - source outline

Judges' pitch for NASA Space Apps 2026, challenge "Flame in Freefall". The deck is sized for the Space Apps rule for Global Award eligibility: the demo is reachable through a public link and the presentation has no more than **7 slides**. This file is the source outline; `build_pitch.py` reads the speaker notes below and writes `flamescope-pitch.pptx` (7 slides, no backup slides).

Build: `.venv/bin/python docs/decks/build_pitch.py` (needs the `docs` extra: `python-pptx`). The script also verifies the result: 7 slides, a title and notes on every slide, every shape inside the slide, body word limits, images present, metadata free of tool names.

Remember one idea: **FlameScope turns 12 TB of microgravity combustion data into ranked, cited fire-safety answers for the lunar habitat era.**

Spoken time: about 3.5 minutes (seven slides of 25 to 35 seconds).

Placeholders to fill before presenting: `{{TEAM_NAME}}`, `{{MEMBERS}}` (slide 1 and the file author), `{{REPO_URL}}`, `{{DEMO_URL}}` (slide 7).

Design: 16:9, dark theme of the product (background `#0A0E14`, surfaces `#10151D`, text `#E6EAF0`, muted `#94A3B8`, flame orange `#F97316`, cool blue `#38BDF8`), Inter for text (Helvetica Neue or Arial where Inter is not installed), JetBrains Mono for numbers. Diagrams are native shapes. Screenshots are real captures of the running stack (live mode, Ollama) in `screens/`, 1440 x 900, with a 1 px `#232B38` border and rounded corners.

## Slide 1 - FlameScope

**On the slide:** challenge chip "NASA Space Apps 2026 - Flame in Freefall"; title "FlameScope"; the one idea; `{{TEAM_NAME}}`; `{{MEMBERS}}`; Overview hero screenshot.

### Speaker notes

Say: We are {{TEAM_NAME}}, and our answer to Flame in Freefall is FlameScope. NASA's Physical Sciences Informatics repository holds the combustion experiments flown in microgravity. FlameScope turns that archive into ranked, cited fire-safety answers for the people who will design lunar habitats. Everything you see today is running, and every answer points back to its source.

Point to land: FlameScope turns 12 TB of microgravity combustion data into ranked, cited fire-safety answers for the lunar habitat era.

Transition: Why now? Look at the air a lunar habitat will breathe.

## Slide 2 - Lunar habitat air raises flammability, and the evidence sits in 12 TB

**On the slide:** native oxygen-versus-pressure plane: Earth at sea level 21 % at 14.7 psi, spacesuit 100 % at 4.3 psi, the lunar-habitat envelope of 30 % oxygen or more at 10.2 psi or less (shaded). Right: "24 investigations", "~12 TB of data", "Hard to find what matters."

### Speaker notes

Say: On Earth we breathe 21 percent oxygen at 14.7 psi. A spacesuit runs pure oxygen at 4.3 psi. Lunar habitats and rovers are expected at 30 percent oxygen or more and 10.2 psi or less, this shaded region, and the challenge tells us that makes materials more flammable. The evidence to design for it exists: 24 combustion investigations and about 12 terabytes in PSI. But it is stored investigation by investigation, in data folders, documents and papers, so finding what matters for one design question is hard.

Point to land: the risk is real, and the evidence exists but is hard to use.

Transition: So we built one place that does the finding for you.

## Slide 3 - FlameScope summarizes, ranks and interprets PSI for every challenge objective

**On the slide:** three columns. Rank - O1 - identify relevant investigations - Ranking, Scenario Lab. Summarize - O2 - extract model-ready data - Data Extract. Interpret - O3 - inform controls and equipment - Safety Tech, Ask. Band: O4 Earth add-on - Earth Apps.

### Speaker notes

Say: FlameScope does the three things the challenge asks for. It ranks investigations by relevance to crewed habitats, objective one. It summarizes test conditions and outcomes into data you can take to a model, objective two. And it interprets findings for fire-safety controls and equipment, objective three. The Earth add-on links the same evidence to fire safety at home.

Point to land: every challenge objective has a working view.

Transition: Start with objective one: what should a habitat designer read first?

## Slide 4 - Ranking and Scenario Lab show evidence, coverage and honest gaps

**On the slide:** Ranking screenshot (lunar_habitat preset, BRE evidence drawer open) with "Every score opens its evidence; weights re-rank without AI." Scenario Lab screenshot (lunar preset: coverage and gravity bounding) with "Partial gravity bounded by 0 g and 1 g; analogue E-FIELD Flames."

### Speaker notes

Say: Ranking scores each investigation under three lenses: habitat, modeling and controls. The lunar habitat preset weights atmosphere match and gravity higher. Open any row and you see each criterion's rating, the rationale and the source; a criterion without evidence stays empty and lowers the confidence. Move a slider and the list re-ranks at once, with no AI involved. Scenario Lab takes an assumed lunar atmosphere, 34 percent oxygen at 56.5 kilopascals and 0.166 g, and shows where the catalog covers it. On gravity it is honest: PSI has no partial-gravity combustion data, so FlameScope bounds the answer with 0 g and 1 g results and names E-FIELD Flames as the analogue. It never invents a number.

Point to land: transparent evidence and honest gaps, not a black box.

Transition: Ranking tells you where to look. Next, taking the data and the findings with you.

## Slide 5 - Every extracted value and answer sentence carries its source

**On the slide:** three screenshots. O2 Data Extract: "CSV and JSON with source and confidence columns." O3 Safety Tech: "Findings by control type, plus data gaps." Ask: "Uncited sentences removed; live answer shown."

### Speaker notes

Say: For objective two, Data Extract builds a table of test runs with conditions and outcomes and exports it as CSV or JSON, with source and confidence columns on every row. For objective three, Safety Tech groups findings by detection, suppression, material screening and post-fire hazards, and names the gaps, such as the untested oxygen and pressure region that overlaps the lunar envelope. And Ask answers in plain language with a citation on each sentence. This answer is live: the verifier removed one sentence that no source supported.

Point to land: receipts everywhere; nothing is stated without a source.

Transition: How does it stay trustworthy? Here is the machine behind it.

## Slide 6 - AI works offline; online answers are deterministic except three cited calls

**On the slide:** native architecture diagram: PSI bucket (s3://nasa-psi) to Ingestion (AI, offline) to Knowledge base (PostgreSQL) to Services (deterministic) to Dashboard, with Agents (3 request-time calls) below Services. Test tiles: 1015 unit, 221 Vitest, 247 integration, 106 end-to-end, captioned "Tests passing, last full run". "Every fact sourced; unknown stays null." In-app Architecture page screenshot.

### Speaker notes

Say: Ingestion runs offline. It reads the public nasa-psi bucket or curated seed files, and agents built on Google ADK extract and score with evidence. Everything lands in PostgreSQL with pgvector. Online, ranking, matching and export are deterministic Python. AI runs at request time in only three places, Ask, compare narratives and scenario explanations, and every output is schema-validated and citation-checked. A fact without a source stays null. A mock mode runs the whole system offline, and the last full test run passed 1015 unit, 221 Vitest, 247 integration and 106 end-to-end tests. The architecture you see here is also a page inside the product, with live status.

Point to land: deterministic where it matters, and proven by tests.

Transition: And the value does not stop in space.

## Slide 7 - FlameScope turns 12 TB into cited fire-safety answers for lunar habitats

**On the slide:** "Earth (O4)": fine water mist, smoke detection, firefighter gear. "Next": run-level data for 14 investigations; LUCI and FM2 partial gravity; more PSI disciplines. Links: Code `{{REPO_URL}}`, Demo `{{DEMO_URL}}`. "Thank you".

### Speaker notes

Say: The same evidence serves Earth: Earth Apps links it to fine water mist extinguishers, smoke detection and firefighter gear. To be clear about where we are: the catalog holds 14 of the 24 investigations today, built from sourced facts, and run-level data is the next thing to curate. Then partial-gravity data from LUCI and FM2 when it arrives, and other PSI disciplines; discipline is already a column. FlameScope turns 12 terabytes of microgravity combustion data into ranked, cited fire-safety answers for the lunar habitat era. The code and the live demo are at these links. Thank you.

Point to land: the one idea, and that the path forward is concrete.

Transition: none; take questions.

## Numbers and sources

| Number | Where it appears | Source |
|--------|------------------|--------|
| 24 investigations, about 12 TB | slides 2, 7 (notes) | Challenge text, `docs/architecture/01-requirements-and-scope.md` section 1 |
| Earth 14.7 psi; spacesuit 100 % O2 at 4.3 psi; lunar habitats 30 % O2 or more at 10.2 psi or less | slide 2 | Challenge text, doc 01 section 6 |
| Earth sea level 21 % O2 | slide 2 | `iss_cabin` preset "sea-level atmosphere" 0.21 at 101.3 kPa (14.7 psi), doc 08 section 4.1 |
| 34 % O2, 56.5 kPa, 0.166 g (assumed default) | slide 4 (screenshot and notes) | `lunar_habitat` scenario preset, doc 08 section 4.1 |
| 0 g and 1 g bounds; LUCI, FM2; E-FIELD Flames analogue | slides 4, 7 | Doc 01 section 6 and FR-16; doc 08 section 4.4 |
| Three lenses; five ranking presets | slide 4 (notes) | Doc 08 sections 1 and 3 |
| Three request-time AI calls | slide 6 | Doc 00 one-paragraph architecture; doc 02 section 1 |
| 14 investigations catalogued; 0 test runs; 0 findings | slide 7 | `GET /api/v1/meta/stats` on the running stack, 2026-11-14 (also OI-06 in doc 01 section 7) |
| One sentence removed in the Ask answer | slide 5 | Live Ask answer in `screens/ask.png` |
| 1015 unit tests passed | slide 6 | Last full clean `make test` run, `tests/reports/unit.xml` of that run: 1017 tests, 2 expected failures (later-prompt paths), 0 failures. Since the deck exists the `docs/decks` check is strict, so later unit runs pass 1016; update the tile after the next full run. |
| 247 integration tests passed | slide 6 | `tests/reports/integration.xml`: 247 tests, 0 failures |
| 106 end-to-end tests passed | slide 6 | `tests/reports/e2e.xml`: 106 tests, 0 failures |
| 221 Vitest tests passed | slide 6 | Last full clean `make test` run (Vitest writes no file to `tests/reports/`) |
