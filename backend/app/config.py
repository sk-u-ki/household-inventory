"""Application settings loaded from household-inventory/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


def _psycopg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    postgres_db: str = "household"
    postgres_user: str = "household"
    postgres_password: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url_env: str = Field(default="", validation_alias="DATABASE_URL")

    lidl_language: str = "pl"
    lidl_country: str = "PL"
    lidl_refresh_token: str = ""
    lidl_refresh_token_file: str = ""

    @property
    def database_url(self) -> str:
        if self.database_url_env.strip():
            return _psycopg_url(self.database_url_env.strip())
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
