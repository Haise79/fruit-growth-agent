from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Fruit Growth Agent"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://fruit_agent:fruit_agent@localhost:5432/fruit_agent"
    )
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
