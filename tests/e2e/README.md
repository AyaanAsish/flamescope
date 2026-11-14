# End-to-end tests

Browser journeys with Playwright for Python (Chromium) against the deployed stack, as listed in
`docs/architecture/12-testing-strategy.md` section 3. Every file names the requirement IDs and
call flows it covers (document 13 section 1). Selectors are the `data-testid` values of document
10 section 5; what the UI shows is cross-checked against the API instead of hard-coded.

| File | Covers |
|------|--------|
| `test_e2e_00_shell.py` | NFR-03, NFR-02, NFR-09: dark tokens, sidebar order and navigation, top-bar badges, footer, global search, every route clean at 1440 and 1024 px |
| `test_e2e_01_overview.py` | FR-14, FR-16 (CF-11) |
| `test_e2e_02_explorer.py` | FR-01, FR-02, FR-06, FR-15 (CF-04) |
| `test_e2e_03_ranking.py` | FR-03, FR-04, FR-15, NFR-09 (CF-05) |
| `test_e2e_04_compare.py` | FR-05, FR-12 (CF-06) |
| `test_e2e_05_scenario.py` | FR-07, FR-08, FR-16, NFR-09 (CF-07) |
| `test_e2e_06_extract.py` | FR-08, FR-15 (CF-08) |
| `test_e2e_07_safety_earth.py` | FR-09, FR-10, FR-16 (CF-10) |
| `test_e2e_08_ask.py` | FR-11, FR-15 (CF-09) |
| `test_e2e_09_architecture.py` | FR-13 (CF-12) |
| `test_e2e_10_visual.py` | NFR-03: screenshots, axe-core, focus ring, reduced motion |
| `test_e2e_99_undeploy.py` | NFR-01 (CF-13); marker `lifecycle`; skipped with `KEEP_STACK=1` |

## Running

- All end-to-end tests (installs Chromium, writes `tests/reports/e2e.xml` and `e2e.html`):
  `make test-e2e`. The last file runs `make undeploy`; keep the stack with `KEEP_STACK=1 make test-e2e`.
- The harness (`conftest.py`) reuses a stack that is ready in mock mode; otherwise it runs
  `make deploy` once with `LLM_PROVIDER=mock EMBED_PROVIDER=mock`, whatever `.env` says.
- One file: `KEEP_STACK=1 .venv/bin/python -m pytest tests/e2e/test_e2e_03_ranking.py`.
- One test: add `-k <name>`, for example `-k evidence_drawer`.
- Headed, to watch the browser: `HEADED=1 KEEP_STACK=1 .venv/bin/python -m pytest tests/e2e/test_e2e_04_compare.py`.
- axe-core comes from `src/ui/node_modules/axe-core` (`make ui-install`).

## Artifacts

- `tests/e2e/artifacts/<test>.png` and `<test>.trace.zip`: full-page screenshot and Playwright
  trace of a failing test (open a trace with `.venv/bin/python -m playwright show-trace <file>`).
- `tests/e2e/artifacts/screens/<route>.png`: full-page screenshot of every route at 1440x900
  from `test_e2e_10_visual.py` (`overview`, `explorer`, `investigation-detail`, `ranking`,
  `compare`, `scenario`, `extract`, `safety-tech`, `earth`, `ask`, `architecture`).
- `make clean` removes `tests/e2e/artifacts/`.

## Rules

- Each test fails on any browser console error or failed request (requests the page cancels
  itself, `net::ERR_ABORTED`, are not failures). Links to public source sites are answered by a
  local stub page, so no test reaches the internet.
- Seed data has no test runs, fuels or findings (document 01 OI-06); where a journey's data is
  absent, the test asserts the documented empty state instead of skipping.
