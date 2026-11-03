from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = "replace-with-a-long-random-value"
    database_url: str = "sqlite:///./data/truthlayer.db"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 8
    image_retention_days: int = 7
    allowed_origins: str = "http://localhost:5173"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    gemini_enabled: bool = True
    gemini_timeout_seconds: int = 25
    gemini_max_retries: int = 1
    tavily_api_key: str = ""
    tavily_enabled: bool = True
    tavily_max_results: int = 5
    tavily_timeout_seconds: int = 20
    min_ocr_confidence: float = 0.55
    max_search_queries: int = 5
    offline_dataset_dir: str = "./data/datasets"
    rate_limit_enabled: bool = True
    rate_limit_upload_per_minute: int = Field(default=60, ge=1, le=10000)
    rate_limit_processing_per_minute: int = Field(default=60, ge=1, le=10000)
    rate_limit_general_per_minute: int = Field(default=300, ge=1, le=10000)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
