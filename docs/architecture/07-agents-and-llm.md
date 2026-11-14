# 07 - Agents and LLM Layer

## 1. Principles

1. One agent, one job, one runtime prompt file, one input schema, one output schema.
2. Agents return JSON validated by Pydantic. The only streamed free text is the Insight QA answer, and it is post-verified.
3. Agents state only what their supplied context supports and attach a source to each statement. "Unknown" is a valid and preferred answer over a guess.
4. Agents have no tools and no database access. Services and stages prepare their context and persist their output.
5. Provider details live only in the gateway.
6. Agents are built on Google ADK (`google-adk`): each runtime agent is one ADK `LlmAgent` with no tools, run by the orchestrator through an ADK `Runner`.

## 2. Runtime prompt files

Location: `src/agents/flamescope_agents/prompts/`

| File | Agent | Version key |
|------|-------|-------------|
| `extractor.md` | ExtractorAgent | `extractor@1` |
| `scorer.md` | ScorerAgent | `scorer@1` |
| `comparator.md` | ComparatorAgent | `comparator@1` |
| `scenario_interpreter.md` | ScenarioInterpreterAgent | `scenario_interpreter@1` |
| `insight_qa.md` | InsightQAAgent | `insight_qa@1` |
| `earth_apps.md` | EarthAppsAgent | `earth_apps@1` |
| `shared/grounding_rules.md` | included by all | - |
| `shared/domain_primer.md` | included by all | - |

File format: YAML front matter (`name`, `version`, `output_schema`, `temperature`, `max_tokens`) followed by `## System` and `## User` sections. Variables use `{{name}}`. `{{> shared/grounding_rules.md}}` includes a shared file. `base.Agent` renders the file; no prompt text is embedded in Python.

`shared/grounding_rules.md` content (normative summary): use only the supplied context; cite by the given IDs; never invent numbers, names, DOIs or links; return null for unknowns; keep quotes verbatim and under 240 characters; output JSON only, matching the schema.

`shared/domain_primer.md`: short glossary - microgravity versus normal gravity, buoyancy, opposed and concurrent flow, flammability limits, oxygen fraction versus partial pressure, cool flames, hardware names (CIR, MSG, MDCA, ACME, SPICE duct), and the partial-gravity gap.

## 3. Agent contracts

### ExtractorAgent
- **Input**: `{acronym, title, psi_url, context:[{doc_id, title, section, text}]}`
- **Output**: `InvestigationCard` draft; every source uses `doc_id` and a verbatim `quote`.
- **Post-checks** (in `extract_stage.py`): quote is a substring of the cited text; units parse; vocabulary valid.

### ScorerAgent
- **Input**: `{acronym, lens, criteria:[{id, label, description, anchors:{0..5}}], card, excerpts:[{chunk_id, text}]}`
- **Output**: `{lens, scores:[{criterion, value:0-5|null, rationale, evidence:[{chunk_id|field_path, quote}]}]}`
- **Rule**: a non-null value requires at least one evidence item.

### ComparatorAgent
- **Input**: `{investigations:[summary + key card fields], matrix, shared, facts:[{id, text, source}]}`
- **Output**: `{sentences:[{text, fact_ids:[...]}]}` - 4 to 7 sentences covering what is common, what differs, and what the difference means for fire safety.

### ScenarioInterpreterAgent
- **Input**: `{scenario, coverage, matches (top 5 with runs), gravity_bounding, facts:[{id, text, source}]}`
- **Output**: `{sentences:[{text, fact_ids}], caveats:[text]}`. Must repeat the gravity-bounding statement when gravity is neither 0 nor 1, and must flag every `extrapolated` or `no_data` dimension.

### InsightQAAgent
- **Input**: `{question, chunks:[{chunk_id, acronym, doc_title, text}], card_facts:[{id, acronym, text}]}`
- **Output (streamed text)**: plain sentences, each ending with one or more citation markers `[c:123]` (chunk) or `[f:45]` (card fact). No Markdown headings.
- **Refusal**: when context is insufficient, output exactly the fixed sentence in document 05, section 10.

### EarthAppsAgent
- **Input**: `{findings:[{id, acronym, statement, category}], known_applications:[...]}`
- **Output**: `{applications:[{title, sector, description, finding_ids, confidence}]}`. Results are written with `reviewed=false` and shown only after curation, except entries from `earth_applications.yaml`.

## 4. Citation verifier

`CitationVerifier.verify(sentences, context) -> VerifiedAnswer`. Deterministic, no LLM:

1. Parse citation markers; a sentence without a marker is `unsupported`.
2. For each cited chunk or fact, compute support: every number in the sentence (with unit normalization) must appear in the cited text, and token overlap of content words must be at least 0.35 (configurable `VERIFY_MIN_OVERLAP`).
3. Unsupported sentences are dropped from the final answer; the count is returned as `dropped`.
4. If all sentences are dropped, the fixed insufficient-information sentence is returned.

## 5. Orchestrator

`AgentOrchestrator.run(name, payload, *, stream=False)`:
1. Resolve the agent; validate the payload against its input schema.
2. Render the prompt; compute the cache key.
3. Run the agent's ADK `LlmAgent` (model from `LLMGateway.model()`, `instruction` = rendered `## System`, user message = rendered `## User`, `output_schema` = output model for JSON agents) through an ADK `Runner` with an `InMemorySessionService`: one throwaway session per call, nothing persisted. Insight QA streams with `RunConfig(streaming_mode=StreamingMode.SSE)`.
4. Validate output; on schema failure, retry up to 2 times with the validation error appended.
5. Log `agent`, `prompt_version`, `provider`, `model`, `latency_ms`, `cache_hit`, `retries`.
6. Raise `LLMError` on final failure; callers decide the fallback (document 05).

## 6. LLM gateway, Google ADK and Ollama

Agents are Google ADK agents; the gateway supplies the model every ADK agent runs on, plus embeddings. ADK agent classes (`LlmAgent`, `Runner`, `InMemorySessionService`, `RunConfig`) are imported only in `flamescope_agents`; ADK model classes (`BaseLlm`, `LiteLlm`) and LiteLLM only in `flamescope_common/llm/`.

```python
class LLMProvider(Protocol):
    name: str
    def model(self) -> BaseLlm: ...                              # google.adk.models.BaseLlm
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class LLMGateway:
    def model(self) -> BaseLlm: ...                              # ADK model for LLM_PROVIDER
    def embed(self, texts: list[str]) -> list[list[float]]: ...  # EMBED_PROVIDER, batches of 64
    def callbacks(self) -> ModelCallbacks: ...                   # ADK before/after model callbacks
```

| Provider | Selection | Behaviour |
|----------|-----------|-----------|
| `mock` | `LLM_PROVIDER=mock` (tests, offline fallback) | `MockLlm` (subclass of ADK `BaseLlm`), deterministic, no network. JSON agents: if a fixture exists at `src/agents/flamescope_agents/fixtures/<agent>/<key>.json` use it; otherwise synthesize a schema-valid response from the request (for example, scorer values derived from card fields by fixed rules). Streaming: builds sentences from the supplied chunks with correct citation markers. `embed`: hashed bag-of-words vector of `EMBED_DIM`, L2-normalized. |
| `ollama` | `LLM_PROVIDER=ollama` (default in `.env.example`), `OLLAMA_BASE_URL`, `LLM_MODEL` (default `qwen2.5:0.5b`), `EMBED_MODEL` (default `nomic-embed-text`) | Ollama running natively on the Mac host. Chat: ADK `LiteLlm(model="ollama_chat/<LLM_MODEL>", api_base=OLLAMA_BASE_URL)`; JSON agents pass `output_schema`, which Ollama enforces as structured output. Embeddings: `POST <OLLAMA_BASE_URL>/api/embed` with `EMBED_MODEL` (768 dimensions, equal to `EMBED_DIM`). `temperature` and `max_tokens` from the prompt front matter map to the ADK `GenerateContentConfig`. |

Gateway features: timeout (`LLM_TIMEOUT_S`, default 60), retry with backoff on transient errors (3), response cache (`llm_cache`, through ADK `before_model_callback` / `after_model_callback`, disabled for streaming), token and latency logging, request-ID propagation. An unreachable Ollama server raises `LLMError`; request-time callers fall back as in section 7.

### 6.1 Model notes (`qwen2.5:0.5b`)
- Chosen for local, free, offline inference at laptop speed (ADR-11).
- Its small size limits extraction and long-form reasoning: expect more schema retries and more sentences dropped by the citation verifier. Both fail safe (null fields, fewer sentences), never into invented facts.
- `LLM_MODEL` may name any Ollama chat model (for example a larger `qwen2.5` variant) without code change; results record provider and model.
- Prerequisite on the host: `ollama pull qwen2.5:0.5b` and `ollama pull nomic-embed-text` (`make ollama-pull`).

## 7. Request-time LLM budget

| Flow | Calls | Fallback |
|------|-------|----------|
| Ask | 1 embedding + 1 streamed completion | `error` SSE event; UI shows retrieved sources. |
| Compare narrative | 1 completion | `narrative.status = unavailable`; matrix still shown. |
| Scenario explanation | 1 completion | `explanation.status = unavailable`; matches still shown. |
| Everything else | 0 | - |

## 8. Safety and quality guardrails

- Scores and narratives carry the disclaimer text (NFR-09).
- The prompt for every agent forbids operational safety directives ("this material is safe to use"); agents describe evidence.
- Prompt-injection hygiene: document text is delimited and labeled as data; instructions inside documents are ignored (stated in `grounding_rules.md`).
- All prompts and the rubric are versioned; versions are stored with results.
