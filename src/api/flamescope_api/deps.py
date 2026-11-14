"""Dependency providers: session, settings, repositories, services, orchestrator (doc 03 s4)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from flamescope_agents.citation_verifier import CitationVerifier
from flamescope_agents.orchestrator import AgentOrchestrator
from flamescope_api.repositories.chunks import ChunkRepo
from flamescope_api.repositories.earth import EarthRepo
from flamescope_api.repositories.investigations import InvestigationRepo
from flamescope_api.repositories.runs import RunRepo
from flamescope_api.repositories.scores import ScoreRepo
from flamescope_api.services.catalog import CatalogService
from flamescope_api.services.compare import CompareService
from flamescope_api.services.earth import EarthService
from flamescope_api.services.extract import ExtractService
from flamescope_api.services.insight import InsightService
from flamescope_api.services.meta import MetaService
from flamescope_api.services.ranking import RankingService
from flamescope_api.services.safety_tech import SafetyTechService
from flamescope_api.services.scenario import ScenarioService
from flamescope_common.config import Settings, get_settings
from flamescope_common.db import get_session
from flamescope_common.llm.gateway import LLMGateway
from flamescope_common.rubric import Presets, Rubric

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache(maxsize=1)
def get_rubric() -> Rubric:
    return Rubric.load()


@lru_cache(maxsize=1)
def get_presets() -> Presets:
    presets = Presets.load()
    presets.validate_against(get_rubric())
    return presets


@lru_cache(maxsize=1)
def get_gateway() -> LLMGateway:
    return LLMGateway()


@lru_cache(maxsize=1)
def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(gateway=get_gateway())


@lru_cache(maxsize=1)
def get_verifier() -> CitationVerifier:
    return CitationVerifier()


RubricDep = Annotated[Rubric, Depends(get_rubric)]
PresetsDep = Annotated[Presets, Depends(get_presets)]


def get_investigation_repo(session: SessionDep) -> InvestigationRepo:
    return InvestigationRepo(session)


def get_run_repo(session: SessionDep) -> RunRepo:
    return RunRepo(session)


def get_score_repo(session: SessionDep, rubric: RubricDep) -> ScoreRepo:
    return ScoreRepo(session, rubric.rubric_version)


def get_chunk_repo(session: SessionDep) -> ChunkRepo:
    return ChunkRepo(session)


def get_earth_repo(session: SessionDep) -> EarthRepo:
    return EarthRepo(session)


InvestigationRepoDep = Annotated[InvestigationRepo, Depends(get_investigation_repo)]
RunRepoDep = Annotated[RunRepo, Depends(get_run_repo)]
ScoreRepoDep = Annotated[ScoreRepo, Depends(get_score_repo)]
ChunkRepoDep = Annotated[ChunkRepo, Depends(get_chunk_repo)]
EarthRepoDep = Annotated[EarthRepo, Depends(get_earth_repo)]
OrchestratorDep = Annotated[AgentOrchestrator, Depends(get_orchestrator)]
VerifierDep = Annotated[CitationVerifier, Depends(get_verifier)]
GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]


def get_ranking_service(
    scores: ScoreRepoDep, rubric: RubricDep, presets: PresetsDep
) -> RankingService:
    return RankingService(scores, rubric, presets)


RankingServiceDep = Annotated[RankingService, Depends(get_ranking_service)]


def get_catalog_service(
    investigations: InvestigationRepoDep, runs: RunRepoDep, ranking: RankingServiceDep
) -> CatalogService:
    return CatalogService(investigations, runs, ranking)


def get_compare_service(
    investigations: InvestigationRepoDep,
    ranking: RankingServiceDep,
    orchestrator: OrchestratorDep,
    verifier: VerifierDep,
) -> CompareService:
    return CompareService(investigations, ranking, orchestrator, verifier)


def get_scenario_service(
    runs: RunRepoDep,
    investigations: InvestigationRepoDep,
    presets: PresetsDep,
    orchestrator: OrchestratorDep,
    verifier: VerifierDep,
) -> ScenarioService:
    return ScenarioService(runs, investigations, presets, orchestrator, verifier)


def get_extract_service(runs: RunRepoDep, rubric: RubricDep) -> ExtractService:
    return ExtractService(runs, rubric)


def get_insight_service(
    chunks: ChunkRepoDep,
    investigations: InvestigationRepoDep,
    orchestrator: OrchestratorDep,
    verifier: VerifierDep,
    gateway: GatewayDep,
) -> InsightService:
    return InsightService(chunks, investigations, orchestrator, verifier, gateway)


def get_safety_tech_service(
    investigations: InvestigationRepoDep, runs: RunRepoDep
) -> SafetyTechService:
    return SafetyTechService(investigations, runs)


def get_earth_service(earth: EarthRepoDep) -> EarthService:
    return EarthService(earth)


def get_meta_service(
    investigations: InvestigationRepoDep,
    settings: SettingsDep,
    rubric: RubricDep,
    gateway: GatewayDep,
) -> MetaService:
    return MetaService(investigations, settings, rubric, gateway)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
CompareServiceDep = Annotated[CompareService, Depends(get_compare_service)]
ScenarioServiceDep = Annotated[ScenarioService, Depends(get_scenario_service)]
ExtractServiceDep = Annotated[ExtractService, Depends(get_extract_service)]
InsightServiceDep = Annotated[InsightService, Depends(get_insight_service)]
SafetyTechServiceDep = Annotated[SafetyTechService, Depends(get_safety_tech_service)]
EarthServiceDep = Annotated[EarthService, Depends(get_earth_service)]
MetaServiceDep = Annotated[MetaService, Depends(get_meta_service)]
