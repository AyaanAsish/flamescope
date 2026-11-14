# FlameScope Build Prompts

Numbered prompts for Claude Code. Run them in order, one per session (or one per `/clear`), from the repository root. Each prompt is self-contained: paste the whole file as the message.

| # | File | Produces | Needs |
|---|------|----------|-------|
| 01 | `01-claude-code-setup.md` | `CLAUDE.md`, `.claude/rules`, `.claude/skills`, `.claude/agents`, `.gitignore` entries | docs only |
| 02 | `02-code.md` | Everything under `src/` (common, agents, api, ingest, ui, data), `pyproject.toml`, `.env.example` | 01 |
| 03 | `03-unit-tests.md` | `tests/unit/`, UI unit tests | 02 |
| 04 | `04-dockerfiles.md` | `deploy/docker/` Dockerfiles, compose, `.dockerignore`, optional Helm chart | 02 |
| 05 | `05-makefile.md` | `Makefile`, `deploy/scripts/` | 04 |
| 06 | `06-integration-tests.md` | `tests/integration/` covering build, deploy and every API | 04, 05 |
| 07 | `07-e2e-tests.md` | `tests/e2e/` covering every UI route and undeploy | 06 |
| 08 | `08-pitch-deck.md` | `docs/decks/flamescope-pitch.pptx` | 02 (07 for screenshots) |
| 09 | `09-demo-deck.md` | `docs/decks/flamescope-demo.pptx` and demo script | 07 |
| 10 | `10-readme.md` | `README.md` | everything |

Why this order: integration and end-to-end tests verify the build and deploy phases, so the Dockerfiles (04) and the Makefile (05) come before them. The README is last so it documents what actually exists.

## The contract every prompt enforces

`docs/architecture/` is the single source of truth. Every prompt begins by making Claude Code read the governing documents and ends with a conformance check against `docs/architecture/13-traceability-and-conformance.md`. If the design and reality conflict, Claude Code must stop and report rather than improvise.

## Standing rules repeated in every prompt

- All source code under `src/`; tests under `tests/`; container and deploy files under `deploy/`; architecture under `docs/`; these prompts under `prompts/`.
- No git commands that change state (no add, commit, push, reset, stash, checkout of files). Leave changes in the working tree.
- No AI or tool attribution in any file, comment, commit text or document.
- Python, Docker and macOS are the target toolchain.
- Do not invent scientific facts. Unknown values are `null` and every stated fact has a source.

## After each prompt

Review the summary Claude Code prints, check the working tree, and commit yourself. If a prompt reports a design conflict, fix the document (or the decision) first, then re-run.
