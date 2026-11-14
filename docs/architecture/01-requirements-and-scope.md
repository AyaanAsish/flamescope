# 01 - Requirements and Scope

## 1. Challenge statement (source: Space Apps 2026 "Flame in Freefall" video and considerations)

Build an AI-powered, web-based dashboard that summarizes, ranks and interprets the results of combustion investigations in PSI to deliver fire-safety insights. The tool should enable users to:

1. **O1** - Identify the investigations most relevant to the fire-safety needs of habitable crew environments.
2. **O2** - Extract data that supports predictive modeling of flammability and fire scenarios in space exploration.
3. **O3** - Highlight research that informs the development of next-generation fire-safety controls and equipment.
4. **O4 (add-on)** - Show potential applications of the PSI data to fire safety on Earth (for example fine water mist extinguishers, smoke detection, firefighter gear).

Data source: PSI Combustion Science area, stated in the challenge video as 24 investigations and about 12 TB. Each investigation has an overview (objectives, approach), data folders per sample or test, science documents, and publications with DOIs. A public S3 bucket `nasa-psi` (region `us-west-2`) fronts the data.

## 2. Users

| Persona | Goal | Primary views |
|---------|------|---------------|
| Professor / student | Understand and compare investigations | Explorer, Compare, Ask |
| Aerospace researcher / modeler | Find quantitative data for models | Ranking (modeling lens), Data Extract |
| Habitat / spacecraft fire-safety engineer | Decide which evidence applies to a design atmosphere | Scenario Lab, Ranking (habitat lens), Safety Tech |
| Earth fire-safety practitioner | See spin-offs | Earth Apps |
| Hackathon judge | See the system and how it works | Overview, Architecture |

## 3. Functional requirements

| ID | Requirement | Objective |
|----|-------------|-----------|
| FR-01 | Catalog every PSI combustion investigation as an **investigation card**: objectives, fuels (phase, material, shape, size or burner), test conditions (oxygen fraction, pressure, flow speed, gravity), varied vs fixed parameters, sensors and measurement types, hardware, platform, publications, PSI links. | O1, O2 |
| FR-02 | Search and filter the catalog by text, fuel phase, material, hardware, project, oxygen range, pressure range, tags. | O1 |
| FR-03 | Rank investigations under three lenses (habitat relevance, modeling value, controls and equipment value) and an overall score. Show the per-criterion breakdown, the evidence for each criterion and a confidence value. | O1, O2, O3 |
| FR-04 | Let the user change lens and criterion weights and choose presets; re-rank without any LLM call. | O1 |
| FR-05 | Compare 2 to 4 investigations: attribute matrix marking same and different, shared hardware, and an optional cited narrative. | O1 |
| FR-06 | Within one investigation, show how its test runs differ and how they are the same (varied vs fixed parameters). | O2 |
| FR-07 | Scenario Lab: given oxygen %, pressure, gravity, airflow and fuel/material, return the closest test runs and investigations, per-dimension coverage (covered, extrapolated, no data) and a gravity-bounding statement. | O1, O2 |
| FR-08 | Data Extract: build a table of test runs with conditions and outcomes, with provenance columns, export as CSV and JSON, and provide a data dictionary. | O2 |
| FR-09 | Safety Tech: group findings by control type (detection, suppression, material screening, post-fire and cleanup, atmosphere design) with links to source investigations. | O3 |
| FR-10 | Earth Apps: list terrestrial applications linked to findings and investigations. | O4 |
| FR-11 | Ask: natural-language question answering over the curated corpus with streamed answers and inline citations to PSI pages, documents or DOIs. Unsupported claims are removed. | O1-O4 |
| FR-12 | Hardware lineage: show which investigations share hardware (CIR, MSG, MDCA, ACME insert, SPICE flow duct) and instruments (for example the smoke instrument used in SAME / SAME-R and reused in DAFT / DAFT-2). | O1, O3 |
| FR-13 | Architecture page in the UI: interactive, detailed architecture diagrams (context, layers, components, data flow, call flows, deployment) with live component status. | Demo |
| FR-14 | Overview page: headline counts, coverage map of the parameter space (oxygen vs pressure by fuel phase), top-ranked investigations, known data gaps. | O1 |
| FR-15 | Every score, extracted field and generated statement carries a source reference. The UI can open it. | All |
| FR-16 | Explicitly present the partial-gravity gap: PSI currently has no partial-gravity combustion data; show microgravity and normal-gravity evidence as bounds and name E-FIELD Flames as the analogue. | O1 |

## 4. Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | Runs on macOS with Docker (Docker Desktop or Colima), Apple Silicon and Intel, with Ollama installed natively for live LLM mode. One command each for build, deploy, undeploy. |
| NFR-02 | Works fully offline in **mock mode**: seed data plus a deterministic mock LLM and mock embeddings. Mock mode is the default for tests and a safe fallback for the demo. |
| NFR-03 | UI is dark theme only, professional, consistent design tokens, WCAG AA contrast, responsive from 1280 px upward, usable at 1024 px. |
| NFR-04 | Non-LLM API endpoints respond in under 300 ms p95 on the seed dataset on a laptop. |
| NFR-05 | Ingestion is idempotent and re-runnable per investigation; curator overrides always win over LLM output. |
| NFR-06 | No secrets in the repository. Configuration by environment variables with a committed `.env.example`. |
| NFR-07 | Agents are built on Google ADK. The LLM provider is swappable by configuration (`mock`, `ollama`) and the Ollama model by `LLM_MODEL` (default `qwen2.5:0.5b`). No provider-specific code outside the gateway. |
| NFR-08 | Tests cover build, deploy, every API endpoint, every UI route, and undeploy (document 12). |
| NFR-09 | Scores are decision aids, not safety certifications; the UI states this wherever scores appear. |
| NFR-10 | Raw PSI data (video, image stacks, large sensor files) is never bulk-downloaded; it is referenced by bucket key, size and type. |
| NFR-11 | Structured JSON logs; one request ID propagated UI to API to LLM gateway. |
| NFR-12 | Python 3.12, type-checked (mypy), linted (ruff). TypeScript strict mode, ESLint clean. |

## 5. Scope

**In scope**: PSI Combustion Science investigations; documents, overviews, publication metadata; tabular condition and outcome data where present in documents or small data files; the eleven UI routes in document 10.

**Out of scope**: processing video or image data; running combustion simulations; user accounts and authentication; write access to PSI; other PSI disciplines (the pipeline must not preclude them: discipline is a column).

## 6. Domain facts the system encodes (from the challenge text)

- The six ACME experiments burned gaseous fuels with one modular hardware set in the Combustion Integrated Rack (CIR). They include BRE (materials flammability in still atmospheres, emulated with gaseous fuel), CFI-G (highest oxygen concentrations: up to 85% oxygen from a spherical burner, inverse flame) and E-FIELD Flames (electric field on flame ions, mimics partial gravity).
- FLEX, FLEX-2 and CFI burned liquid fuel droplets in the Multi-user Droplet Combustion Apparatus (MDCA) in the CIR.
- BASS, BASS-II, SPICE and SLICE covered solid and gaseous fuels in the Microgravity Science Glovebox (MSG) using the fan-driven flow duct built for SPICE.
- SAME and SAME-R studied smoke; one of their instruments was reused for dust in DAFT and DAFT-2.
- Spacesuits use 100% oxygen at 4.3 psi; Earth sea level is 14.7 psi. Lunar habitats and rovers are expected at 30% oxygen or more and 10.2 psi or less, which makes materials more flammable.
- No partial-gravity combustion data is in PSI yet; LUCI and FM2 are expected to add it. Microgravity and normal-gravity results can bound intermediate gravity.

These are seed knowledge for the linker and the presets; the pipeline must confirm each against PSI sources and attach references.

## 7. Open items

| ID | Open item | Default until resolved |
|----|-----------|------------------------|
| OI-01 | Exact key layout of `s3://nasa-psi/` and which prefixes hold Combustion Science. | `discover` stage lists the bucket and writes a manifest; prefix is configuration (`PSI_PREFIX`). |
| OI-02 | The authoritative list of the 24 investigations and their acronyms. | Seed files cover the investigations named in section 6; `discover` adds the rest and flags cards as `reviewed=false`. |
| OI-03 | How much quantitative run-level data is available in small files versus only in papers. | Extract ranges and qualitative outcomes; mark numeric fields null when absent. |
| OI-04 | Which LLM will be used at the event. | Resolved 2026-11-12: Ollama running natively on the Mac, chat model `qwen2.5:0.5b`, embeddings `nomic-embed-text`, agents on Google ADK (ADR-11). Mock mode always available. Open: whether a larger `qwen2.5` variant is needed for harvest-mode extraction quality. |
| OI-05 | Embedding dimension. | `EMBED_DIM=768`; changing it requires a migration (document 04). |
| OI-06 | Content gap: the seed covers 14 of the 24 investigations (those named in section 6), all as stubs (`reviewed: false`, no `runs`, no `scores`), so Ranking, Scenario and Overview are sparse until a harvest or curation fills them. | Accepted under OI-02: missing scores are computed at seed time and unknown values stay `null`. Extend the seed files from PSI pages or DOIs once retrievable (document 06 section 5). |
