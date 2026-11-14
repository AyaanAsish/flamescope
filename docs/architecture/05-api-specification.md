# 05 - API Specification

Base path: `/api/v1`. JSON over HTTP; `POST /ask` responds with `text/event-stream`. OpenAPI at `/api/v1/openapi.json`, Swagger UI at `/api/v1/docs`. No authentication.

## 1. Conventions

- IDs in paths are the investigation **acronym** (URL-encoded), case-insensitive. Numeric IDs are also accepted.
- Pagination: `page` (default 1), `page_size` (default 24, max 100). List responses: `{"items": [...], "page": 1, "page_size": 24, "total": 24}`.
- Every response carries `X-Request-ID`.
- Numeric units: oxygen as fraction 0 to 1 (`o2_fraction`), pressure in kPa, flow in cm/s, gravity in g.
- `sources` arrays contain `SourceRef` objects (document 04).

## 2. Error envelope

```json
{"error": {"code": "not_found", "message": "Investigation 'XYZ' not found", "details": null, "request_id": "..."}}
```

| HTTP | code | When |
|------|------|------|
| 400 | `bad_request` | Semantically invalid input (for example fewer than 2 IDs to compare, an unknown preset or column, an invalid `scenario_id`). Raised by services as `flamescope_common.errors.ValidationError` (document 03 section 2). |
| 404 | `not_found` | Unknown investigation or resource (`NotFoundError`). |
| 422 | `validation_error` | Schema validation failure; `details` lists fields. Produced by the API from FastAPI request validation, not by a domain error. |
| 502 | `llm_unavailable` | LLM provider failed after retries. Deterministic part of the response is still returned where the endpoint says so. |
| 500 | `internal_error` | Anything else. |

## 3. Health and meta

| Method | Path | Response |
|--------|------|----------|
| GET | `/health` | `{"status":"ok"}` always when the process is up. |
| GET | `/ready` | `{"status":"ready","db":true,"migrations":"0001_initial","investigations":24}`; HTTP 503 if the database is unreachable, migrations missing, or zero investigations. The 503 body has the same fields with `"status":"not_ready"` (for example `{"status":"not_ready","db":false,"migrations":null,"investigations":0}`), not the error envelope. |
| GET | `/meta/stats` | `{"investigations":n,"test_runs":n,"publications":n,"findings":n,"chunks":n,"hardware":n,"fuel_phase_counts":{"gas":n,"liquid":n,"solid":n},"o2_range":[min,max],"pressure_range_kpa":[min,max],"rubric_version":"...","last_ingest":"iso8601","ingest_mode":"seed|harvest"}`; the ranges are the union of the investigation ranges (document 04 section 2): a side is null when any investigation's range is open on it, both are null without data |
| GET | `/meta/status` | Component status for the Architecture page: `{"components":[{"id":"C-API","status":"up","detail":"..."},{"id":"C-DB",...},{"id":"C-LLM","status":"up|mock|down","provider":"ollama","model":"qwen2.5:0.5b"},{"id":"C-ING","status":"idle","last_run":{...}}]}` |
| GET | `/meta/rubric` | The `Rubric` model loaded from `rubric.yaml` (document 08 section 1): `{"rubric_version":"2026.11-1","lens_weights":{"habitat":0.4,"modeling":0.3,"controls":0.3},"lenses":{"habitat":{"label":"Habitat relevance","description":"..","criteria":[{"id":"fuel_realism","label":"Fuel realism","weight":0.25,"description":"","anchors":{"0":"..","3":"..","5":".."}}]},"modeling":{..},"controls":{..}}}` |
| GET | `/meta/presets` | The `Presets` model loaded from `presets.yaml` (document 08 sections 3 and 4): `{"rubric_version":"2026.11-1","ranking":{"lunar_habitat":{"lens_weights":{"habitat":0.6,"modeling":0.2,"controls":0.2},"criterion_weights":{"habitat":{"atmosphere_match":0.35,..}}},..},"scenario":{"lunar_habitat":{"o2_fraction":0.34,"pressure_kpa":56.5,"pressure_psi":8.2,"gravity_g":0.166,"flow_speed_cm_s":10,"assumed_default":true,"note":".."},..},"texts":{"gravity_bounding":"The scenario gravity is {gravity_g} g. .."}}`. `criterion_weights` lists only the lenses a preset changes; `pressure_psi` may be null. |

## 4. Catalog

### GET `/investigations`
Query: `q`, `fuel_phase` (repeatable), `material`, `hardware` (repeatable), `project`, `tag` (repeatable), `o2_min`, `o2_max`, `pressure_min_kpa`, `pressure_max_kpa`, `gravity_level`, `sort` (`acronym`, `overall`, `habitat`, `modeling`, `controls`; default `acronym`), `page`, `page_size`.

Range filters keep investigations whose derived range (document 04 section 2) overlaps the requested bounds; a null endpoint is open on that side, so `o2_max=0.3` keeps an investigation stated as `[null, 0.85]`; investigations without data for the dimension are excluded.

Item shape (`InvestigationSummary`):
```json
{"id": 7, "acronym": "BASS-II", "title": "...", "project": null, "platform": "ISS",
 "gravity_level": "microgravity", "fuel_phases": ["solid"], "hardware": ["MSG", "SPICE flow duct"],
 "summary": "...", "fire_safety_tags": ["flame_spread"],
 "o2_range": [0.14, 0.21], "pressure_range_kpa": [101.3, 101.3], "flow_range_cm_s": [1, 55],
 "scores": {"habitat": 78.0, "modeling": 64.0, "controls": 51.0, "overall": 66.0},
 "reviewed": true, "psi_url": "https://..."}
```
`o2_range`, `pressure_range_kpa` and `flow_range_cm_s` are `[min, max]` from the derived columns; one element is null for a half-open stated range (open on that side, for example `[null, 0.85]`), and the field is null when both are unknown.

### GET `/investigations/{id}`
`InvestigationDetail` = summary plus `card` (full `InvestigationCard`), `publications`, `measurements`, `findings`, `score_breakdown` (same shape as in section 5), `run_count`, `data` (`s3_prefix`, `volume_bytes`, `file_types`).

### GET `/investigations/{id}/runs`
Query: `page`, `page_size`. Items: `{"id":..,"label":"..","fuel":{"name":"PMMA","phase":"solid"},"geometry":{..},"condition":{"o2_fraction":..,"pressure_kpa":..,"flow_speed_cm_s":..,"flow_direction":"..","gravity_g":0},"outcome":{..},"is_aggregate":false,"source":{..},"confidence":0.8}`

### GET `/investigations/{id}/variables`
`{"varied":[{"name":"o2_fraction","values":[0.14,0.17,0.21],"unit":"fraction"}],"fixed":[{"name":"pressure_kpa","value":101.3,"unit":"kPa"}],"run_count":12}` (FR-06).

### GET `/investigations/{id}/publications`
List of publications with `doi`, `title`, `authors`, `year`, `venue`, `url`, `key_findings`.

### GET `/facets`
`{"fuel_phase":[{"value":"solid","count":6}],"hardware":[...],"project":[...],"tag":[...],"platform":[...],"gravity_level":[...]}`

### GET `/hardware`
Lineage graph (FR-12): `{"nodes":[{"id":"hw:CIR","type":"hardware","label":"CIR","kind":"facility"},{"id":"inv:FLEX","type":"investigation","label":"FLEX"},{"id":"proj:ACME","type":"project","label":"ACME"}],"edges":[{"source":"inv:FLEX","target":"hw:MDCA","role":"apparatus"},{"source":"hw:MDCA","target":"hw:CIR","role":"hosted_in"},{"source":"inv:FLEX","target":"proj:ACME","role":"member_of"}]}`. Project membership is an edge from `inv:<acronym>` to `proj:<name>` with role `member_of`.

### GET `/projects`
`[{"name":"ACME","description":"...","investigations":["BRE","CFI-G","E-FIELD Flames", "..."]}]`

## 5. Ranking

### POST `/rank`
Request:
```json
{"lens": "habitat | modeling | controls | overall",
 "preset": "lunar_habitat",
 "criterion_weights": {"habitat": {"fuel_realism": 0.25}},
 "lens_weights": {"habitat": 0.4, "modeling": 0.3, "controls": 0.3},
 "filters": {"fuel_phase": ["solid"]},
 "limit": 24}
```
All fields optional except `lens`. Explicit weights override the preset, which overrides rubric defaults. Weights need not sum to 1; they are normalized. `limit` truncates the ranked list after ranking (ranks stay 1..n of the full ordering).

Response:
```json
{"lens": "habitat", "rubric_version": "2026.11-1", "weights_used": {...},
 "items": [{"rank": 1, "acronym": "BASS-II", "title": "...", "score": 78.0, "confidence": 0.85,
            "lens_scores": {"habitat": 78.0, "modeling": 64.0, "controls": 51.0},
            "breakdown": [{"criterion": "fuel_realism", "label": "Fuel realism", "value": 5, "weight": 0.25,
                           "contribution": 25.0, "rationale": "...", "evidence": [{...SourceRef}], "origin": "llm"}]}],
 "disclaimer": "Scores are relative decision aids, not safety certifications."}
```

No LLM call. Deterministic for identical input.

## 6. Compare

### POST `/compare`
Request: `{"investigations": ["BASS-II","FLEX-2","SPICE"], "narrative": true}` (2 to 4 IDs).

Response:
```json
{"investigations": [InvestigationSummary, ...],
 "matrix": [{"attribute": "fuel_phase", "label": "Fuel phase", "group": "fuel",
             "values": {"BASS-II": ["solid"], "FLEX-2": ["liquid"]}, "same": false}],
 "shared": {"hardware": ["MSG"], "tags": ["extinction"], "instruments": []},
 "narrative": {"text": "...", "sentences": [{"text": "...", "citations": [{...SourceRef}]}], "status": "ok | unavailable | skipped"}}
```
Attributes in the matrix, in order: `project`, `platform`, `gravity_level`, `hardware`, `fuel_phase`, `fuel_materials`, `geometry`, `o2_range`, `pressure_range_kpa`, `flow_range_cm_s`, `flow_direction`, `varied_parameters`, `measurements`, `phenomena` (tags), `data_volume`.

Range attribute values are `[min, max]` from the card's stated ranges with the section 4 null rule (a null end is open).

If the LLM fails, HTTP is still 200 with `narrative.status = "unavailable"`.

## 7. Scenario

### POST `/scenario`
Request:
```json
{"preset": "lunar_habitat",
 "o2_fraction": 0.34, "pressure_kpa": 56.5, "gravity_g": 0.166, "flow_speed_cm_s": 10,
 "fuel_phase": "solid", "material": "PMMA",
 "weights": {"o2": 0.35, "pressure": 0.25, "flow": 0.15, "fuel": 0.25},
 "explain": true, "limit": 10}
```
Either a preset or explicit values; explicit values override the preset. The resolved `scenario` carries `assumed_default` (true only for an unedited preset marked so in `presets.yaml`, document 08 section 4.1). An unknown preset, or neither a preset nor any value, is HTTP 400 `bad_request`. When the scenario sets no distance dimension (only `gravity_g`), `matches` is empty. The explanation is requested only when `explain` is true and there is at least one match; its sentences are the verified, cited agent sentences followed by deterministic, uncited caveats (document 08 section 4.4).

Response:
```json
{"scenario": {...resolved values...},
 "coverage": {"o2_fraction": {"state": "covered", "catalog_range": [0.1, 0.85]},
              "pressure_kpa": {"state": "extrapolated", "catalog_range": [70, 101.3]},
              "flow_speed_cm_s": {"state": "covered", "catalog_range": [0, 60]},
              "gravity_g": {"state": "no_data", "catalog_values": [0, 1]}},
 "matches": [{"acronym": "BASS-II", "similarity": 0.81, "best_run": {...run...}, "median_similarity": 0.62,
              "per_dimension": {"o2": 0.9, "pressure": 0.4, "flow": 0.95, "fuel": 1.0}, "matching_runs": 7}],
 "gravity_bounding": {"partial_gravity_data": false,
                      "lower_bound": {"gravity_g": 0, "investigations": ["BASS-II"]},
                      "upper_bound": {"gravity_g": 1, "investigations": []},
                      "analogue": {"acronym": "E-FIELD Flames", "note": "..."},
                      "statement": "No partial-gravity combustion data exists in PSI ..."},
 "explanation": {"text": "...", "sentences": [...], "status": "ok | unavailable | skipped"},
 "scenario_id": "eyJhc3N1bWVkX2RlZmF1bHQiOnRydWUs..."}
```

`scenario_id` is stateless and invertible: the URL-safe base64 encoding without `=` padding of the canonical JSON of the resolved `scenario` object (all its fields including `preset`, `weights` and `assumed_default`; keys sorted, compact separators `,` and `:`). The server keeps no scenario store; `POST /extract/*` decodes the id back into the resolved scenario (section 8), so the id stays valid across restarts and workers.

## 8. Extract

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/extract/preview` | Request `{"filters": {"investigations": [], "fuel_phase": [], "o2_min": .., "o2_max": .., "pressure_min_kpa": .., "pressure_max_kpa": .., "has_outcome": ["flame_spread_rate_mm_s"], "scenario_id": null}, "columns": [...], "limit": 50}`. Response `{"columns":[{"name","label","unit","description"}],"rows":[[...]],"total":n}`. |
| POST | `/extract/export` | Same request plus `"format": "csv | json"`. Returns a file download (`text/csv` or `application/json`) with `Content-Disposition`. CSV has a commented header block with export time, filters and rubric version. |
| GET | `/extract/dictionary` | Data dictionary for all available columns: `{"columns":[{"name":"o2_fraction","label":"Oxygen fraction","unit":"fraction","description":"Oxygen mole fraction, 0 to 1."}]}` (`unit` is null for unitless columns). |

Default columns: `investigation`, `run_label`, `fuel_name`, `fuel_phase`, `shape`, `characteristic_dimension_mm`, `o2_fraction`, `diluent`, `pressure_kpa`, `flow_speed_cm_s`, `flow_direction`, `gravity_g`, `ignited`, `flame_spread_rate_mm_s`, `extinction`, `is_aggregate`, `confidence`, `source_uri`, `source_locator`. `columns` omitted or empty means the default columns; an unknown column name is HTTP 400 `bad_request`.

- `characteristic_dimension_mm` is the first stated dimension in the run's `geometry.dimensions_mm`, or null.
- `limit` (default 50, at most 1000) bounds the preview rows only; `total` counts every matching run. `POST /extract/export` returns every matching run.
- `filters.scenario_id` is the `scenario_id` returned by `POST /scenario` (section 7). The service decodes it into the resolved scenario and keeps only runs with similarity >= 0.6 to it (document 08 section 4.2, `matching_runs`), after the other filters. An id that is not valid unpadded URL-safe base64 of a resolved-scenario JSON object is HTTP 400 `bad_request`.

## 9. Insights and Earth applications

| Method | Path | Response |
|--------|------|----------|
| GET | `/insights/safety-tech` | `{"groups":[{"category":"detection","label":"Detection","findings":[{"id":..,"statement":"..","investigation":"SAME","source":{..},"confidence":0.8}],"investigations":["SAME","SAME-R"]}]}`. Always all six finding categories, in the order `detection`, `suppression`, `material_screening`, `post_fire`, `atmosphere_design`, `fundamental`; a category without findings has empty `findings` and `investigations`. |
| GET | `/insights/gaps` | `{"gaps":[{"id":"partial_gravity","title":"No partial-gravity data","detail":"..","related":["E-FIELD Flames"],"future":["LUCI","FM2"]}]}` including computed parameter-space gaps (oxygen and pressure bins with no runs). The `partial_gravity` gap is present only while no run has a gravity strictly between 0 g and 1 g (more than 0.02 g from either). Parameter-space gaps follow it: one item per 4-connected region of uncovered grid cells (document 08 section 5), id `param_gap_<n>` numbered in output order, title "Untested oxygen and pressure region", the region's bounding box (oxygen and pressure ranges) and cell count in `detail`, empty `related` and `future`; regions that intersect the lunar-habitat envelope come first, then larger regions. |
| GET | `/earth-applications` | Query `sector`. `{"items":[{"id":..,"title":"Fine water mist extinguishers","sector":"firefighting","description":"..","maturity":"..","investigations":["..."],"findings":[..],"references":[{..}]}]}` |

## 10. Ask (SSE)

### POST `/ask`
Request: `{"question": "Which experiments tested solids above 30% oxygen?", "filters": {"investigations": []}, "top_k": 8}`

Response: `text/event-stream`. Events in order:

| event | data |
|-------|------|
| `meta` | `{"request_id":"..","retrieved":[{"chunk_id":1,"acronym":"..","doc_title":"..","score":0.71}]}` |
| `token` | `{"text":"partial text"}` (many) |
| `citations` | `{"sentences":[{"text":"..","citations":[{...SourceRef}],"supported":true}],"dropped":1}` |
| `related` | `{"investigations":["BASS-II","CFI-G"]}` |
| `done` | `{"status":"ok"}` |
| `error` | `{"code":"llm_unavailable","message":".."}` (terminal) |

The `citations` event carries the verified final answer; the UI replaces the streamed draft with it. Retrieval fuses keyword and vector hits by reciprocal rank fusion (constant 60) and keeps the best `top_k` (default 8). Every keyword match counts; a vector hit counts only with cosine similarity at or above `MIN_VECTOR_SIMILARITY` of the embedding provider (`EMBED_PROVIDER`, constants in `services/insight.py`): 0.2 for `mock` (content-word hashing, document 07 section 6) and 0.5 for `ollama`. The `ollama` value is calibrated for `nomic-embed-text` against the 28 seed chunks: the best chunk for eight corpus questions (flame spread, BASS, droplets and cool flames, reduced pressure, smoke detection, electric fields, FLEX fuels, flow and extinction) scored 0.60 to 0.76 and their eighth-best 0.52 to 0.68, while the best chunk for eight off-corpus questions ("What is the capital of France?", sourdough bread, football, guitar, spiders, Hamlet, bitcoin, car tyres) scored 0.38 to 0.47 (measured 2026-11). A different `EMBED_MODEL` needs a new calibration. If retrieval returns nothing above the threshold, the answer is the fixed sentence "The curated PSI corpus does not contain enough information to answer that." with no citations.

## 11. Endpoint inventory (for tests)

`GET /health`, `GET /ready`, `GET /meta/stats`, `GET /meta/status`, `GET /meta/rubric`, `GET /meta/presets`, `GET /investigations`, `GET /investigations/{id}`, `GET /investigations/{id}/runs`, `GET /investigations/{id}/variables`, `GET /investigations/{id}/publications`, `GET /facets`, `GET /hardware`, `GET /projects`, `POST /rank`, `POST /compare`, `POST /scenario`, `POST /extract/preview`, `POST /extract/export`, `GET /extract/dictionary`, `GET /insights/safety-tech`, `GET /insights/gaps`, `GET /earth-applications`, `POST /ask`.

24 endpoints. Every one must have at least one integration test (document 12).
