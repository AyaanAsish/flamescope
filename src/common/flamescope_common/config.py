"""Application settings (document 11 section 3)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ProviderName = Literal["mock", "ollama"]
BYTES_PER_MB = 1024 * 1024


class Settings(BaseSettings):
    """Environment-driven configuration shared by the API, agents and ingestion."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False, env_ignore_empty=True
    )

    database_url: str = "postgresql+psycopg://flamescope:flamescope@db:5432/flamescope"

    # Falls back to mock when unset; the test harness forces mock (document 11 section 3).
    llm_provider: ProviderName = "mock"
    ollama_base_url: str = "http://host.docker.internal:11434"
    llm_model: str = "qwen2.5:0.5b"
    llm_timeout_s: float = 60.0
    embed_provider: ProviderName | None = None
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    psi_bucket: str = "nasa-psi"
    psi_region: str = "us-west-2"
    psi_prefix: str = ""
    harvest_max_doc_mb: int = 25
    harvest_max_table_mb: int = 5
    harvest_max_tables: int = 20
    harvest_max_total_mb: int = 300
    ingest_command: str = "seed"

    raw_dir: Path = Path("/data/raw")
    data_dir: Path = Path("/app/src/data")

    verify_min_overlap: float = 0.35
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, raw: object) -> object:
        if isinstance(raw, str):
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        return raw

    @model_validator(mode="after")
    def _default_embed_provider(self) -> Settings:
        if self.embed_provider is None:
            self.embed_provider = self.llm_provider
        return self

    @property
    def embed_provider_name(self) -> ProviderName:
        """The embedding provider; never None after validation."""
        return self.embed_provider or self.llm_provider

    @property
    def harvest_max_doc_bytes(self) -> int:
        return self.harvest_max_doc_mb * BYTES_PER_MB

    @property
    def harvest_max_table_bytes(self) -> int:
        return self.harvest_max_table_mb * BYTES_PER_MB

    @property
    def harvest_max_total_bytes(self) -> int:
        return self.harvest_max_total_mb * BYTES_PER_MB


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide cached settings; call `get_settings.cache_clear()` after changing env."""
    return Settings()
