# 10 - UI Architecture (Next.js)

## 1. Stack

Next.js (App Router), React, TypeScript strict, Tailwind CSS, shadcn/ui (Radix primitives), TanStack Query, Zustand, Recharts, `@xyflow/react` (React Flow), Mermaid (client-side, for sequence diagrams), lucide-react icons, `next/font/local` with Inter and JetBrains Mono from the woff2 files of the `@fontsource-variable/inter` and `@fontsource-variable/jetbrains-mono` packages (no font download at build time, so offline and container builds work). Package manager: npm. Node 20 LTS or newer.

Location: `src/ui/`. Output mode `standalone` for the container image.

## 2. Design system - dark, professional

Dark theme only. `<html class="dark">`; no theme toggle.

### 2.1 Tokens (CSS variables in `app/globals.css`, mapped in `tailwind.config.ts`)

| Token | Value | Use |
|-------|-------|-----|
| `--bg` | `#0A0E14` | page background |
| `--surface-1` | `#10151D` | cards, panels |
| `--surface-2` | `#161C26` | raised elements, table header, hover |
| `--border` | `#232B38` | hairlines |
| `--border-strong` | `#334155` | focused / selected outlines |
| `--text` | `#E6EAF0` | primary text |
| `--text-muted` | `#94A3B8` | secondary text |
| `--text-faint` | `#8391A7` | captions, axis labels (at least 4.5:1 on `--bg`, `--surface-1` and `--surface-2`) |
| `--accent` | `#F97316` | primary action, flame orange |
| `--accent-soft` | `rgba(249,115,22,0.12)` | accent backgrounds |
| `--cool` | `#38BDF8` | secondary accent, microgravity blue |
| `--success` | `#34D399` | covered, up |
| `--warning` | `#FBBF24` | extrapolated, low confidence |
| `--danger` | `#F87171` | no data, down, errors |
| `--gas` / `--liquid` / `--solid` | `#38BDF8` / `#A78BFA` / `#F97316` | fuel-phase encoding, used consistently in every chart and badge |

Lens colours: habitat `#F97316`, modeling `#38BDF8`, controls `#34D399`.

Architecture page colours (section 6.3) are also variables in `app/globals.css`, the only place colour literals appear: `--kind-ui`, `--kind-api`, `--kind-services`, `--kind-agents` (`#A78BFA`), `--kind-data`, `--kind-ingestion` (`#FB7185`), `--kind-external` (node strips; the others reuse the tokens above), `--edge` (`#475569`) and `--edge-llm` (`#A78BFA`, request-time LLM edges).

### 2.2 Typography and spacing

- Inter for UI text; JetBrains Mono for numbers, IDs, units and code.
- Scale: 12, 13, 14 (body), 16, 20, 24, 32. Line height 1.5 body, 1.2 headings. Tabular numerals in tables.
- 4 px spacing grid; card padding 20 px; page gutter 24 px; max content width 1440 px.
- Radius 10 px for cards, 6 px for inputs and badges. Borders 1 px; no drop shadows heavier than `0 1px 0 rgba(255,255,255,0.03) inset`.

### 2.3 Quality rules (binding)

1. No pure black or pure white; no gradients except a subtle accent glow on the Overview hero.
2. Text contrast at least 4.5:1; never encode meaning by colour alone (pair with icon or label).
3. Every data panel has four states: loading skeleton, empty, error with retry, data.
4. Numbers always carry units; oxygen shown as percent in the UI, converted from fraction.
5. Charts: dark grid lines `--border`, axis labels `--text-faint`, tooltips on `--surface-2`, no chart junk, legends clickable.
6. Motion: 150 ms ease-out for hover and panel transitions; respect `prefers-reduced-motion`.
7. Keyboard: all interactive elements focusable with visible focus ring (`--accent`); `/` focuses global search; `Esc` closes drawers.
8. The score disclaimer (NFR-09) appears in the Ranking and Scenario views and in the footer.

## 3. App structure

```
src/ui/
  app/
    layout.tsx                 # html.dark, fonts, providers
    globals.css
    (dashboard)/
      layout.tsx               # sidebar + top bar + footer
      page.tsx                 # Overview            /
      explorer/page.tsx        #                     /explorer
      investigations/[id]/page.tsx   #               /investigations/[id]
      ranking/page.tsx         #                     /ranking
      compare/page.tsx         #                     /compare
      scenario/page.tsx        #                     /scenario
      extract/page.tsx         #                     /extract
      safety-tech/page.tsx     #                     /safety-tech
      earth/page.tsx           #                     /earth
      ask/page.tsx             #                     /ask
      architecture/page.tsx    #                     /architecture
      _components/             # route-private view bodies and hooks (not routes)
    not-found.tsx, error.tsx
  components/
    ui/                        # shadcn primitives
    layout/                    # Sidebar, TopBar, Footer, PageHeader, Providers (TanStack Query provider)
    investigations/            # InvestigationCard, DetailTabs, DetailPanels, RunsTable, VariablesPanel, SourceLink, EvidenceDrawer
    ranking/                   # LensTabs, WeightSliders, PresetSelect, RankTable, ScoreBar (wraps charts/StackedScoreBar), weights.ts
    compare/                   # ComparePicker, DiffMatrix, NarrativePanel, LineageGraph
    scenario/                  # ScenarioForm, CoveragePanel, MatchList, GravityBoundingCard, scenario-values.ts
    extract/                   # QueryBuilder, PreviewTable, ColumnPicker, ExportButtons, extract-state.ts
    ask/                       # ChatPanel, MessageList, CitationChip, SourcesPanel, use-ask.ts
    architecture/              # ArchTabs, FlowCanvas, FlowViewer, NodeTypes, NodePanel, Legend, SequenceDiagram, StatusBadge, build-flow.ts
    charts/                    # ParameterSpaceScatter, ScoreRadar, StackedScoreBar, CoverageBars, Timeline, chart-style.ts
  content/architecture/        # context.json, layers.json, components.json, dataflow.json, datamodel.json, deployment.json, flows/*.mmd,
                               # index.ts (diagram exports and FLOWS metadata), types.ts (diagram types), load-flows.ts (server-side .mmd reader)
  lib/
    api/client.ts, types.ts, hooks.ts, sse.ts
    store.ts, format.ts (units), constants.ts, use-url-state.ts (URL-mirrored state), utils.ts (class names)
  public/                      # logo.svg, favicon, flamescope-architecture.drawio
  next.config.mjs              # output: 'standalone'; rewrites /api/:path* -> ${API_INTERNAL_URL}/api/:path*
  tailwind.config.ts, tsconfig.json, package.json, vitest.config.ts
```

## 4. Layout

- **Sidebar** (240 px, collapsible to 64 px): logo, then navigation in this order - Overview, Explorer, Ranking, Compare, Scenario Lab, Data Extract, Safety Tech, Earth Apps, Ask, Architecture. Active item has an accent bar and `--surface-2` background.
- **Top bar**: global search (navigates to Explorer with `q`), LLM mode badge (`mock`, or `ollama` with the model name, from `/meta/status`), dataset badge (`seed` / `harvest`, count), link to PSI.
- **Footer**: disclaimer, rubric version, data source credit "Data: NASA Physical Sciences Informatics (PSI)".

## 5. Routes

| Route | Purpose | Key components | API calls | `data-testid` roots |
|-------|---------|----------------|-----------|---------------------|
| `/` | Overview | Stat tiles, ParameterSpaceScatter (O2 % vs pressure, colour by fuel phase, lunar-habitat envelope shaded), top 5 overall, gaps card, quick links | CF-11 | `overview-stats`, `overview-scatter`, `overview-top`, `overview-gaps` |
| `/explorer` | Catalog | Facet filters, card grid, sort select | `/investigations`, `/facets` | `explorer-filters`, `investigation-card`, `explorer-q`, `explorer-sort` |
| `/investigations/[id]` | Detail | Header with badges and PSI link; tabs: Summary, Test runs, Variables, Measurements, Publications, Scores, Data | detail, runs, variables | `detail-header`, `detail-tabs`, `runs-table` |
| `/ranking` | Ranking | LensTabs, PresetSelect, WeightSliders, RankTable with StackedScoreBar, EvidenceDrawer | `/meta/rubric`, `/meta/presets`, `/rank` | `ranking-lens-tabs`, `ranking-weights`, `rank-row`, `evidence-drawer`, `ranking-preset` |
| `/compare` | Compare | ComparePicker (2-4), DiffMatrix with same/different highlighting, NarrativePanel, LineageGraph | `/compare`, `/hardware` | `compare-picker`, `diff-matrix`, `compare-narrative`, `lineage-graph`, `compare-add` |
| `/scenario` | Scenario Lab | ScenarioForm (preset, sliders with numeric inputs, unit toggle kPa/psi), CoveragePanel, GravityBoundingCard, MatchList, Explain button, export | `/meta/presets`, `/scenario`, `/extract/export` | `scenario-form`, `coverage-panel`, `gravity-bounding`, `scenario-match`, `scenario-preset`, `scenario-phase`, `scenario-material` |
| `/extract` | Data Extract | QueryBuilder, ColumnPicker, PreviewTable, ExportButtons, dictionary drawer | `/extract/*` | `extract-query`, `extract-preview`, `export-csv`, `export-json` |
| `/safety-tech` | Controls and equipment | Category columns with finding cards, linked investigations, gaps | `/insights/*` | `safety-group` |
| `/earth` | Earth applications | Sector filter, application cards with linked investigations | `/earth-applications` | `earth-card` |
| `/ask` | Cited Q&A | ChatPanel with streaming, CitationChip, SourcesPanel, suggested questions | `/ask` | `ask-input`, `ask-answer`, `citation-chip`, `ask-sources` |
| `/architecture` | Architecture | ArchTabs, FlowCanvas, NodePanel, SequenceDiagram, StatusBadge, download draw.io | `/meta/status` | `arch-tabs`, `arch-canvas`, `arch-node`, `arch-node-panel`, `arch-sequence` |

Control test IDs sit on the form controls that end-to-end tests drive, and equal the control's `id`: `explorer-q` (search input), `explorer-sort` (sort select), `ranking-preset` (PresetSelect), `compare-add` (ComparePicker add select), `scenario-preset`, `scenario-phase`, `scenario-material` (ScenarioForm).

URL state: filters, lens, preset, selected investigations and scenario values are mirrored in query parameters so every view is linkable.

## 6. Architecture page (FR-13) - detailed design

Purpose: show judges and engineers exactly how the system is built, inside the product.

### 6.1 Tabs

| Tab | Renderer | Content file | Shows |
|-----|----------|--------------|-------|
| System context | React Flow | `context.json` | Users, FlameScope, PSI, S3 bucket, DOI, LLM |
| Layers | React Flow | `layers.json` | Presentation, API, services, agents, data, ingestion as swimlane groups |
| Components | React Flow | `components.json` | Every component of document 03 with IDs, grouped by container |
| Data flow | React Flow | `dataflow.json` | Ingestion stages 1-9 and artifacts |
| Data model | React Flow (entity nodes) | `datamodel.json` | Tables and relations of document 04 |
| Call flows | Mermaid | `flows/cf-01.mmd` ... `cf-13.mmd` | Selector for each CF with its sequence diagram and notes |
| Deployment | React Flow | `deployment.json` | Containers, ports, volumes, Makefile targets |

### 6.2 Content JSON shape

```json
{"id": "components", "title": "Component view", "direction": "LR",
 "nodes": [{"id": "C-SVC", "type": "component", "group": "api", "position": {"x": 720, "y": 0},
            "width": 250, "height": 76,
            "data": {"label": "Domain services", "accent": "services", "subtitle": "C-SVC - services/",
                     "componentId": "C-SVC", "kind": "service",
                     "responsibility": "...", "interfaces": ["RankingService.rank(lens, weights, preset, filters) / breakdown(id)"],
                     "files": ["src/api/flamescope_api/services/ranking.py"],
                     "flows": ["CF-05", "CF-11"], "statusKey": "C-API", "doc": "03-component-design.md#5"}}],
 "groups": [{"id": "api", "label": "flamescope-api (FastAPI)", "color": "api"}],
 "edges": [{"id": "e2", "source": "C-API", "target": "C-SVC", "label": "calls one service", "animated": false,
            "sourceSide": "right", "targetSide": "left", "llm": false}]}
```

Fields beyond the minimal shape (all needed to check and render the layout rules):

| Field | Values | Meaning |
|-------|--------|---------|
| diagram `direction` | `LR`, `TB` | Main reading direction; default edge sides follow it. |
| node `width`, `height` | px | Node rectangle used for the overlap, gap and edge-path checks. |
| node `data.accent` | `ui`, `api`, `services`, `agents`, `data`, `ingestion`, `external` | Left colour strip (section 6.3). |
| node `data.subtitle` | text | Second line under the label. |
| node `data.columns` | list of text | Entity nodes only: table columns (document 04). |
| edge `sourceSide`, `targetSide` | `top`, `right`, `bottom`, `left` | Optional handle sides; default from `direction`. |
| edge `llm` | boolean, default false | Request-time LLM call: dashed violet edge. |

Groups keep the `{id, label, color}` shape; their boxes are computed from the member nodes (padding 24 px, 44 px at the top for the label chip), so group boxes never need hand-set positions.

The Components tab has one node per document 03 component ID (C-UI, C-API, C-SVC, C-REPO, C-ORCH, C-AGT, C-CV, C-LLM, C-COM, C-DB, C-RAW, C-ING) plus the external systems; node `id` equals the `componentId`. The services, repositories, agents and modules of a component are listed in that node's `interfaces` and `files` and shown in NodePanel, which keeps the left-to-right layout free of edges through nodes.

Positions are hand-set in the JSON so the layout is deliberate: left-to-right or top-to-bottom, orthogonal `smoothstep` edges, no edge crossing a node, minimum 40 px gap between nodes.

### 6.3 Node types and styling

- `actor`, `external`, `component`, `store`, `job`, `group`, `entity` custom nodes in `components/architecture/NodeTypes.tsx`.
- Node: `--surface-1` fill, 1 px `--border`, 10 px radius, title 13 px semibold, subtitle 12 px muted, left colour strip by kind (UI blue `--cool`, API green, services orange, agents violet `#A78BFA`, data amber, ingestion rose `#FB7185`, external slate).
- Groups: dashed `--border-strong` outline with label chip.
- Edges: 1.5 px `#475569` (`--edge`), arrowhead, label on `--bg` chip; edges for request-time LLM calls are dashed violet.
- StatusBadge on nodes with a `statusKey`: green dot up, amber dot `mock` or idle, red dot down.
- Controls: zoom, fit view, minimap (dark), legend panel, "Download draw.io" button linking to `/flamescope-architecture.drawio`.

### 6.4 Interaction

- Click a node: NodePanel slides in from the right with responsibility, interfaces, source files, related call flows (links switch to the Call flows tab) and the document reference.
- Hover: highlights connected edges and neighbours; others dim to 35% opacity.
- Call flows tab: left list of CF-01..CF-13 with title and "LLM: none / optional / yes" chip; right pane renders the Mermaid diagram with the dark theme (`theme: 'base'` with token variables) and the flow's failure notes.

### 6.5 Conformance

`content/architecture/index.ts` exports all diagrams, the list of flow files and the `FLOWS` metadata (title, LLM usage, endpoints, failure notes, document anchor); `content/architecture/types.ts` holds the diagram types. The `.mmd` files are plain text read on the server by `content/architecture/load-flows.ts` (the bundler has no raw-text imports) and passed to the Call flows tab as props; each is a verbatim copy of the Mermaid block of its section in document 09. A unit test asserts that every `componentId` in the JSON exists in the list of IDs from document 03 and that every CF file listed in document 09 exists.

## 7. Data fetching

- `lib/api/client.ts`: `apiGet`, `apiPost`, `apiDownload`; base path `/api/v1`; throws `ApiError` with the envelope fields.
- `lib/api/sse.ts`: `streamAsk(body, handlers)` using `fetch` and `ReadableStream`, parsing `event:` / `data:` frames.
- `lib/api/hooks.ts`: one TanStack Query hook per endpoint; query keys include all parameters; `staleTime` 5 minutes for catalog data, 0 for `/meta/status`.
- Types in `lib/api/types.ts` are a hand-maintained mirror of `flamescope_common.schemas.api`. The script `npm run gen:types` writes `lib/api/types.generated.ts` from the OpenAPI document as a reference for diffing against `types.ts` (it never overwrites `types.ts`; the generated file is excluded from ESLint).

## 8. Testing hooks

Every interactive or asserted element carries a `data-testid` from the table in section 5. End-to-end tests rely on them (document 12).
