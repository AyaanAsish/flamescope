# Prompt 01 - Claude Code project setup: rules, skills and agents

You are setting up this repository so that every later session builds FlameScope exactly as designed. Do not write application code in this session.

## Step 0 - Read (mandatory, before anything else)

Read every file in `docs/architecture/` in numeric order, completely: `00-README.md` through `13-traceability-and-conformance.md`. Then read `prompts/00-README.md`. These documents are the project's single source of truth. Everything you create in this session exists to make later sessions follow them without deviation.

Before creating files, check the current Claude Code documentation for the correct locations and front-matter fields of project memory (`CLAUDE.md`), rules (`.claude/rules/`), skills (`.claude/skills/<name>/SKILL.md`), subagents (`.claude/agents/<name>.md`) and settings (`.claude/settings.json`). If the documented conventions differ from the paths named here, follow the documentation and tell me what you changed.

## Step 1 - `CLAUDE.md` (repository root)

Keep it under 120 lines. It must contain:

1. One paragraph: what FlameScope is (from `docs/architecture/00-README.md`).
2. **The prime directive**: `docs/architecture/` is binding. Read the governing document sections before touching an area. Names in the documents (paths, modules, classes, endpoints, JSON fields, tables, columns, environment variables, Makefile targets, `data-testid` values, component IDs) are contracts. If the design is wrong or incomplete: stop, cite document and section, propose the change, and update the document in the same change set. Never leave code and documents disagreeing.
3. A table mapping areas to governing documents (copy the index from `00-README.md`).
4. Repository layout (document 02 section 4) in brief, with the rule that all source code is under `src/`.
5. Layer and import rules in five bullets (document 02 section 2, document 03 section 10).
6. Commands: the Makefile targets from document 11 section 4.
7. Working rules:
   - Never run state-changing git commands (add, commit, push, pull, merge, rebase, reset, stash, checkout of files, tag). The repository owner commits manually. Read-only git (status, diff, log) is fine.
   - Never add AI or tool attribution to any file, comment, document or message.
   - Target toolchain: Python 3.12, Docker, macOS. Next.js for the UI, dark theme only.
   - Mock mode (`LLM_PROVIDER=mock`) and seed ingestion must always keep working.
   - No scientific fact without a source reference; unknown is `null`.
   - After completing any new kind of task, reflect: if a reusable procedure emerged, update the relevant skill in `.claude/skills/` or create a new one.
8. Definition of done: the conformance checklist in document 13 section 4.

## Step 2 - Rules in `.claude/rules/`

Create one Markdown file per rule set. Where path scoping is supported, scope each to the paths shown. Each file: short, imperative, with the document references that justify each rule.

| File | Scope | Must cover |
|------|-------|-----------|
| `00-architecture-bible.md` | all | Read-before-write; names are contracts; no extra surface (no undeclared endpoints, tables, routes, dependencies); conflict procedure; conformance checklist at the end of every task. |
| `10-python.md` | `src/common/**`, `src/agents/**`, `src/api/**`, `src/ingest/**` | Python 3.12, full type hints, Pydantic v2, SQLAlchemy 2.x style, ruff and mypy clean; routers have no business logic; services deterministic; repositories own SQL; no provider SDK imports outside `flamescope_common/llm/providers`; structured logging with request ID; error classes from `flamescope_common.errors`. |
| `20-agents-and-prompts.md` | `src/agents/**` | One agent, one prompt file, one schema; no prompt text in Python; grounding rules; mock fixtures required for every agent; prompt versions bumped on change (document 07). |
| `30-ui.md` | `src/ui/**` | Next.js App Router, TypeScript strict; dark theme tokens only (document 10 section 2), no hard-coded colours outside tokens; four panel states; `data-testid` values from document 10 section 5; all API access through `lib/api`; URL-mirrored state; accessibility rules. |
| `40-data-and-grounding.md` | `src/data/**` | Seed file format (document 06 section 5); every fact has a `source` with an allowed URI; unknown is `null`; controlled vocabularies (document 04 section 5); never invent numbers, DOIs or links. |
| `50-testing.md` | `tests/**`, `src/ui/**/*.test.*` | Test file names and cases from document 12; deterministic, mock provider; no network; tests assert against the documents' worked examples; never weaken or delete a failing test to make it pass - fix the code or raise a design conflict. |
| `60-devops.md` | `deploy/**`, `Makefile` | Document 11: target names, compose project name, non-root images, health checks, macOS make 3.81 compatibility, both Apple Silicon and Intel. |
| `70-git-and-attribution.md` | all | No state-changing git; no attribution; keep `CLAUDE.md`, `.claude/`, build logs and agent briefs out of version control via `.gitignore`. |

## Step 3 - Skills in `.claude/skills/<name>/SKILL.md`

Each skill has front matter (`name`, `description` that says precisely when to use it) and a body with a numbered procedure, the documents to read, the files to touch, and a verification step. Create these:

| Skill | When | Procedure essentials |
|-------|------|----------------------|
| `arch-lookup` | Before any implementation task | Map the task to requirement IDs, components, endpoints, call flows and tests using document 13 section 1; list the exact document sections to read; output a short "governing spec" note. |
| `conformance-check` | End of every task and on request | Walk document 13 section 4; verify paths, names, endpoint inventory, Makefile targets, UI routes and test IDs by inspecting the repository; report pass / fail per line with file references; never edit code. |
| `add-endpoint` | Adding or changing an API endpoint | Confirm it exists in document 05 (else conflict procedure); schema in `flamescope_common/schemas/api.py`; router; service; repository; unit + integration test; update UI types. |
| `add-agent` | Adding or changing a runtime agent | Contract in document 07; prompt file with front matter; schemas; agent class; orchestrator registration; mock fixture; unit tests including prompt-file validation. |
| `seed-investigation` | Authoring or correcting a seed file | Gather PSI overview and publication sources; fill the YAML per document 06 section 5; nulls for unknowns; validate against `InvestigationCard`; run seed ingestion for that acronym; review report. |
| `ui-view` | Building or changing a UI route | Read document 10 for the route; components; hooks; four states; tokens; test IDs; Vitest test; check at 1440 and 1024 widths. |
| `arch-diagram-sync` | When document 03 or 09 changes, or the Architecture page is built | Regenerate `src/ui/content/architecture/*.json` and `flows/*.mmd` from the documents; hand-set positions with no overlaps and no edge crossing a node; run the content integrity test. |
| `stack-ops` | Building, deploying, debugging the stack | Makefile targets; reading logs; readiness checks; common failures on macOS (ports in use, Docker not running, architecture mismatch). |
| `test-authoring` | Writing tests at any level | Which level; file naming from document 12; fixtures; determinism; mapping to requirement IDs. |
| `skill-maintenance` | After any new kind of task | Reflect on what was learned; update the relevant skill or create a new one; keep skills short and procedural. |

## Step 4 - Subagents in `.claude/agents/<name>.md`

Each file has front matter (`name`, `description` stating when to delegate to it, `tools` limited to what the role needs) and a system prompt that: states the role, lists the documents it must read first, lists the paths it owns, repeats the prime directive, and defines its done criteria.

| Agent | Owns | Reads first | Tools |
|-------|------|-------------|-------|
| `architect` | nothing (read-only reviewer); runs conformance checks and rules on design conflicts | all documents | read, search only |
| `backend-engineer` | `src/common/`, `src/api/` | 02, 03, 04, 05, 08, 09 | read, write, shell |
| `agent-engineer` | `src/agents/`, `src/common/flamescope_common/llm/` | 03, 07, 08 | read, write, shell |
| `ingest-engineer` | `src/ingest/` | 03, 04, 06, 07 | read, write, shell |
| `data-curator` | `src/data/` | 01 section 6, 04, 06 section 5, 08 | read, write, web lookups for PSI sources |
| `ui-engineer` | `src/ui/` | 05, 09, 10 | read, write, shell |
| `test-engineer` | `tests/`, UI test files | 12, 13 and the documents for the code under test | read, write, shell |
| `devops-engineer` | `deploy/`, `Makefile` | 11, 12 section 2 | read, write, shell |
| `docs-writer` | `README.md`, `docs/decks/` sources | 00, 01, 11, 13 | read, write |

All agents: no state-changing git, no attribution, stop and report on design conflict.

## Step 5 - Settings and ignore files

1. `.claude/settings.json`: deny state-changing git commands (`git add`, `git commit`, `git push`, `git pull`, `git merge`, `git rebase`, `git reset`, `git stash`, `git checkout`, `git tag`) and allow the project's routine commands (make targets, pytest, ruff, mypy, npm scripts, docker compose). Use the permission syntax from the current documentation.
2. `.gitignore`: add `CLAUDE.md`, `.claude/`, `*.build.log`, `agent-briefs/`, plus standard Python, Node, Next.js, Docker and macOS entries (`.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `node_modules/`, `.next/`, `.env`, `.DS_Store`, `tests/reports/`, `tests/e2e/artifacts/`). Do not ignore `prompts/` or `docs/`.

## Step 6 - Verify and report

1. List every file you created with a one-line purpose.
2. For each rule, skill and agent, name the document sections it enforces.
3. Confirm nothing under `src/`, `tests/` or `deploy/` was created.
4. Report any documentation-versus-convention differences you found in Step 0.

Do not run any git command that changes state. Do not add attribution anywhere.
