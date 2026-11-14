"""Optional live-model check (document 12 section 2; document 07 sections 3 to 6).

Requirements: NFR-07 (agents on Google ADK; provider swapped to `ollama` by configuration;
`LLM_MODEL` read from `.env`). Call flows: CF-06 (comparator), CF-07 (scenario interpreter),
CF-09 (streamed insight QA and embeddings).

Marker `ollama`: skipped unless Ollama answers at `OLLAMA_BASE_URL` (seen from the host as
`localhost`) with `LLM_MODEL` and `EMBED_MODEL` pulled. The agents run in-process through
`AgentOrchestrator` with an in-memory response cache, so the deployed mock-mode stack is
only read (for realistic inputs) and never redeployed. Each agent must produce schema-valid
output whose sentences pass the citation verifier, or end in the documented `unavailable`
state (`LLMError`, or every sentence dropped); the outcome is printed in the summary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx
import pytest

from flamescope_agents.citation_verifier import CitationVerifier, ContextEntry
from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_api.services.compare import card_facts
from flamescope_common.config import Settings
from flamescope_common.errors import LLMError
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.schemas.agents import (
    ComparatorInput,
    ComparatorOutput,
    Fact,
    InsightQAInput,
    QAChunk,
    ScenarioInterpreterInput,
    ScenarioInterpreterOutput,
    VerifiedAnswer,
)
from flamescope_common.schemas.card import InvestigationCard
from flamescope_common.sources import SourceRef

pytestmark = [pytest.mark.integration, pytest.mark.ollama, pytest.mark.order(21)]

Rows = Callable[..., list[dict[str, Any]]]
CONTAINER_HOST = "host.docker.internal"
TAGS_TIMEOUT_S = 5.0
REPORT_SECTION = "NFR-07 live model (test_21_llm_ollama)"
RUN_FACT_LABELS = {
    "o2_fraction": "oxygen fraction",
    "pressure_kpa": "pressure (kPa)",
    "flow_speed_cm_s": "flow speed (cm/s)",
    "gravity_g": "gravity (g)",
}
FIXED_SENTENCE = "The curated PSI corpus does not contain enough information to answer that."
COMPARED = 3
TOP_MATCHES = 5  # doc 07 s3: the interpreter sees the top 5 matches
QA_CHUNKS = 4
QA_QUESTION = "Which experiments used the Combustion Integrated Rack?"
QA_CHUNK_QUERY = (
    "SELECT c.id, c.text, c.doc_title, c.source, i.acronym FROM chunk c "
    "JOIN investigation i ON i.id = c.investigation_id "
    "WHERE c.text ILIKE '%Combustion Integrated Rack%' ORDER BY c.id LIMIT :limit"
)


class InMemoryCache:
    """Keeps live replies out of the shared `llm_cache` table (same `get`/`put` as `LLMCache`)."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._entries.get(key)

    def put(self, key: str, provider: str, model: str, response: dict[str, Any]) -> None:
        self._entries[key] = response


def _tagged(model: str) -> str:
    """Ollama lists an untagged model as `<name>:latest`."""
    return model if ":" in model else f"{model}:latest"


@pytest.fixture(scope="module")
def live_settings(setting: Callable[[str], str]) -> Settings:
    base_url = setting("OLLAMA_BASE_URL").replace(CONTAINER_HOST, "localhost")
    models = [setting("LLM_MODEL"), setting("EMBED_MODEL")]
    try:
        tags = httpx.get(f"{base_url}/api/tags", timeout=TAGS_TIMEOUT_S).json()
    except httpx.HTTPError as error:
        pytest.skip(f"Ollama not reachable at {base_url}: {error}")
    pulled = {item["name"] for item in tags.get("models", [])}
    missing = [model for model in models if _tagged(model) not in pulled]
    if missing:
        pytest.skip(f"Ollama at {base_url} lacks {missing}; run make ollama-pull")
    return Settings(
        _env_file=None,
        llm_provider="ollama",
        embed_provider="ollama",
        ollama_base_url=base_url,
        llm_model=models[0],
        embed_model=models[1],
        llm_timeout_s=float(setting("LLM_TIMEOUT_S")),
        embed_dim=int(setting("EMBED_DIM")),
    )


@pytest.fixture(scope="module")
def gateway(live_settings: Settings) -> LLMGateway:
    return LLMGateway(live_settings, cache=InMemoryCache())  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def orchestrator(gateway: LLMGateway, live_settings: Settings) -> AgentOrchestrator:
    return AgentOrchestrator(gateway=gateway, settings=live_settings)


@pytest.fixture(scope="module")
def verifier(live_settings: Settings) -> CitationVerifier:
    return CitationVerifier(live_settings)


def _cards(stack: str, acronyms: Sequence[str]) -> list[InvestigationCard]:
    details = [httpx.get(f"{stack}/investigations/{a}", timeout=30).json() for a in acronyms]
    return [InvestigationCard.model_validate(detail["card"]) for detail in details]


def _fact_context(facts: Sequence[Fact]) -> dict[str, ContextEntry]:
    return {fact.id: ContextEntry(fact.text, fact.source) for fact in facts}


def _check_verified(answer: VerifiedAnswer, agent: str, report: Any) -> None:
    """Kept sentences are supported and cited; all dropped is the documented fallback."""
    kept = [sentence for sentence in answer.sentences if sentence.text != FIXED_SENTENCE]
    state = "ok" if kept else "unavailable (every sentence dropped by the verifier)"
    report.add(REPORT_SECTION, f"{agent}: {state}; kept {len(kept)}, dropped {answer.dropped}")
    assert all(sentence.supported and sentence.citations for sentence in kept)


def _report_unavailable(agent: str, error: LLMError, report: Any) -> None:
    report.add(REPORT_SECTION, f"{agent}: unavailable (LLMError: {error.message})")


def _post(stack: str, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
    response = httpx.post(f"{stack}{path}", json=body, timeout=30)
    assert response.status_code == httpx.codes.OK, response.text
    return dict(response.json())


def _comparator_input(stack: str, acronyms: list[str]) -> ComparatorInput:
    """The deterministic part of `POST /compare` plus the card facts the service supplies."""
    compared = _post(stack, "/compare", {"investigations": acronyms, "narrative": False})
    return ComparatorInput(
        investigations=compared["investigations"],
        matrix=compared["matrix"],
        shared=compared["shared"],
        facts=card_facts(_cards(stack, acronyms)),
    )


def _run_facts(matches: Sequence[Mapping[str, Any]]) -> list[Fact]:
    """The matched runs' conditions, as the scenario service supplies them (doc 08 s4.4)."""
    facts: list[Fact] = []
    for match in matches:
        run = match["best_run"]
        values = ", ".join(
            f"{label} {run['condition'][key]:g}"
            for key, label in RUN_FACT_LABELS.items()
            if run["condition"].get(key) is not None
        )
        text = f"{match['acronym']} run {run['label']}: {values}."
        facts.append(Fact(id=f"R{len(facts) + 1}", text=text, source=run["source"]))
    return facts


def _interpreter_input(stack: str) -> ScenarioInterpreterInput:
    """The lunar-preset scenario with fixture-run matches, as `explain=true` builds it."""
    resolved = _post(stack, "/scenario", {"preset": "lunar_habitat"})
    matches = resolved["matches"][:TOP_MATCHES]
    assert matches, "fixture runs must produce a match"
    return ScenarioInterpreterInput(
        scenario=resolved["scenario"],
        coverage=resolved["coverage"],
        matches=matches,
        gravity_bounding=resolved["gravity_bounding"],
        facts=_run_facts(matches),
    )


def _chunk_context(rows: list[dict[str, Any]]) -> dict[str, ContextEntry]:
    return {
        f"c:{row['id']}": ContextEntry(
            row["text"], SourceRef.model_validate({**row["source"], "chunk_id": row["id"]})
        )
        for row in rows
    }


async def _stream_answer(orchestrator: AgentOrchestrator, payload: InsightQAInput) -> str:
    return "".join([delta async for delta in orchestrator.run("insight_qa", payload, stream=True)])


async def test_nfr07_comparator_on_live_model(
    stack: str,
    seed_acronyms: list[str],
    orchestrator: AgentOrchestrator,
    verifier: CitationVerifier,
    terminal_report: Any,
) -> None:
    """NFR-07, CF-06: `ComparatorOutput` on the live model, then citation verification."""
    payload = _comparator_input(stack, sorted(seed_acronyms)[:COMPARED])
    try:
        output = await orchestrator.run("comparator", payload)
    except LLMError as error:
        _report_unavailable("comparator", error, terminal_report)
        return
    assert isinstance(output, ComparatorOutput)
    verified = verifier.verify(output.sentences, _fact_context(payload.facts))
    _check_verified(verified, "comparator", terminal_report)


async def test_nfr07_scenario_interpreter_on_live_model(
    stack: str,
    fixture_runs: list[int],
    orchestrator: AgentOrchestrator,
    verifier: CitationVerifier,
    terminal_report: Any,
) -> None:
    """NFR-07, CF-07: `ScenarioInterpreterOutput` for the lunar preset, then verification."""
    payload = _interpreter_input(stack)
    try:
        output = await orchestrator.run("scenario_interpreter", payload)
    except LLMError as error:
        _report_unavailable("scenario_interpreter", error, terminal_report)
        return
    assert isinstance(output, ScenarioInterpreterOutput)
    verified = verifier.verify(output.sentences, _fact_context(payload.facts))
    _check_verified(verified, "scenario_interpreter", terminal_report)


async def test_nfr07_insight_qa_streams_on_live_model(
    sql: Rows,
    orchestrator: AgentOrchestrator,
    verifier: CitationVerifier,
    terminal_report: Any,
) -> None:
    """NFR-07, CF-09: the streamed insight-QA draft passes the citation verifier."""
    rows = sql(QA_CHUNK_QUERY, limit=QA_CHUNKS)
    if not rows:
        pytest.skip("precondition absent: no chunk mentions the Combustion Integrated Rack")
    chunks = [
        QAChunk(
            chunk_id=row["id"],
            acronym=row["acronym"],
            doc_title=row["doc_title"],
            text=row["text"],
        )
        for row in rows
    ]
    try:
        draft = await _stream_answer(
            orchestrator, InsightQAInput(question=QA_QUESTION, chunks=chunks)
        )
    except LLMError as error:
        _report_unavailable("insight_qa", error, terminal_report)
        return
    assert draft.strip()
    _check_verified(verifier.verify(draft, _chunk_context(rows)), "insight_qa", terminal_report)


def test_nfr07_embeddings_have_embed_dim(
    gateway: LLMGateway, live_settings: Settings, terminal_report: Any
) -> None:
    """NFR-07, doc 07 s6: `EMBED_MODEL` vectors have `EMBED_DIM` dimensions."""
    vectors = gateway.embed(["Flame spread over PMMA in microgravity.", "Droplet combustion."])
    shape = f"{len(vectors)} x {len(vectors[0])}"
    terminal_report.add(REPORT_SECTION, f"embeddings: {shape} from {live_settings.embed_model}")
    assert [len(vector) for vector in vectors] == [live_settings.embed_dim] * len(vectors)
