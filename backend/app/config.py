"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # --- Application ---
    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str = "change-this-to-a-random-secret"
    cors_origins: str = "http://localhost:3000"

    # --- LLM API Keys ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- Database ---
    database_url: str = "postgresql+asyncpg://knockknock:knockknock@localhost:5432/knockknock_ai"
    redis_url: str = "redis://localhost:6379/0"

    # --- Vector Database ---
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "knockknock-knowledge"

    # --- Web Search ---
    tavily_api_key: str = ""

    # --- Content Platforms ---
    note_api_token: str = ""
    medium_api_token: str = ""
    wordpress_url: str = ""
    wordpress_username: str = ""
    wordpress_password: str = ""

    # --- SNS ---
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    linkedin_access_token: str = ""

    # --- SEO & Analytics ---
    google_search_console_credentials: str = ""
    ahrefs_api_key: str = ""
    ga4_property_id: str = ""

    # --- Agent Model Configuration ---
    # Use valid Anthropic model IDs. See https://docs.anthropic.com/en/docs/models
    default_orchestrator_model: str = "claude-sonnet-4-5-20250514"
    default_writer_model: str = "claude-sonnet-4-5-20250514"
    default_researcher_model: str = "claude-sonnet-4-5-20250514"
    default_planner_model: str = "claude-sonnet-4-5-20250514"
    default_editor_model: str = "claude-sonnet-4-5-20250514"
    default_localizer_model: str = "claude-sonnet-4-5-20250514"
    default_publisher_model: str = "claude-haiku-4-5-20250514"

    # --- Pipeline ---
    max_retry_count: int = Field(default=3, description="Max retries per quality gate")
    article_generation_timeout: int = Field(default=1800, description="Timeout in seconds")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
