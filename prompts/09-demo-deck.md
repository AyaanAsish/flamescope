# Prompt 09 - Demo deck and demo script (PowerPoint)

Create the live-demo companion deck `docs/decks/flamescope-demo.pptx`, the presenter script `docs/decks/flamescope-demo-script.md`, and a pre-demo checklist `docs/decks/demo-checklist.md`.

The pitch deck (prompt 08) persuades. This deck guides a live walkthrough of the running product and doubles as a fallback if the live demo fails.

## Contract

1. Read `docs/architecture/09-call-flows.md`, `10-ui-architecture.md`, `11-deployment-and-operations.md`, `08-scoring-and-scenario.md` and `13-traceability-and-conformance.md` (section 2, objective coverage).
2. Every step in the script must work on the deployed stack in mock mode with seed data. Execute the whole path yourself in a browser automation run (Playwright) before writing the final script, and use the acronyms, counts and texts that actually appear. Do not script anything you did not see work.
3. Screenshots come from the real UI at 1440x900 (`tests/e2e/artifacts/screens/` or new captures for specific states: evidence drawer open, scenario at the lunar preset, a streamed answer with citations, the Architecture page with a node panel open).
4. Build with `python-pptx` via `docs/decks/build_demo.py`. Same dark visual system as the pitch deck (see prompt 08, "Visual design").
5. No AI or tool attribution anywhere. No state-changing git commands. No claims beyond what the product does.

## Demo storyline (about 3 minutes live)

A fire-safety engineer is choosing materials and detection for a lunar habitat at elevated oxygen and reduced pressure. She has an afternoon, not a month.

| Step | Route | Action | What the audience should notice | Objective |
|------|-------|--------|---------------------------------|-----------|
| 1 | `/` | Open Overview | The whole PSI combustion portfolio on one screen; the lunar-habitat envelope on the oxygen-pressure map; visible gaps | O1 |
| 2 | `/ranking` | Choose the `lunar_habitat` preset; open the top result's evidence drawer | Order changes with her priorities; each score links to a source | O1 |
| 3 | `/investigations/[id]` | Open the top investigation; show runs and varied versus fixed parameters | Fuels, geometry, conditions and sensors summarized | O1, O2 |
| 4 | `/compare` | Compare a solid-fuel study with a droplet study and one sharing hardware | Same and different at a glance; shared hardware lineage | O1 |
| 5 | `/scenario` | Lunar preset; point at coverage and the gravity-bounding card; click Explain | Honest about extrapolation; partial gravity bounded by 0 g and 1 g, not invented | O1, O2 |
| 6 | `/extract` | Export the matching runs as CSV | Model-ready table with provenance | O2 |
| 7 | `/safety-tech` | Show detection and suppression groups | Research mapped to equipment decisions | O3 |
| 8 | `/ask` | Ask one prepared question; click a citation | Streamed, cited answer; source opens | all |
| 9 | `/earth` | Show one application | Benefits on Earth | O4 |
| 10 | `/architecture` | Open Components tab, click a node, switch to a call flow | The design is inside the product; live status | trust |

Choose the concrete investigations and the prepared question from what the seeded stack returns; write them into the script verbatim.

## Deck structure (about 16 slides)

1. Title: "FlameScope - live demo", presenter, date placeholder.
2. Scenario card: who the user is and the question she needs answered.
3. Demo map: the ten steps as a horizontal route with route names.
4 to 13. One slide per step: left, a real screenshot with two or three numbered callouts drawn as native shapes; right, "Do", "Say" (one sentence) and "Shows" (objective tag). These slides are the fallback if the network or laptop fails.
14. Under the hood in 20 seconds: ingestion offline with AI and review, deterministic services online, three request-time AI calls, mock mode.
15. Proof: build, deploy, test with one Makefile; real numbers for unit, integration and end-to-end tests from `tests/reports/`.
16. Questions; links placeholders `{{REPO_URL}}`, `{{DEMO_URL}}`.

Every slide has speaker notes with exact click targets (use the visible labels) and a timing budget. Total 180 seconds for steps 1 to 10.

## `flamescope-demo-script.md`

- Timed table: step, seconds (cumulative), route, clicks, words to say.
- Prepared inputs: the Ask question, the investigations to compare, the scenario values.
- Recovery lines: what to do and say if a panel is slow (use the fallback slide), if the LLM is unavailable (mock mode badge; narrative panels show the documented unavailable state), if the stack is down (`make deploy`, about how long it takes on this machine - measure it).
- A 60-second short version (steps 2, 5, 6, 8).

## `demo-checklist.md`

Thirty minutes before: `make doctor`, `make deploy`, `make status`; check the LLM mode badge; open all tabs in order; zoom level 100%; notifications off; display mirroring and resolution; fallback deck open; water. After: `make undeploy` optional.

## Verify and report

1. Run the scripted path end to end with Playwright against the deployed stack and confirm each step's expected element appears; record the run time per step.
2. Validate the generated `.pptx` (slide count, titles, notes, no shapes outside slide bounds, images present); render to PNG and review if LibreOffice is available.
3. Report: the concrete investigations and question chosen, measured timings, placeholders left, and anything not verified.
