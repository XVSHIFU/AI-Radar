from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    radar_data_mode: Literal["postgres", "fixture"] = "postgres"
    database_url: str | None = None
    db_host: str | None = None
    db_port: int = 5432
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    admin_token: str | None = None
    business_timezone: str = "Asia/Shanghai"
    fetch_dns_mode: Literal["system", "cloudflare"] = "system"
    llm_api_key: str | None = None
    cursor_secret: str = Field(default="development-only-change-me", min_length=16)

    def sqlalchemy_url(self) -> str | URL | None:
        if self.database_url:
            return self.database_url
        if not all((self.db_host, self.db_name, self.db_user)):
            return None
        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
