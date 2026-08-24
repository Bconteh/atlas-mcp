"""
Configuration management with environment-specific profiles (dev, uit, prod)
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Environment
    environment: str = "dev"
    app_name: str = "Atlas MCP Server"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Atlas API
    atlas_api_base_url: str = "https://atlas-api.dev.example.com"
    atlas_api_key: str = "mock-api-key-dev"
    atlas_api_timeout: int = 30
    atlas_use_mock: bool = True  # Use mock data instead of real Atlas API

    # LLM Configuration (OpenAI-compatible: works with GitHub Copilot, Azure OpenAI, OpenAI)
    llm_api_key: str = "your-llm-api-key-here"
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.1

    # GitHub Copilot / Azure OpenAI overrides (optional)
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: Optional[str] = "2024-02-01"

    # MCP Settings
    mcp_server_name: str = "atlas-mcp"
    mcp_server_version: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


class DevSettings(Settings):
    environment: str = "dev"
    debug: bool = True
    atlas_api_base_url: str = "https://atlas-api.dev.example.com"
    atlas_api_key: str = "mock-api-key-dev"
    atlas_use_mock: bool = True

    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class UitSettings(Settings):
    environment: str = "uit"
    debug: bool = False
    atlas_api_base_url: str = "https://atlas-api.uit.example.com"
    atlas_api_key: str = "mock-api-key-uit"
    atlas_use_mock: bool = True

    model_config = SettingsConfigDict(
        env_file=".env.uit",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class ProdSettings(Settings):
    environment: str = "prod"
    debug: bool = False
    atlas_api_base_url: str = "https://atlas-api.prod.example.com"
    atlas_api_key: str = "prod-api-key"
    atlas_use_mock: bool = False

    model_config = SettingsConfigDict(
        env_file=".env.prod",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def get_settings() -> Settings:
    """Return the appropriate settings based on APP_ENV environment variable."""
    env = os.getenv("APP_ENV", "dev").lower()
    settings_map = {
        "dev": DevSettings,
        "uit": UitSettings,
        "prod": ProdSettings,
    }
    settings_class = settings_map.get(env, DevSettings)
    return settings_class()


@lru_cache()
def get_cached_settings() -> Settings:
    """Cached settings instance."""
    return get_settings()

