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
    jwt_public_key: str = ""
    jwt_audience: str = "fruit-agent-api"
    log_level: str = "INFO"
    demo_mode: bool = False
    demo_private_key_path: str = ".demo/rs256-private.pem"
    demo_public_key_path: str = ".demo/rs256-public.pem"


@lru_cache
def get_settings() -> Settings:
    return Settings()
