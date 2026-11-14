# 13 - Traceability and Conformance

## 1. Requirement to design to test

| Requirement | Components | API | UI route | Call flow | Tests |
|-------------|------------|-----|----------|-----------|-------|
| FR-01 cards | C-ING, CatalogService, InvestigationRepo | `/investigations`, `/investigations/{id}` | `/explorer`, `/investigations/[id]` | CF-02, CF-03, CF-04 | `test_seed_loader`, `test_04_ingestion`, `test_11_api_catalog`, `test_e2e_02` |
| FR-02 search and filter | CatalogService | `/investigations`, `/facets` | `/explorer` | CF-04 | `test_11_api_catalog`, `test_e2e_02` |
| FR-03 ranking with evidence | ScorerAgent, RankingService, ScoreRepo | `/rank`, `/meta/rubric` | `/ranking` | CF-05 | `test_ranking_aggregate`, `test_12_api_rank`, `test_e2e_03` |
| FR-04 tunable weights | RankingService, Presets | `/rank`, `/meta/presets` | `/ranking` | CF-05 | `test_12_api_rank`, `test_e2e_03` |
| FR-05 compare | CompareService, ComparatorAgent, CitationVerifier | `/compare` | `/compare` | CF-06 | `test_compare_diff_matrix`, `test_13_api_compare`, `test_e2e_04` |
| FR-06 run variables | CatalogService, RunRepo | `/investigations/{id}/variables`, `/runs` | `/investigations/[id]` | CF-04 | `test_11_api_catalog`, `test_e2e_02` |
| FR-07 scenario | ScenarioService, ScenarioInterpreterAgent | `/scenario` | `/scenario` | CF-07 | `test_scenario_*`, `test_gravity_bounding`, `test_14_api_scenario`, `test_e2e_05` |
| FR-08 extract | ExtractService | `/extract/*` | `/extract` | CF-08 | `test_extract_table`, `test_15_api_extract`, `test_e2e_06` |
| FR-09 safety tech | SafetyTechService | `/insights/safety-tech` | `/safety-tech` | CF-10 | `test_16_api_insights_earth`, `test_e2e_07` |
| FR-10 Earth apps | EarthService, EarthAppsAgent | `/earth-applications` | `/earth` | CF-10 | `test_16_api_insights_earth`, `test_e2e_07` |
| FR-11 ask | InsightService, InsightQAAgent, CitationVerifier, ChunkRepo | `/ask` | `/ask` | CF-09 | `test_insight_*`, `test_citation_verifier`, `test_17_api_ask`, `test_e2e_08` |
| FR-12 lineage | CatalogService, linker | `/hardware`, `/projects` | `/compare` | CF-06 | `test_11_api_catalog`, `test_e2e_04` |
| FR-13 architecture page | C-UI architecture, MetaService | `/meta/status` | `/architecture` | CF-12 | UI content tests, `test_e2e_09` |
| FR-14 overview | MetaService, RankingService, SafetyTechService | `/meta/stats`, `/rank`, `/insights/gaps` | `/` | CF-11 | `test_10_api_health_meta`, `test_e2e_01` |
| FR-15 provenance | SourceRef everywhere | all | EvidenceDrawer, CitationChip | all | seed validation, `test_12`, `test_17`, `test_e2e_03`, `test_e2e_08` |
| FR-16 partial-gravity gap | ScenarioService, SafetyTechService | `/scenario`, `/insights/gaps` | `/scenario`, `/` | CF-07 | `test_gravity_bounding`, `test_14`, `test_e2e_05` |
| NFR-01 Mac + Docker | Makefile, compose | - | - | CF-01, CF-13 | `test_00`-`test_02`, `test_e2e_99` |
| NFR-02 mock mode | LLM gateway mock provider, seed mode | - | top-bar badge | CF-02 | `test_llm_mock_provider`, all integration |
| NFR-03 dark professional UI | design system | - | all | - | `test_e2e_00`, `test_e2e_10` |
| NFR-04 latency | services, indexes | non-LLM endpoints | - | - | `test_19_performance` |
| NFR-05 idempotent ingest | loader, pipeline | - | - | CF-02 | `test_04_ingestion` |
| NFR-07 ADK agents, provider swap | gateway, agents (Google ADK), Ollama | - | top-bar badge | CF-02, CF-03, CF-06, CF-07, CF-09 | `test_llm_gateway`, `test_llm_ollama_provider`, `test_orchestrator`, `test_21_llm_ollama` |
| NFR-08 test coverage | tests | - | - | - | `make test` |

## 2. Objective coverage

| Challenge objective | Primary views | Evidence in demo |
|---------------------|---------------|------------------|
| O1 identify relevant investigations | Ranking (habitat lens), Scenario Lab, Overview | Ranked list with evidence; lunar preset |
| O2 extract data for modeling | Data Extract, Ranking (modeling lens), detail runs | CSV with conditions, outcomes, provenance |
| O3 inform controls and equipment | Safety Tech, Ranking (controls lens) | Findings grouped by control type |
| O4 Earth applications | Earth Apps | Application cards linked to investigations |

## 3. Conformance rules for anyone (human or AI) changing the project

1. **Read first.** Before writing code for an area, read the documents that govern it (index in `00-README.md`).
2. **Names are contracts.** Paths, module names, class names, endpoint paths, JSON field names, table and column names, environment variables, Makefile targets, `data-testid` values and component IDs in these documents must be used exactly.
3. **No silent divergence.** If the design is wrong, incomplete or impossible, stop, state the conflict with the document and section, propose the change, and update the document in the same change set as the code. Never leave code and documents disagreeing. Unresolved conflicts are logged in `DESIGN-CONFLICTS.md` in this folder (document, section, problem, proposed resolution) until the owner decides.
4. **No extra surface.** Do not add endpoints, tables, services, routes or dependencies that the documents do not describe without following rule 3.
5. **Layer rules** (document 02 section 2) and **import rules** (document 03 section 10) are enforced by tests and may not be bypassed.
6. **Grounding.** No seed value, score, narrative or UI text may state a scientific fact without a source reference. Unknown is `null`.
7. **Determinism.** Anything that can be computed without an LLM must be. Mock mode must keep working.
8. **Tests accompany code.** A change is complete only when the tests named in section 1 for the touched requirement pass.
9. **Architecture page stays in step.** When document 03 or 09 changes, update `src/ui/content/architecture/` and the draw.io file.

## 4. Conformance checklist (used at the end of each build prompt)

- [ ] Repository layout equals document 02 section 4.
- [ ] Every component in document 03 exists at the stated path with the stated public interface.
- [ ] Database schema equals document 04; migration applies cleanly.
- [ ] The 24 endpoints of document 05 exist with the stated shapes; nothing extra.
- [ ] Ingestion stages, CLI commands and seed format equal document 06.
- [ ] Runtime prompt files, agent contracts and gateway providers equal document 07.
- [ ] Rubric, formulas, presets and worked examples equal document 08.
- [ ] Each call flow in document 09 can be traced in code.
- [ ] UI routes, tokens, components and test IDs equal document 10; the Architecture page has seven tabs.
- [ ] Containers, compose, environment variables and Makefile targets equal document 11.
- [ ] Test files and cases equal document 12.
- [ ] `make all` passes on a Mac.

## 5. Change log

| Date | Change | Documents |
|------|--------|-----------|
| 2026-11-12 | Initial architecture baseline. | all |
| 2026-11-12 | Agents on Google ADK; LLM providers reduced to `mock` and `ollama` (Ollama native on the Mac host, `qwen2.5:0.5b`, embeddings `nomic-embed-text`); new ADR-11, env vars `OLLAMA_BASE_URL`, `LLM_MODEL`, `EMBED_MODEL` defaults, Makefile target `ollama-pull`, tests `test_llm_ollama_provider`, `test_21_llm_ollama`; OI-04 resolved. | 01, 02, 03, 05, 06, 07, 09, 10, 11, 12, draw.io v2 |
| 2026-11-12 | Added code-complexity limits: radon and xenon dev dependencies, ruff `C901` / `PLR` and ESLint complexity rules; `make lint` runs xenon. | 02, 11 |
| 2026-11-14 | Design conflicts DC-01 to DC-38 from the first build resolved: modules `llm/providers/mock_agents.py` and `services/scenario_math.py`; `SeedInvestigation` and `PageRequest` schemas; extended service and pure-function signatures, service dependencies and repository methods; orchestrator async contract, `prompt_version`, `agent_names`; `CitationVerifier.verify` types; prompt variables `{{input_json}}`, `{{validation_feedback}}`, `output_schema: text`; mock fixtures optional (ADR-07); `export-seed` in doc 03; `harvest` is the full harvest run; override format; `s3_map.yaml` format; `index --force` after an `EMBED_MODEL` change; nullability; publication fields; `/extract/dictionary`, `/meta/rubric`, `/meta/presets` shapes; error-code mapping; under-specified behaviours of docs 05 and 08; aggregate-run range convention; binding `rubric.yaml` and `presets.yaml` layout, `equipment_designer` weights and `assumed_default`; challenge page allowed as a `curated` URI; interim `psi_url`; `E-FIELD-Flames` key; dependency list; UI tree, content JSON fields, component-level architecture nodes, fonts, extra test IDs, `ScoreBar`; CF-11 and CF-13 Mermaid blocks; OI-06 seed coverage. | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 12 |
| 2026-11-14 | API contract change: `scenario_id` is now the URL-safe base64 (no padding) of the canonical JSON of the resolved scenario, decoded statelessly by `POST /extract/export` (was a one-way SHA-1 needing a process-local store). Harvest `review` stage calls `EarthAppsAgent` and writes `/data/raw/<acronym>/earth_candidates.json` for curation (never the database). | 03, 05, 06, 07, 08, 09 |
| 2026-11-14 | DC-40: legacy binary `.doc`, `.ppt`, `.xls` are harvested but not parsed (reported `unsupported`). DC-42: `@vitest/coverage-v8` added; `npm test` enforces 80% lines over UI `lib/`. Prompt 03 code fixes: path parameter `{id}` on `/investigations/{id}` routes; citation markers bind to the preceding sentence; coverage chips carry an icon per state. | 02, 06, 12 |
| 2026-11-14 | DC-39: the gateway caches only valid replies (schema-valid for an output-model `output_schema`, non-empty for plain text), so a schema retry always reaches the model. DC-41: a half-open stated range keeps its null endpoint in `varied_parameters` and is open on the missing side for distance and gap coverage; catalog ranges widen only by known endpoints. DC-43: unit tests `test_catalog_service.py`, `test_safety_tech_gaps.py`, `test_meta_service.py`, `test_earth_service.py` added to the api list. DC-44: fuel distance is unset (removed) when the scenario gives no fuel. `insight_qa` prompt bumped to `insight_qa@2` (`{{validation_feedback}}` added). | 06, 07, 08, 12 |
| 2026-11-14 | `API_INTERNAL_URL` is a build argument of `Dockerfile.ui` (Next.js fixes rewrites at build time); runtime value applies to `npm run dev` only. | 11 |
| 2026-11-14 | Prompt 05 conflicts resolved: re-index after an embedding change is `... run --rm ingest index --force` (doc 11 section 5); `pytest-html` added so test targets write JUnit XML and HTML reports to `tests/reports/` (doc 02 section 3, doc 12 section 5). | 02, 11 |
| 2026-11-14 | DC-45: no gravity bounds or statement within 0.02 g of 0 or 1. DC-46: a null endpoint of a half-open range stays null in the derived investigation columns, `InvestigationSummary` ranges and compare range rows (open, shown as a bound), range filters treat it as open, `/meta/stats` ranges are the union (open when any range is open on that side). DC-47: the mock embedding hashes content words only (English stop words dropped); `MIN_VECTOR_SIMILARITY` per embedding provider (mock 0.2, ollama 0.5, calibrated for `nomic-embed-text`). DC-48: the Ollama provider sends `think: false` on chat calls. | 04, 05, 06, 07, 08 |
| 2026-11-14 | Prompt 07 conflicts resolved: CF-11 coverage scatter uses `limit 1000` (the `POST /extract/preview` maximum; doc 09 and `cf-11.mmd`); `--text-faint` lightened to `#8391A7` to meet 4.5:1 on every surface (doc 10 section 2.1); detail-page source links open a new tab, the evidence drawer stays on `/ranking` (doc 12 section 3). | 09, 10, 12 |
| 2026-11-14 | Prompt 08 pitch deck: owner constraint (Space Apps Global Award eligibility) of at most 7 slides and a public demo link overrides the 13-slide plan; `docs/decks/flamescope-pitch.pptx` has exactly 7 slides and no backups. `python-pptx` added as the optional extra `docs` (doc 02 section 3, Decks row); the deck build and verification scripts in `docs/decks/` are the one exception to "nothing executable outside `src/`, `tests/`, `deploy/`" (doc 02 section 4); deck screenshots are live captures in `docs/decks/screens/`. | 02 |
