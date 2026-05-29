from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Reaper Eagle Scout"
    app_env: str = "development"
    debug: bool = False

    database_url: str = "sqlite:///./eagle_scout.db"

    # Bright Data
    brightdata_api_key: str = ""
    brightdata_serp_zone: str = "serp_api1"
    brightdata_unlocker_zone: str = "web_unlocker1"
    brightdata_request_endpoint: str = "https://api.brightdata.com/request"
    allow_search_fallback: bool = True

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = 2000

    # CORS
    frontend_origin: str = "http://localhost:5173"

    # Search
    max_serp_results: int = 10
    max_pages_per_search: int = 8
    search_timeout_seconds: int = 120

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
