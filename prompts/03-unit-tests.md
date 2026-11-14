# Prompt 03 - Unit tests

Write the unit test suite for FlameScope. The tests verify that the code implements the architecture documents; the documents, not the current code, define correct behaviour.

## Contract

1. Read `docs/architecture/12-testing-strategy.md` fully, then `13-traceability-and-conformance.md`, then documents 03, 04, 05, 06, 07, 08 and 10. Read the code under `src/` only after that.
2. Expected values come from the documents (for example the worked examples in document 08 section 6), never from running the code and copying its output.
3. If a test fails because the code deviates from the documents, fix the **code**. If the documents are wrong, follow the conflict procedure: record it in `docs/architecture/DESIGN-CONFLICTS.md` and report it. Never weaken, skip or delete a test to get a green run.
4. Unit tests need no Docker, no database server, no network and no real LLM. Use `LLM_PROVIDER=mock`, fakes for repositories, `respx` for HTTP, and `tmp_path` for files.
5. Scope: `tests/unit/**`, `tests/conftest.py` (shared fixtures only), and UI tests beside the code in `src/ui/` (`*.test.ts`, `*.test.tsx`), plus `vitest.config.ts` and test setup if missing. No integration or end-to-end tests here.
6. No state-changing git commands. No attribution in any file.

## Python unit tests

Create exactly the directory layout and file names in document 12 section 1. Each file covers at least the cases the document lists; add edge cases where they follow from the documents. Mark all with `@pytest.mark.unit`.

Required content, by area:

**common**
- `test_config.py`: defaults equal document 11 section 3; environment overrides; invalid provider rejected.
- `test_units.py`: psi to kPa (14.7 psi is 101.35 kPa within 0.1; 10.2 psi is 70.3; 8.2 psi is 56.5; 4.3 psi is 29.6), percent to fraction, flow unit conversions, gravity labels.
- `test_rubric.py`: `rubric.yaml` loads; three lenses with the five criterion IDs each from document 08; weights per lens sum to 1; presets reference only existing lenses and criteria.
- `test_sources.py`, `test_schemas_card.py`: `SourceRef` required fields and allowed URI schemes; `InvestigationCard` accepts nulls for unknowns and rejects unknown tags.
- `test_llm_ollama_provider.py`: `model()` returns an ADK `LiteLlm` for `ollama_chat/<LLM_MODEL>` with `api_base = OLLAMA_BASE_URL`; `embed` posts to `/api/embed` (mocked with `respx`); unreachable server raises `LLMError`. No live Ollama.
- `test_llm_gateway.py`, `test_llm_mock_provider.py`, `test_llm_cache.py`: provider selection by setting (`mock`, `ollama`); `MockLlm` runs inside an ADK `Runner`; retry and timeout behaviour with a fake provider; mock determinism; schema-valid mock output for every agent; embedding length equals `EMBED_DIM` and unit norm; cache hit avoids a second provider call; no provider SDK import outside the providers package.

**agents**
- `test_prompt_files.py`: every runtime prompt file exists, has valid front matter with `name`, `version`, `output_schema`, has `## System` and `## User`, uses only variables the agent supplies, and its includes resolve.
- `test_base_agent.py`, `test_orchestrator.py`: rendering, schema validation, retry on invalid JSON (max 2), `LLMError` after final failure, logging fields.
- One file per agent: input validation, schema-valid output in mock mode, contract rules (scorer: non-null value requires evidence; scenario interpreter: repeats the gravity statement for non 0/1 gravity and flags extrapolated or no-data dimensions; insight QA: citation markers on every sentence, fixed refusal sentence).
- `test_citation_verifier.py`: supported sentence kept; number mismatch dropped; sentence without marker dropped; all dropped returns the fixed sentence; `dropped` count correct.

**api**
- `test_ranking_aggregate.py`: document 08 worked example gives 72.9 with confidence 0.85; all-null gives null; weight normalization; preset then explicit override precedence; ordering and tie-breaks; contributions sum to the score.
- `test_scenario_distance.py`, `test_scenario_coverage.py`, `test_gravity_bounding.py`: worked example similarity 0.696 (tolerance 0.001); range handling for aggregate runs; unset dimensions removed; fuel distance tiers 0, 0.3, 0.6, 1; coverage states; gravity cases 0, 1, 0.166, 0.38; gravity never changes similarity.
- `test_compare_diff_matrix.py`: attribute order equals document 05 section 6; `same` flags; shared hardware.
- `test_extract_table.py`: default columns in the documented order; provenance columns; CSV header block; null handling.
- `test_insight_fusion.py`: reciprocal rank fusion order; deduplication.
- `test_error_envelope.py`, `test_sse_format.py`: envelope shape for 400, 404, 422, 500, 502; SSE frame formatting.
- `test_routers_contract.py`: with FastAPI `TestClient` and fake services injected through dependency overrides, exercise every endpoint in document 05 section 11: status codes, response model fields, pagination bounds, validation errors, `X-Request-ID` echo, compare with 1 and 5 IDs returning 400.

**ingest**
- `test_seed_loader.py`: every file in `src/data/seed/investigations/` validates; every fact has a source with an allowed URI; tags in vocabulary; no value copied from the illustrative example in document 04.
- `test_normalizer.py`, `test_overrides.py`, `test_parser.py` (small generated HTML, PDF and CSV fixtures), `test_harvest_rules.py` (download decisions per file type and size caps with a fake S3 listing), `test_quote_verification.py`, `test_chunking.py` (size 1000, overlap 150, section boundaries), `test_cli.py` (commands exist with the documented names and options).

**architecture**
- `test_import_rules.py`: parse imports with `ast` and enforce the table in document 03 section 10.
- `test_docs_conformance.py`: registered API routes equal the inventory in document 05 section 11 (parse the document); repository layout directories from document 02 section 4 exist; every runtime prompt file named in document 07 exists; UI architecture JSON `componentId` values appear in document 03; a `flows/cf-NN.mmd` file exists for every CF heading in document 09. Tests that depend on files from later prompts (Makefile targets, Dockerfiles) are written now and marked `xfail(strict=False, reason="created by prompt 04/05")` only for those specific assertions.

## UI unit tests (Vitest + Testing Library)

- `lib/format.test.ts`: fraction to percent, kPa to psi toggle, number formatting with units.
- `lib/api/sse.test.ts`: frame parser handles split chunks, multiple events per chunk, the documented event order, and the `error` event.
- `lib/api/client.test.ts`: error envelope mapped to `ApiError`.
- Components: `WeightSliders` (normalization, callbacks), `StackedScoreBar`, `DiffMatrix` (same and different markers, not colour alone), `CoveragePanel` (three states with icon and label), `GravityBoundingCard`, `CitationChip`, `StatusBadge`, `InvestigationCard`.
- Pages: each of the eleven routes renders loading, empty, error and data states with a mocked API layer, and exposes the `data-testid` values from document 10 section 5.
- `content/architecture/content.test.ts`: every diagram has unique node IDs; every edge references existing nodes; no two node rectangles in a diagram overlap (use declared width and height); every `componentId` is in the list derived from document 03; all seven tabs are exported.
- Design tokens: `globals.css` defines every token in document 10 section 2.1 with the documented value.

## Run and report

1. Run `pytest tests/unit -q` and `npm test` in `src/ui`. All tests pass with no network.
2. Report coverage against the targets in document 12 section 1 and list any gaps.
3. List every code fix you made because the code deviated from the documents, citing document and section.
4. List any `DESIGN-CONFLICTS.md` entries.
