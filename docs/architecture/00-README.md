# FlameScope Architecture - Index

FlameScope is an AI-powered web dashboard that summarizes, ranks and interprets the combustion investigations in NASA's Physical Sciences Informatics (PSI) repository to deliver fire-safety insights. It is the entry for the NASA Space Apps Challenge 2026 challenge "Flame in Freefall".

These documents are the single source of truth for the build. Code, tests, containers and decks must follow them. Where code and documents disagree, the documents win until they are changed deliberately (see `13-traceability-and-conformance.md`).

## Reading order

| # | Document | What it settles |
|---|----------|-----------------|
| 01 | `01-requirements-and-scope.md` | Challenge objectives, requirement IDs, scope, open items |
| 02 | `02-system-architecture.md` | Context, layers, technology choices, repository layout, decisions |
| 03 | `03-component-design.md` | Every component: responsibility, modules, interfaces, dependencies |
| 04 | `04-data-model.md` | Tables, columns, JSON shapes, the investigation card schema |
| 05 | `05-api-specification.md` | Every REST and SSE endpoint with request and response shapes |
| 06 | `06-ingestion-pipeline.md` | Seed and harvest modes, stages, artifacts, idempotency |
| 07 | `07-agents-and-llm.md` | Agents, runtime prompt files, LLM gateway, mock provider, guardrails |
| 08 | `08-scoring-and-scenario.md` | Rubric, formulas, presets, scenario matching, gravity bounding |
| 09 | `09-call-flows.md` | Sequence diagrams for every user and system flow |
| 10 | `10-ui-architecture.md` | Next.js routes, dark design system, components, architecture page |
| 11 | `11-deployment-and-operations.md` | Containers, compose, Makefile targets, configuration, Helm option |
| 12 | `12-testing-strategy.md` | Unit, integration, end-to-end; build and deploy verification |
| 13 | `13-traceability-and-conformance.md` | Requirement to component to test mapping; change rules |

Diagrams: `../design-diagrams/flamescope-architecture-v2.drawio` (13 tabs). The Markdown files are authoritative; the draw.io file is the visual companion and is also the source for the in-app Architecture page.

## Conventions used in these documents

- **Requirement IDs**: `FR-nn` functional, `NFR-nn` non-functional (document 01).
- **Component IDs**: `C-xxx` (document 03). **Call flow IDs**: `CF-nn` (document 09). **Decision IDs**: `ADR-nn` (document 02). **Open items**: `OI-nn` (document 01).
- **Must / must not** are binding. **Should** is the default unless a recorded reason exists.
- All source code lives under `src/`. All build prompts live under `prompts/`. All architecture lives under `docs/`.
- "Runtime prompts" are the prompt files the application's own agents load (`src/agents/flamescope_agents/prompts/`). "Build prompts" are the numbered files in `prompts/` used to generate the project. They are different things.

## One-paragraph architecture

A Next.js dark-theme UI calls a FastAPI service over REST and Server-Sent Events. The API reads a PostgreSQL database (with pgvector) that holds curated "investigation cards", test runs, relevance scores and document chunks. That database is filled by an offline ingestion pipeline that either loads curated seed files (deterministic, offline) or harvests the public `nasa-psi` S3 bucket and uses LLM agents to extract and score. LLM calls at request time are limited to three places: cited question answering, comparison narratives and scenario explanations. Ranking, matching and export are deterministic Python. Everything runs on a Mac with Docker through one Makefile.
