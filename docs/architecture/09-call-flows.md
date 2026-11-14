# 09 - Call Flows

Participants use the component names of document 03. Every flow lists its endpoint(s), whether an LLM is involved, and failure behaviour. Mermaid sources for the UI Architecture page are copied from here into `src/ui/content/architecture/flows/`.

## CF-01 Build and deploy bring-up

```mermaid
sequenceDiagram
  actor Dev as Developer (Mac)
  participant Make as Makefile
  participant DC as Docker Compose
  participant DB as db
  participant ING as ingest
  participant API as api
  participant UI as ui
  Dev->>Make: make build
  Make->>DC: compose build api ingest ui
  Dev->>Make: make deploy
  Make->>DC: compose up -d db
  DC->>DB: start, healthcheck pg_isready
  Make->>DC: compose run --rm ingest
  ING->>DB: alembic upgrade head
  ING->>DB: seed (normalize, link, score, index, review)
  ING-->>Make: exit 0 + report
  Make->>DC: compose up -d api ui
  API->>DB: readiness query
  Make->>API: wait for GET /api/v1/ready = 200
  Make->>UI: wait for GET / = 200
  Make-->>Dev: URLs printed
```

Failure: any non-zero exit stops `make deploy` and prints `make logs` hint. `make undeploy` runs `compose down -v --remove-orphans`.

## CF-02 Seed ingestion of one investigation

```mermaid
sequenceDiagram
  participant CLI as flamescope-ingest
  participant SEED as seed.py
  participant NORM as normalizer
  participant LINK as linker / loader
  participant SCORE as score_stage
  participant ORCH as AgentOrchestrator
  participant GW as LLMGateway
  participant EMB as embedder
  participant DB as PostgreSQL
  CLI->>SEED: load <acronym>.yaml + overrides
  SEED->>NORM: card (validated as InvestigationCard)
  NORM->>LINK: canonical card
  LINK->>DB: upsert project, hardware, investigation, fuels, runs, conditions, measurements, publications, findings
  CLI->>SCORE: score(acronym)
  alt scores present in seed
    SCORE->>DB: upsert relevance_score (origin seed)
  else missing
    SCORE->>ORCH: run("scorer", payload) per lens
    ORCH->>GW: ADK Runner runs scorer LlmAgent on gateway model
    GW-->>ORCH: values + evidence
    SCORE->>DB: upsert relevance_score (origin llm)
  end
  CLI->>EMB: index(acronym)
  EMB->>GW: embed(chunks)
  EMB->>DB: upsert chunks
  CLI->>DB: insert ingest_run report
```

## CF-03 Harvest ingestion of one investigation

```mermaid
sequenceDiagram
  participant CLI as flamescope-ingest
  participant DISC as discover
  participant S3 as s3://nasa-psi
  participant HARV as harvester
  participant RAW as /data/raw
  participant PARSE as parser
  participant EXT as extract_stage
  participant ORCH as AgentOrchestrator
  participant GW as LLMGateway
  participant REST as normalize, link, score, index
  participant DB as PostgreSQL
  CLI->>DISC: discover()
  DISC->>S3: list objects (unsigned)
  DISC->>RAW: manifest.json
  CLI->>HARV: harvest(acronym)
  HARV->>S3: get allowed documents
  HARV->>RAW: raw/*
  CLI->>PARSE: parse(acronym)
  PARSE->>RAW: parsed/*.json
  CLI->>EXT: extract(acronym)
  EXT->>ORCH: run("extractor", context pack)
  ORCH->>GW: ADK Runner runs extractor LlmAgent (output_schema InvestigationCard)
  GW-->>ORCH: draft card
  EXT->>EXT: verify quotes, apply overrides
  EXT->>RAW: card.draft.json
  CLI->>REST: continue as CF-02 from normalize
  REST->>DB: upserts
  CLI->>ORCH: review: run("earth_apps", findings)
  ORCH->>GW: ADK Runner runs earth_apps LlmAgent on gateway model
  GW-->>ORCH: candidate Earth applications
  CLI->>RAW: earth_candidates.json (curator review before publishing)
```

## CF-04 Explorer: list and detail

Endpoints: `GET /investigations`, `GET /facets`, `GET /investigations/{id}`, `GET /investigations/{id}/runs`, `GET /investigations/{id}/variables`. LLM: none.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as API router
  participant CAT as CatalogService
  participant REPO as InvestigationRepo / RunRepo
  participant DB as PostgreSQL
  U->>UI: open /explorer, set filters
  par
    UI->>API: GET /investigations?fuel_phase=solid
    API->>CAT: list(filters, page)
    CAT->>REPO: search()
    REPO->>DB: SQL
    DB-->>REPO: rows + scores
    CAT-->>API: page of InvestigationSummary
  and
    UI->>API: GET /facets
    API->>CAT: facets()
  end
  API-->>UI: JSON
  U->>UI: click card
  UI->>API: GET /investigations/BASS-II
  API->>CAT: get("BASS-II")
  CAT-->>API: InvestigationDetail
  UI->>API: GET /investigations/BASS-II/runs, /variables
  API-->>UI: runs, varied vs fixed
```

## CF-05 Ranking

Endpoint: `POST /rank`. LLM: none.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as rank router
  participant RANK as RankingService
  participant SREPO as ScoreRepo
  participant RUB as Rubric / Presets
  U->>UI: choose preset or move weight sliders
  UI->>API: POST /rank {lens, preset, weights}
  API->>RANK: rank(...)
  RANK->>RUB: defaults + preset
  RANK->>SREPO: all_scores(filters)
  SREPO-->>RANK: criterion rows with evidence
  RANK->>RANK: aggregate(), sort
  RANK-->>API: ranked items + breakdown
  API-->>UI: JSON
  U->>UI: open evidence drawer
  UI->>UI: show rationale + SourceRef links (already in response)
```

The UI debounces slider changes (250 ms) and keeps previous data while refetching.

## CF-06 Compare

Endpoint: `POST /compare`. LLM: optional.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as compare router
  participant CMP as CompareService
  participant REPO as Repos
  participant ORCH as AgentOrchestrator
  participant GW as LLMGateway
  participant CV as CitationVerifier
  U->>UI: select 2-4 investigations
  UI->>API: POST /compare {investigations, narrative:false}
  API->>CMP: compare(ids, false)
  CMP->>REPO: cards, runs
  CMP->>CMP: diff_matrix()
  CMP-->>UI: matrix + shared (fast)
  UI->>API: POST /compare {investigations, narrative:true}
  API->>CMP: compare(ids, true)
  CMP->>ORCH: run("comparator", matrix + facts)
  ORCH->>GW: ADK Runner runs comparator LlmAgent on gateway model
  GW-->>ORCH: sentences with fact_ids
  CMP->>CV: verify(sentences, facts)
  CV-->>CMP: supported sentences
  CMP-->>UI: matrix + narrative
```

Failure: LLM error gives `narrative.status = "unavailable"`; UI shows the matrix and a muted notice.

## CF-07 Scenario Lab

Endpoint: `POST /scenario`. LLM: optional.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as scenario router
  participant SCN as ScenarioService
  participant RREPO as RunRepo
  participant ORCH as AgentOrchestrator
  participant CV as CitationVerifier
  U->>UI: pick preset "lunar_habitat", adjust sliders
  UI->>API: POST /scenario {.., explain:false}
  API->>SCN: match(scenario, false)
  SCN->>RREPO: condition_ranges(), query(runs)
  SCN->>SCN: distance(), coverage(), gravity_bounding()
  SCN-->>UI: matches + coverage + gravity_bounding
  U->>UI: click "Explain"
  UI->>API: POST /scenario {.., explain:true}
  SCN->>ORCH: run("scenario_interpreter", ...)
  ORCH-->>SCN: sentences + caveats
  SCN->>CV: verify
  SCN-->>UI: explanation
  U->>UI: "Export matching runs"
  UI->>API: POST /extract/export {filters:{scenario_id}, format:"csv"}
```

`scenario_id` is stateless: the URL-safe base64 encoding of the canonical scenario JSON (document 05 section 7). `ExtractService` decodes it to the scenario values and recomputes the matching runs, so no server-side registry is kept and the id survives restarts and multiple workers. Failure: an LLM error gives `explanation.status = "unavailable"`; a malformed `scenario_id` is HTTP 400 `bad_request`.

## CF-08 Data extract

Endpoints: `GET /extract/dictionary`, `POST /extract/preview`, `POST /extract/export`. LLM: none.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as extract router
  participant EXT as ExtractService
  participant RREPO as RunRepo
  U->>UI: open /extract
  UI->>API: GET /extract/dictionary
  U->>UI: set filters, choose columns
  UI->>API: POST /extract/preview
  API->>EXT: preview(query)
  EXT->>RREPO: query(filters)
  EXT->>EXT: build_table()
  EXT-->>UI: columns + first rows + total
  U->>UI: Export CSV
  UI->>API: POST /extract/export {format:"csv"}
  API-->>UI: file stream (provenance columns + header block)
```

## CF-09 Ask (cited question answering)

Endpoint: `POST /ask` (SSE). LLM: yes.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as ask router
  participant INS as InsightService
  participant GW as LLMGateway
  participant CREPO as ChunkRepo
  participant ORCH as AgentOrchestrator
  participant CV as CitationVerifier
  U->>UI: type question
  UI->>API: POST /ask (fetch + ReadableStream)
  API->>INS: ask(question, filters)
  INS->>GW: embed(question)
  par
    INS->>CREPO: keyword_search()
  and
    INS->>CREPO: vector_search()
  end
  INS->>INS: fuse_ranks(), add card facts
  INS-->>UI: event meta (retrieved sources)
  INS->>ORCH: run("insight_qa", stream=True)
  loop tokens
    ORCH-->>INS: text delta
    INS-->>UI: event token
  end
  INS->>CV: verify(draft, chunks)
  CV-->>INS: verified sentences, dropped count
  INS-->>UI: event citations (final answer)
  INS-->>UI: event related, event done
```

Failure: gateway error after `meta` produces `event: error`; the UI keeps the retrieved sources visible. No retrieval hits: fixed insufficient-information sentence, no LLM call.

## CF-10 Safety Tech, gaps and Earth applications

Endpoints: `GET /insights/safety-tech`, `GET /insights/gaps`, `GET /earth-applications`. LLM: none.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as insights / earth routers
  participant ST as SafetyTechService
  participant ES as EarthService
  participant REPO as Repos
  U->>UI: open /safety-tech
  UI->>API: GET /insights/safety-tech
  API->>ST: grouped()
  ST->>REPO: findings by category
  ST-->>UI: groups
  UI->>API: GET /insights/gaps
  ST-->>UI: partial-gravity gap + parameter gaps
  U->>UI: open /earth
  UI->>API: GET /earth-applications
  API->>ES: list()
  ES-->>UI: applications with linked investigations
```

## CF-11 Overview page

Endpoints: `GET /meta/stats`, `POST /rank` (lens `overall`, limit 5), `GET /insights/gaps`, `POST /extract/preview` (columns `o2_fraction`, `pressure_kpa`, `fuel_phase`, `investigation`; limit 1000 for the coverage scatter, the `POST /extract/preview` maximum). Requests run in parallel; each panel has its own loading and error state. LLM: none.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant API as meta / rank / insights / extract routers
  participant META as MetaService
  participant RANK as RankingService
  participant ST as SafetyTechService
  participant EXT as ExtractService
  U->>UI: open /
  par
    UI->>API: GET /meta/stats
    API->>META: stats()
  and
    UI->>API: POST /rank (lens overall, limit 5)
    API->>RANK: rank(...)
  and
    UI->>API: GET /insights/gaps
    API->>ST: gaps()
  and
    UI->>API: POST /extract/preview (4 columns, limit 1000)
    API->>EXT: preview(query)
  end
  API-->>UI: each panel renders its own loading, error and data state
```

## CF-12 Architecture page with live status

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Next.js UI
  participant CONTENT as content/architecture/*.json
  participant API as meta router
  participant META as MetaService
  U->>UI: open /architecture
  UI->>CONTENT: import diagram JSON (static)
  UI->>UI: render React Flow tabs
  loop every 10 s
    UI->>API: GET /meta/status
    API->>META: status()
    META-->>UI: component states
    UI->>UI: update node badges
  end
  U->>UI: click node
  UI->>UI: side panel: responsibility, interfaces, files, related flows
```

## CF-13 Undeploy

`make undeploy` -> `docker compose -p flamescope down -v --remove-orphans` -> containers, network and volumes removed. `make clean` additionally removes images and local caches. LLM: none.

```mermaid
sequenceDiagram
  actor Dev as Developer (Mac)
  participant Make as Makefile
  participant DC as Docker Compose
  Dev->>Make: make undeploy
  Make->>DC: compose -p flamescope down -v --remove-orphans
  DC-->>Make: containers, network and volumes removed
  Dev->>Make: make clean
  Make->>DC: undeploy, then remove images, .venv, node_modules and caches
```
