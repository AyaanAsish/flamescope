# Prompt 07 - End-to-end tests: every UI route, the main journeys, and undeploy

Write browser-driven end-to-end tests with Playwright for Python against the deployed stack, finishing with verification of undeploy.

## Contract

1. Read `docs/architecture/12-testing-strategy.md` (section 3 is binding), then document 10 (routes, components, `data-testid` values, design tokens, Architecture page), document 09 (call flows), document 05 (API shapes used for cross-checks) and document 13.
2. Selectors are the `data-testid` values in document 10 section 5. If one is missing in the UI, add it to the UI (the document is right) and report it.
3. If a test fails because the UI or API deviates from the documents, fix the **product**. If the documents are wrong, record it in `docs/architecture/DESIGN-CONFLICTS.md`. Never weaken, skip or delete a test to pass.
4. Deterministic: mock LLM, seed data. Cross-check what the UI shows against the API (`httpx`) instead of hard-coding counts or acronyms.
5. Scope: `tests/e2e/**`. No state-changing git commands. No attribution in any file.

## Harness (`tests/e2e/conftest.py`)

- Requires the stack; if `/api/v1/ready` or the UI is not reachable, run `make deploy` once.
- Chromium, headless by default (`HEADED=1` to watch), viewport 1440x900; a `small_page` fixture at 1024x768.
- `page` fixture collects console errors and failed network requests; every test asserts none occurred (allow-list empty by default).
- On failure: screenshot and trace saved to `tests/e2e/artifacts/`.
- `api` fixture for cross-checks; `sample` fixture providing seeded acronyms chosen dynamically (a solid-fuel one, a liquid-fuel one, a gaseous-fuel one, and the gravity analogue if seeded).
- Helpers: `goto(route)`, `expect_no_layout_overflow(page)` (no horizontal scrollbar), `css_var(page, name)`.
- Marked `e2e`; ordered by file number; the undeploy test marked `lifecycle`.

## Test files (create exactly these; journeys from document 12 section 3)

- `test_e2e_00_shell.py` - `html` has class `dark`; computed `--bg`, `--surface-1`, `--accent` equal the documented token values; body background is the `--bg` colour; sidebar shows the ten views in the documented order and navigates to each; active item is marked; top bar shows the LLM mode badge `mock` and the dataset badge with the count from `/meta/stats`; footer shows the disclaimer and rubric version; global search navigates to Explorer with `q`; no console errors on any of the eleven routes; no horizontal overflow at 1440 and 1024.
- `test_e2e_01_overview.py` - stat tiles equal `/meta/stats`; the parameter-space scatter renders marks and a legend for fuel phases; the lunar-habitat envelope is drawn; top-five list equals `POST /rank` overall top five and links to detail pages; gaps card mentions partial gravity.
- `test_e2e_02_explorer.py` - card count equals API total; applying a fuel-phase filter updates cards and the URL; clearing filters restores; search by acronym finds the card; sort changes order; opening a card shows the detail header, PSI link (`target=_blank`, `rel` includes `noopener`), all seven tabs; runs table rows equal `/runs`; variables panel shows varied and fixed; a source link opens the evidence drawer.
- `test_e2e_03_ranking.py` - lens tabs switch and reorder; rank rows equal the API order; choosing the `lunar_habitat` preset updates sliders and order; dragging or keying a slider changes scores after debounce and updates the URL; reloading the URL restores state; evidence drawer shows rationale and at least one source link; disclaimer visible.
- `test_e2e_04_compare.py` - pick three investigations via the picker (and by deep link); matrix rows in documented order; same and different markers present with text or icon, not colour alone; narrative panel shows sentences with citation chips; removing one investigation updates the matrix; lineage graph renders nodes for selected investigations and their hardware; picker prevents a fifth selection.
- `test_e2e_05_scenario.py` - selecting the `lunar_habitat` preset fills oxygen 34%, pressure 56.5 kPa (and 8.2 psi after toggling units), gravity 0.166 g; coverage panel shows three states with labels and gravity as no data; gravity-bounding card contains the documented statement and names the analogue when seeded; match list equals the API order; Explain shows text and caveats; "Export matching runs" downloads a CSV whose row count equals the API extract total for that `scenario_id`; switching to gravity 0 removes the gap statement.
- `test_e2e_06_extract.py` - dictionary drawer lists columns with units; build a query with a filter; preview rows equal the API preview; toggle a column off and on; download CSV and JSON, parse them, and check provenance columns and row counts.
- `test_e2e_07_safety_earth.py` - safety-tech groups equal the API groups; each finding links to its investigation and opens its source; gaps section present; Earth page cards equal the API; sector filter works; cards link to investigations.
- `test_e2e_08_ask.py` - suggested questions present; asking one shows streaming text (content grows over time) and then the final answer with citation chips; clicking a chip highlights the source in the sources panel with a working link; related investigations link to detail pages; an out-of-corpus question shows the fixed insufficient-information sentence; input is disabled while streaming and re-enabled after; Enter submits, Shift+Enter adds a line.
- `test_e2e_09_architecture.py` - seven tabs in documented order; each React Flow tab renders nodes and edges and the minimap; node count per tab equals the content JSON; a node exists for every component ID of document 03 on the Components tab; clicking a node opens the side panel with responsibility, interfaces, source files and related call flows; clicking a related flow switches to the Call flows tab with that flow selected; every call flow CF-01 to CF-13 renders a non-empty SVG; status badges match `/meta/status` (LLM shows mock); hovering a node dims unrelated nodes; fit-view control works; legend present; no node bounding boxes overlap on any tab (compute from the DOM); "Download draw.io" returns a file.
- `test_e2e_10_visual.py` - full-page screenshot of every route at 1440x900 saved to `tests/e2e/artifacts/screens/<route>.png` (these feed the decks and README); inject axe-core and assert no serious or critical violations per route; check focus visibility by tabbing through the sidebar; check `prefers-reduced-motion` disables transitions.
- `test_e2e_99_undeploy.py` - skipped when `KEEP_STACK=1`; otherwise `make undeploy` exits 0; no containers, networks or volumes with the `flamescope` project label remain; API and UI ports are closed; running `make undeploy` again still exits 0.

## Traceability

Module docstrings name requirement IDs and call flows (document 13 section 1). Add `tests/e2e/README.md`: how to run headed, how to run one file, where artifacts go.

## Run and report

1. `make test-e2e` from a deployed stack: all pass. Then `make test` from a fully clean state: build, deploy, unit, integration, end-to-end and undeploy all pass and nothing is left running.
2. Report: tests per file, pass counts, product fixes made (with document reference), any test IDs added to the UI, accessibility findings, conflicts recorded, and the list of screenshots produced.
