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
| 400 | `bad_request` | Semantically invalid input (for example fewer than 2 IDs to compare). |
| 404 | `not_found` | Unknown investigation or resource. |
| 422 | `validation_error` | Schema validation failure; `details` lists fields. |
| 502 | `llm_unavailable` | LLM provider failed after retries. Deterministic part of the response is still returned where the endpoint says so. |
| 500 | `internal_error` | Anything else. |

## 3. Health and meta

| Method | Path | Response |
|--------|------|----------|
| GET | `/health` | `{"status":"ok"}` always when the process is up. |
| GET | `/ready` | `{"status":"ready","db":true,"migrations":"0001_initial","investigations":24}`; HTTP 503 if the database is unreachable, migrations missing, or zero investigations. |
| GET | `/meta/stats` | `{"investigations":n,"test_runs":n,"publications":n,"findings":n,"chunks":n,"hardware":n,"fuel_phase_counts":{"gas":n,"liquid":n,"solid":n},"o2_range":[min,max],"pressure_range_kpa":[min,max],"rubric_version":"...","last_ingest":"iso8601","ingest_mode":"seed|harvest"}` |
| GET | `/meta/status` | Component status for the Architecture page: `{"components":[{"id":"C-API","status":"up","detail":"..."},{"id":"C-DB",...},{"id":"C-LLM","status":"up|mock|down","provider":"ollama","model":"qwen2.5:0.5b"},{"id":"C-ING","status":"idle","last_run":{...}}]}` |
| GET | `/meta/rubric` | Rubric: lenses, criteria, default weights, descriptions, version. |
| GET | `/meta/presets` | Ranking presets and scenario presets (document 08). |

## 4. Catalog

### GET `/investigations`
Query: `q`, `fuel_phase` (repeatable), `material`, `hardware` (repeatable), `project`, `tag` (repeatable), `o2_min`, `o2_max`, `pressure_min_kpa`, `pressure_max_kpa`, `gravity_level`, `sort` (`acronym`, `overall`, `habitat`, `modeling`, `controls`; default `acronym`), `page`, `page_size`.

Item shape (`InvestigationSummary`):
```json
{"id": 7, "acronym": "BASS-II", "title": "...", "project": null, "platform": "ISS",
 "gravity_level": "microgravity", "fuel_phases": ["solid"], "hardware": ["MSG", "SPICE flow duct"],
 "summary": "...", "fire_safety_tags": ["flame_spread"],
 "o2_range": [0.14, 0.21], "pressure_range_kpa": [101.3, 101.3], "flow_range_cm_s": [1, 55],
 "scores": {"habitat": 78.0, "modeling": 64.0, "controls": 51.0, "overall": 66.0},
 "reviewed": true, "psi_url": "https://..."}
```

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
Lineage graph (FR-12): `{"nodes":[{"id":"hw:CIR","type":"hardware","label":"CIR","kind":"facility"},{"id":"inv:FLEX","type":"investigation","label":"FLEX"},{"id":"proj:ACME","type":"project","label":"ACME"}],"edges":[{"source":"inv:FLEX","target":"hw:MDCA","role":"apparatus"},{"source":"hw:MDCA","target":"hw:CIR","role":"hosted_in"}]}`

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
All fields optional except `lens`. Explicit weights override the preset, which overrides rubric defaults. Weights need not sum to 1; they are normalized.

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
Either a preset or explicit values; explicit values override the preset.

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
 "scenario_id": "sha1 of resolved scenario"}
```

## 8. Extract

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/extract/preview` | Request `{"filters": {"investigations": [], "fuel_phase": [], "o2_min": .., "o2_max": .., "pressure_min_kpa": .., "pressure_max_kpa": .., "has_outcome": ["flame_spread_rate_mm_s"], "scenario_id": null}, "columns": [...], "limit": 50}`. Response `{"columns":[{"name","label","unit","description"}],"rows":[[...]],"total":n}`. |
| POST | `/extract/export` | Same request plus `"format": "csv | json"`. Returns a file download (`text/csv` or `application/json`) with `Content-Disposition`. CSV has a commented header block with export time, filters and rubric version. |
| GET | `/extract/dictionary` | Data dictionary for all available columns. |

Default columns: `investigation`, `run_label`, `fuel_name`, `fuel_phase`, `shape`, `characteristic_dimension_mm`, `o2_fraction`, `diluent`, `pressure_kpa`, `flow_speed_cm_s`, `flow_direction`, `gravity_g`, `ignited`, `flame_spread_rate_mm_s`, `extinction`, `is_aggregate`, `confidence`, `source_uri`, `source_locator`.

## 9. Insights and Earth applications

| Method | Path | Response |
|--------|------|----------|
| GET | `/insights/safety-tech` | `{"groups":[{"category":"detection","label":"Detection","findings":[{"id":..,"statement":"..","investigation":"SAME","source":{..},"confidence":0.8}],"investigations":["SAME","SAME-R"]}]}` |
| GET | `/insights/gaps` | `{"gaps":[{"id":"partial_gravity","title":"No partial-gravity data","detail":"..","related":["E-FIELD Flames"],"future":["LUCI","FM2"]}]}` including computed parameter-space gaps (oxygen and pressure bins with no runs). |
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

The `citations` event carries the verified final answer; the UI replaces the streamed draft with it. If retrieval returns nothing above the threshold, the answer is the fixed sentence "The curated PSI corpus does not contain enough information to answer that." with no citations.

## 11. Endpoint inventory (for tests)

`GET /health`, `GET /ready`, `GET /meta/stats`, `GET /meta/status`, `GET /meta/rubric`, `GET /meta/presets`, `GET /investigations`, `GET /investigations/{id}`, `GET /investigations/{id}/runs`, `GET /investigations/{id}/variables`, `GET /investigations/{id}/publications`, `GET /facets`, `GET /hardware`, `GET /projects`, `POST /rank`, `POST /compare`, `POST /scenario`, `POST /extract/preview`, `POST /extract/export`, `GET /extract/dictionary`, `GET /insights/safety-tech`, `GET /insights/gaps`, `GET /earth-applications`, `POST /ask`.

24 endpoints. Every one must have at least one integration test (document 12).
