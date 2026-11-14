# Prompt 10 - README (final step)

Write the repository `README.md`. This is the last prompt: document what exists and works, verified against the repository and the running stack. Do not describe intentions.

## Contract

1. Read all of `docs/architecture/` and inspect the repository: `Makefile`, `deploy/`, `src/`, `tests/`, `.env.example`, `docs/decks/`. Where the documents and the repository differ, the README describes the repository as it is and you list the difference in your report (and in `docs/architecture/DESIGN-CONFLICTS.md` if not already there).
2. **Verify every command you print.** From a clean state on this machine run the quick-start sequence exactly as written in the README and confirm it works. Record real durations and real counts (investigations, endpoints, tests). No command, path, port, variable or target may appear in the README unless you confirmed it exists.
3. Facts about NASA, PSI and the challenge come from `docs/architecture/01-requirements-and-scope.md` only.
4. No AI or tool attribution, no badges for services that are not configured, no emoji. No state-changing git commands.
5. Scope: `README.md` at the repository root and images under `docs/images/` (copy selected screenshots from `tests/e2e/artifacts/screens/`). Nothing else.

## Style

Professional, direct, scannable. Short paragraphs, tables for reference material, fenced code blocks with the shell language tag for commands. Sentence-case headings. Relative links to documents. Target length 300 to 450 lines. Written for three readers: a judge with two minutes, an engineer who wants to run it on a Mac, and a contributor who wants to extend it.

## Required sections, in order

1. **Title and one-line description**; then a hero screenshot of the Overview page (dark UI) from `docs/images/`.
2. **What it does** - four bullets mapped to the challenge objectives O1 to O4, each naming the view that delivers it.
3. **Screens** - a compact gallery: Ranking, Scenario Lab, Data Extract, Ask, Architecture (one line each).
4. **Quick start (macOS)** - prerequisites with versions (Docker Desktop or Colima, Docker Compose v2, GNU Make, Python 3.12, Node for local UI work); then:
   ```bash
   make doctor
   make build
   make deploy
   make open
   ```
   State what each does, how long it took on your run, the URLs (UI, API docs, Architecture page), and that the default mode runs seed data with `qwen2.5:0.5b` on the host's Ollama (prerequisite: Ollama installed and `make ollama-pull`), with a fully offline mock mode for tests and fallback. Then `make undeploy`.
5. **LLM modes** - Google ADK agents on Ollama (`qwen2.5:0.5b`, `nomic-embed-text`) versus `mock`; the variables to set in `.env`, `make restart`, what changes in the UI (mode badge), and the note about embedding dimension and re-indexing.
6. **Harvesting from PSI** - what `make ingest-harvest` does, the public bucket and prefix variables, download limits, review and overrides, exporting reviewed cards back to seed files. State plainly what was and was not verified against the live bucket.
7. **Architecture at a glance** - one Mermaid diagram (layers) and a paragraph; the three design principles (curate and link, AI offline and arithmetic online, provenance everywhere); a table linking to each document in `docs/architecture/`; mention the in-app Architecture page and the draw.io file.
8. **Repository layout** - the tree from document 02 section 4 as it exists.
9. **Makefile targets** - table generated from `make help`.
10. **Configuration** - table of environment variables from `.env.example` with defaults and meaning.
11. **API** - base path, link to the OpenAPI docs URL, table of the endpoints grouped by area, and two `curl` examples you executed (ranking with the lunar preset; scenario with the lunar preset) with truncated real output.
12. **Scoring method** - the three lenses, the formula in one block, the disclaimer that scores are decision aids and not safety certifications, link to document 08.
13. **Data and provenance** - what a card contains, where seed files live, the rule that unknown values stay null and every fact has a source, the partial-gravity gap and how it is presented.
14. **Testing** - the three levels, what each covers (build, deploy, every API endpoint, every UI route, undeploy), commands, where reports go, real counts and run times from your run, `KEEP_STACK=1`.
15. **Optional: Kubernetes and OpenShift** - Helm targets and key values; say whether you verified them.
16. **Troubleshooting** - port in use, Docker not running, Apple Silicon notes, stack not ready, resetting data; each with the exact command.
17. **Project decks** - links to the pitch and demo decks and the demo script.
18. **Data source and acknowledgements** - NASA Physical Sciences Informatics (PSI); NASA Space Apps Challenge 2026, "Flame in Freefall"; statement that this project is not affiliated with or endorsed by NASA.
19. **Team** - placeholder `{{TEAM_NAME}}`, `{{MEMBERS}}`.
20. **License** - state the license only if a `LICENSE` file exists; otherwise a placeholder line and list it in your report.

## Verify and report

1. Run every command block in the README in order from a clean, undeployed state; fix the README (not reality) wherever they differ, unless the difference is a defect, in which case fix the defect and report it.
2. Check every relative link and image path resolves.
3. Confirm the endpoint table matches the OpenAPI document and the targets table matches `make help`.
4. Report: commands verified with durations, counts quoted and their sources, placeholders left, differences found between documents and repository, anything not verified.
