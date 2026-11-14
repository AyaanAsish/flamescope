"""Settings defaults and overrides (document 11 section 3; NFR-02, NFR-07)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from flamescope_common.config import Settings, get_settings

pytestmark = pytest.mark.unit

ENV_VARIABLES = (
    "DATABASE_URL",
    "LLM_PROVIDER",
    "OLLAMA_BASE_URL",
    "LLM_MODEL",
    "LLM_TIMEOUT_S",
    "EMBED_PROVIDER",
    "EMBED_MODEL",
    "EMBED_DIM",
    "PSI_BUCKET",
    "PSI_REGION",
    "PSI_PREFIX",
    "HARVEST_MAX_DOC_MB",
    "HARVEST_MAX_TABLE_MB",
    "HARVEST_MAX_TABLES",
    "HARVEST_MAX_TOTAL_MB",
    "INGEST_COMMAND",
    "RAW_DIR",
    "DATA_DIR",
    "VERIFY_MIN_OVERLAP",
    "CORS_ORIGINS",
    "LOG_LEVEL",
)
BYTES_PER_MB = 1024 * 1024
DOCUMENTED_DEFAULTS: dict[str, object] = {
    "database_url": "postgresql+psycopg://flamescope:flamescope@db:5432/flamescope",
    "llm_provider": "mock",
    "ollama_base_url": "http://host.docker.internal:11434",
    "llm_model": "qwen2.5:0.5b",
    "llm_timeout_s": 60,
    "embed_model": "nomic-embed-text",
    "embed_dim": 768,
    "psi_bucket": "nasa-psi",
    "psi_region": "us-west-2",
    "psi_prefix": "",
    "harvest_max_doc_mb": 25,
    "harvest_max_table_mb": 5,
    "harvest_max_tables": 20,
    "harvest_max_total_mb": 300,
    "ingest_command": "seed",
    "raw_dir": Path("/data/raw"),
    "data_dir": Path("/app/src/data"),
    "verify_min_overlap": 0.35,
    "cors_origins": ["http://localhost:3000"],
    "log_level": "INFO",
}


def settings_view(settings: Settings, expected: dict[str, object]) -> dict[str, object]:
    """The attributes of `settings` named in `expected`, for one dictionary comparison."""
    return {name: getattr(settings, name) for name in expected}


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def settings_without_env_file() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.usefixtures("clean_environment")
def test_defaults_equal_document_11_section_3() -> None:
    """NFR-02: every default of document 11 section 3; unset LLM_PROVIDER falls back to mock."""
    settings = settings_without_env_file()

    assert settings_view(settings, DOCUMENTED_DEFAULTS) == DOCUMENTED_DEFAULTS
    assert settings.embed_provider_name == "mock"


@pytest.mark.usefixtures("clean_environment")
def test_embed_provider_defaults_to_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-07: EMBED_PROVIDER is 'same as LLM_PROVIDER' when unset."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    settings = settings_without_env_file()

    assert settings.embed_provider_name == "ollama"


@pytest.mark.usefixtures("clean_environment")
def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-07: providers, models and limits are set from the environment."""
    overrides = {
        "LLM_PROVIDER": "ollama",
        "EMBED_PROVIDER": "mock",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "LLM_MODEL": "qwen2.5:7b",
        "LLM_TIMEOUT_S": "12.5",
        "EMBED_DIM": "384",
        "VERIFY_MIN_OVERLAP": "0.5",
        "DATA_DIR": "/srv/flamescope-data",
        "HARVEST_MAX_DOC_MB": "2",
    }
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)

    expected = {
        "llm_provider": "ollama",
        "embed_provider_name": "mock",
        "ollama_base_url": "http://localhost:11434",
        "llm_model": "qwen2.5:7b",
        "llm_timeout_s": 12.5,
        "embed_dim": 384,
        "verify_min_overlap": 0.5,
        "data_dir": Path("/srv/flamescope-data"),
        "harvest_max_doc_bytes": 2 * BYTES_PER_MB,
    }

    assert settings_view(settings_without_env_file(), expected) == expected


@pytest.mark.usefixtures("clean_environment")
def test_cors_origins_accepts_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-06: CORS_ORIGINS may list several origins."""
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000")

    assert settings_without_env_file().cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


@pytest.mark.parametrize("variable", ["LLM_PROVIDER", "EMBED_PROVIDER"])
@pytest.mark.parametrize("provider", ["openai", "litellm", "gemini"])
@pytest.mark.usefixtures("clean_environment")
def test_invalid_provider_is_rejected(
    monkeypatch: pytest.MonkeyPatch, variable: str, provider: str
) -> None:
    """NFR-07: providers are `mock` and `ollama` only (document 07 section 6)."""
    monkeypatch.setenv(variable, provider)

    with pytest.raises(PydanticValidationError):
        settings_without_env_file()


def test_get_settings_is_cached_until_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-02: `get_settings()` is cached (document 03 section 2)."""
    first = get_settings()
    assert get_settings() is first

    monkeypatch.setenv("EMBED_DIM", "16")
    get_settings.cache_clear()

    assert get_settings().embed_dim == 16


def test_env_example_defaults_to_live_ollama(repo_root: Path) -> None:
    """NFR-07: `.env.example` sets LLM_PROVIDER=ollama and the documented models."""
    lines = (repo_root / ".env.example").read_text(encoding="utf-8").splitlines()
    assignments = dict(line.split("=", 1) for line in lines if "=" in line and line[0] != "#")

    assert assignments["LLM_PROVIDER"] == "ollama"
    assert assignments["LLM_MODEL"] == "qwen2.5:0.5b"
    assert assignments["EMBED_MODEL"] == "nomic-embed-text"
    assert assignments["EMBED_DIM"] == "768"
    assert set(ENV_VARIABLES) <= set(assignments)


def test_harness_forces_mock_provider() -> None:
    """NFR-02: unit tests always run against the mock provider (document 12)."""
    settings = get_settings()

    assert settings.llm_provider == "mock"
    assert settings.embed_provider_name == "mock"
