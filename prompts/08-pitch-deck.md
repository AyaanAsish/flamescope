# Prompt 08 - Pitch deck (PowerPoint)

Create the judges' pitch deck for FlameScope as a PowerPoint file: `docs/decks/flamescope-pitch.pptx`, plus speaker notes and a source outline `docs/decks/flamescope-pitch.md`.

## Contract

1. Read `docs/architecture/00-README.md`, `01-requirements-and-scope.md`, `02-system-architecture.md`, `08-scoring-and-scenario.md`, `10-ui-architecture.md` and `13-traceability-and-conformance.md`. The deck must describe the system as designed and built; do not claim features that do not exist in the repository.
2. Facts about NASA, PSI and combustion come only from document 01 (challenge text) and from the seeded data and its sources. Do not add statistics, quotes or claims from memory. Numbers about the product (investigation count, run count, findings, test counts) must be read from the running stack (`/api/v1/meta/stats`) or the test reports; if the stack is not running, deploy it with `make deploy` or leave a clearly marked placeholder and list it in your report.
3. Use real screenshots from `tests/e2e/artifacts/screens/` (run `make test-e2e` with `KEEP_STACK=1` if they are missing). No mock-ups presented as the product.
4. No AI or tool attribution on any slide or in file metadata. No state-changing git commands.
5. Build the file with `python-pptx` via a script at `docs/decks/build_pitch.py` so the deck is reproducible; do not hand-edit binary files.

## Audience and goal

NASA Space Apps judges: scientists and engineers scoring on impact, creativity, validity, relevance to the challenge and presentation. In about four minutes they must understand the problem, see that the tool answers the three challenge objectives plus the Earth add-on, trust the method, and remember one idea: **FlameScope turns 12 TB of microgravity combustion data into ranked, cited fire-safety answers for the lunar habitat era.**

## Visual design

- 16:9. Dark theme matching the product: background `#0A0E14`, surfaces `#10151D`, text `#E6EAF0`, muted `#94A3B8`, accent flame orange `#F97316`, secondary cool blue `#38BDF8`. Fuel-phase colours as in document 10.
- Fonts: Inter (fallback Helvetica Neue / Arial); numbers in a monospace face.
- One idea per slide. Headline is a full-sentence claim, at most 12 words. At most 30 words of body text per slide. Generous margins, consistent grid, slide numbers, small footer "FlameScope - NASA Space Apps 2026 - Flame in Freefall".
- Diagrams are drawn natively with shapes (not pasted images) so they stay sharp; screenshots have a 1 px border `#232B38` and rounded corners.
- No clip art, no stock photos, no emoji, no animations beyond simple appear.

## Slides (13)

1. **Title** - FlameScope; tagline; team name and members (placeholders `{{TEAM_NAME}}`, `{{MEMBERS}}`); challenge name.
2. **The stakes** - a fire alarm far from Earth; lunar habitats plan oxygen at 30% or more and pressure at 10.2 psi or less, which makes materials more flammable (from the challenge text). One striking visual: oxygen versus pressure plane with Earth, spacesuit and lunar-habitat points.
3. **The problem** - decades of combustion research, 24 investigations and about 12 TB in PSI; hard to find what matters and to interpret it for design. Show the before: a folder tree.
4. **Our answer in one picture** - FlameScope: summarize, rank, interpret. Three columns mapped to objectives O1, O2, O3, plus the Earth add-on.
5. **Find what matters (O1)** - Ranking screenshot; three lenses; every score has evidence; weights are the user's.
6. **Design for a real atmosphere (O1)** - Scenario Lab screenshot at the lunar preset; coverage and the honest partial-gravity gap with 0 g and 1 g bounds.
7. **Take the data with you (O2)** - Data Extract screenshot; model-ready CSV with provenance.
8. **From research to equipment (O3)** - Safety Tech screenshot; findings grouped by detection, suppression, material screening, post-fire.
9. **Ask, with receipts** - Ask screenshot; every sentence cited; unsupported sentences are removed.
10. **How it works** - native architecture diagram: PSI bucket to ingestion to curated knowledge base to deterministic services and agents to the dashboard. Call out: AI offline for extraction and scoring, deterministic arithmetic online.
11. **Why you can trust it** - provenance on every fact; unknown stays unknown; reproducible rubric; mock mode and tests (state the real test counts).
12. **Back on Earth (O4) and what is next** - Earth applications; roadmap: partial-gravity data from LUCI and FM2 when available, more PSI disciplines, run-level sensor data.
13. **Close** - the one-sentence idea again, links (`{{REPO_URL}}`, `{{DEMO_URL}}`), thank you.

Backup slides (after the close): rubric table (document 08), data model, call flow for Ask, deployment view, objective-to-feature traceability table.

## Speaker notes

Every slide has notes: what to say in 15 to 25 seconds, the single point to land, and the transition line. Total spoken time about four minutes for slides 1 to 13. Put the same notes in `flamescope-pitch.md`.

## Verify and report

1. Open the generated file with `python-pptx` and assert: 13 main slides plus backups, every slide has a title and notes, no text box overflows its slide bounds (check shape extents), body word counts within limits, all images exist.
2. Render slides to PNG if LibreOffice is available and review each for clipped or overlapping elements; fix and rebuild. If rendering is not available, say so.
3. Report: slide list, placeholders left to fill, numbers used and where each came from, and anything not verified.
