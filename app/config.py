"""Centralized application configuration."""

import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.grid_api_key: str = os.getenv("GRID_API_KEY", "")
        self.grid_auth_method: str = os.getenv("GRID_AUTH_METHOD", "x-api-key")
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "")
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.use_mock_data: bool = os.getenv("USE_MOCK_DATA", "false").lower() == "true"
        self.cors_origins: str = os.getenv("CORS_ORIGINS", "*")


@lru_cache
def get_settings() -> Settings:
    return Settings()
