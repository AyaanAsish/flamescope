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
| `insight_qa.md` | InsightQAAgent | `insight_qa@2` |
| `earth_apps.md` | EarthAppsAgent | `earth_apps@1` |
| `shared/grounding_rules.md` | included by all | - |
| `shared/domain_primer.md` | included by all | - |

File format: YAML front matter (`name`, `version`, `output_schema`, `temperature`, `max_tokens`) followed by `## System` and `## User` sections. Variables use `{{name}}`. `{{> shared/grounding_rules.md}}` includes a shared file. `base.Agent` renders the file; no prompt text is embedded in Python.

- `output_schema` names the output model in `flamescope_common/schemas/agents.py`; `text` marks a plain-text agent (Insight QA).
- Framework variables, supplied by `base.Agent` for every prompt: `{{input_json}}`, the validated input payload as JSON (every `## User` embeds it, which is also how the mock provider finds the input, section 6), and `{{validation_feedback}}`, empty on the first attempt and the raw validation error on a retry (section 5); every `## User` ends with it. Top-level scalar input fields are also available as variables (for example `{{acronym}}`).

`shared/grounding_rules.md` content (normative summary): use only the supplied context; cite by the given IDs; never invent numbers, names, DOIs or links; return null for unknowns; keep quotes verbatim and under 240 characters; output JSON only, matching the schema.

`shared/domain_primer.md`: short glossary - microgravity versus normal gravity, buoyancy, opposed and concurrent flow, flammability limits, oxygen fraction versus partial pressure, cool flames, hardware names (CIR, MSG, MDCA, ACME, SPICE duct), and the partial-gravity gap.

## 3. Agent contracts

### ExtractorAgent
- **Input**: `{acronym, title, psi_url, context:[{doc_id, title, section, text}]}`
- **Output**: `InvestigationCard` draft as `ExtractorOutput` (`schemas/agents.py`), which mirrors the card fields; every source is a `DraftSource {doc_id, quote}` with a verbatim `quote`.
- **Post-checks** (in `extract_stage.py`): quote is a substring of the cited text; units parse; vocabulary valid. `extract_stage.py` then converts each `DraftSource` to a `SourceRef` (the `doc_id` becomes the document URI).

### ScorerAgent
- **Input**: `{acronym, lens, criteria:[{id, label, description, anchors:{0..5}}], card, excerpts:[{chunk_id, text}]}`
- **Output**: `{lens, scores:[{criterion, value:0-5|null, rationale, evidence:[{chunk_id|field_path, quote}]}]}`
- **Rule**: a non-null value requires at least one evidence item.

### ComparatorAgent
- **Input**: `{investigations:[summary + key card fields], matrix, shared, facts:[{id, text, source}]}`
- **Output**: `{sentences:[{text, fact_ids:[...]}]}` - 4 to 7 sentences covering what is common, what differs, and what the difference means for fire safety. The sentence count is schema-enforced by `ComparatorOutput` (a shorter or longer answer fails validation and is retried).

### ScenarioInterpreterAgent
- **Input**: `{scenario, coverage, matches (top 5 with runs), gravity_bounding, facts:[{id, text, source}]}`
- **Output**: `{sentences:[{text, fact_ids}], caveats:[text]}`. Must repeat the gravity-bounding statement when gravity is neither 0 nor 1, and must flag every `extrapolated` or `no_data` dimension.

### InsightQAAgent
- **Input**: `{question, chunks:[{chunk_id, acronym, doc_title, text}], card_facts:[{id, acronym, text}]}`
- **Output (streamed text)**: plain sentences, each ending with one or more citation markers `[c:123]` (chunk) or `[f:45]` (card fact). No Markdown headings.
- **Refusal**: when context is insufficient, output exactly the fixed sentence in document 05, section 10.

### EarthAppsAgent
- **Input**: `{findings:[{id, acronym, statement, category}], known_applications:[...]}`
- **Output**: `{applications:[{title, sector, description, finding_ids, confidence}]}`.
- **Caller**: the harvest-mode `review` stage (`review.py`, document 06 section 3.9), once per investigation with stored findings; `known_applications` are the curated entries of `earth_applications.yaml`. Seed mode never calls it.
- **Persistence**: candidates are written to `/data/raw/<acronym>/earth_candidates.json` with the prompt version, never to the database. They are shown only after a curator copies them into `earth_applications.yaml`, the only source of `earth_application` rows (document 04 section 2).
- **Post-check**: candidates citing no supplied finding id are dropped.

## 4. Citation verifier

`CitationVerifier.verify(sentences: str | Sequence[SentenceWithFacts], context: Mapping[str, ContextEntry]) -> VerifiedAnswer`. Deterministic, no LLM.

- A `str` is an Insight QA draft whose sentences cite with `[c:ID]` / `[f:ID]` markers; a sequence of `SentenceWithFacts {text, fact_ids}` comes from the comparator or scenario interpreter.
- `context` is keyed `"c:123"`, `"f:45"` or a fact ID; `ContextEntry(text, source: SourceRef)` is defined in `citation_verifier.py`.
- The texts cited by one sentence are pooled for the number and overlap checks. Markers are stripped from kept sentence text.
- When every sentence is dropped, the result is the fixed sentence with `supported=True` and no citations.

Steps:

1. Parse citation markers; a sentence without a marker is `unsupported`.
2. For each cited chunk or fact, compute support: every number in the sentence (with unit normalization) must appear in the cited text, and token overlap of content words must be at least 0.35 (configurable `VERIFY_MIN_OVERLAP`).
3. Unsupported sentences are dropped from the final answer; the count is returned as `dropped`.
4. If all sentences are dropped, the fixed insufficient-information sentence is returned.

## 5. Orchestrator

`AgentOrchestrator.run(name, payload, *, stream=False)` is a plain method that returns an awaitable or an async iterator:

- `await orchestrator.run(name, payload)` returns the validated output model (a `str` for Insight QA).
- `orchestrator.run(name, payload, stream=True)` returns an `AsyncIterator[str]` of text deltas (`async for`).
- Synchronous callers (the ingestion stages) use `asyncio.run(orchestrator.run(name, payload))`.
- Constructor: `AgentOrchestrator(gateway=None, settings=None, agents=None)`; defaults build the gateway from settings and register every agent.
- `prompt_version(name)` returns the version key (for example `scorer@1`) that callers store with results (section 8); `agent_names()` lists the registered agents.

Steps of one call:
1. Resolve the agent; validate the payload against its input schema.
2. Render the prompt; compute the cache key.
3. Run the agent's ADK `LlmAgent` (model from `LLMGateway.model()`, `instruction` = rendered `## System`, user message = rendered `## User`, `output_schema` = output model for JSON agents) through an ADK `Runner` with an `InMemorySessionService`: one throwaway session per call, nothing persisted. Insight QA streams with `RunConfig(streaming_mode=StreamingMode.SSE)`.
4. Validate output; on schema failure, retry up to 2 times with the validation error appended (as `{{validation_feedback}}`, section 2).
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
| `mock` | `LLM_PROVIDER=mock` (tests, offline fallback) | `MockLlm` (subclass of ADK `BaseLlm`), deterministic, no network. It finds the agent input by scanning the rendered `## User` text, then the `## System` text, for a JSON object that validates as one of the agent `*Input` models (hence `{{input_json}}`, section 2). JSON agents: if a fixture exists at `src/agents/flamescope_agents/fixtures/<agent>/<key>.json` (`<key>` = first 16 hex characters of the SHA-256 of the rendered user text) use it; otherwise synthesize a schema-valid response from the request (for example, scorer values derived from card fields by fixed rules). Fixtures are optional: the mock synthesizes output for every agent, so the `fixtures/` directory may be absent. Streaming: builds sentences from the supplied chunks with correct citation markers. `embed`: hashed bag-of-words vector of the content words (lower-cased `[a-z0-9]+` tokens minus a fixed English stop-word list, `STOP_WORDS` in `mock.py`), length `EMBED_DIM`, L2-normalized; text without content words maps to a fixed unit vector. Shared function words therefore add no similarity (document 05 section 10). |
| `ollama` | `LLM_PROVIDER=ollama` (default in `.env.example`), `OLLAMA_BASE_URL`, `LLM_MODEL` (default `qwen2.5:0.5b`), `EMBED_MODEL` (default `nomic-embed-text`) | Ollama running natively on the Mac host. Chat: ADK `LiteLlm(model="ollama_chat/<LLM_MODEL>", api_base=OLLAMA_BASE_URL)`; JSON agents pass `output_schema`, which Ollama enforces as structured output. Embeddings: `POST <OLLAMA_BASE_URL>/api/embed` with `EMBED_MODEL` (768 dimensions, equal to `EMBED_DIM`). `temperature` and `max_tokens` from the prompt front matter map to the ADK `GenerateContentConfig`. |

Gateway features: timeout (`LLM_TIMEOUT_S`, default 60), retry with backoff on transient errors (3), response cache (`llm_cache`, through ADK `before_model_callback` / `after_model_callback`, disabled for streaming: the callbacks read `callback_context.run_config.streaming_mode` and skip the cache when it is `SSE`, so `callbacks()` keeps its signature; only valid replies are cached: a reply to a request whose `output_schema` is an output model is cached only when it validates against that model (after stripping a Markdown code fence, as `base.Agent` does), a plain-text reply only when non-empty, and a reply to a request carrying any other schema form is not cached, so an invalid reply is never replayed to a schema retry or a later identical request), token and latency logging, request-ID propagation. An unreachable Ollama server raises `LLMError`; request-time callers fall back as in section 7.

### 6.1 Model notes (`qwen2.5:0.5b`)
- Chosen for local, free, offline inference at laptop speed (ADR-11).
- Its small size limits extraction and long-form reasoning: expect more schema retries and more sentences dropped by the citation verifier. Both fail safe (null fields, fewer sentences), never into invented facts.
- `LLM_MODEL` may name any Ollama chat model (for example a larger `qwen2.5` variant) without code change; results record provider and model.
- The Ollama provider disables reasoning for every chat call: `llm/providers/ollama.py` passes `think=False` through the `LiteLlm` extra arguments, which LiteLLM sends as Ollama `think: false` (`THINKING_ENABLED` in that module). Without it a reasoning model (Ollama capability `thinking`) spends the prompt `max_tokens` on hidden reasoning and ends with "Maximum tokens reached"; models without the capability ignore the flag.
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
