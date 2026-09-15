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
    fetch_interval_seconds: float = Field(default=10.0, ge=1.0, le=3600.0)
    fetch_dns_mode: Literal["system", "cloudflare"] = "system"
    llm_api_key: str | None = None
    llm_provider: str = "deepseek"
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = Field(default="deepseek-flash", min_length=1, max_length=200)
    llm_max_tokens: int = Field(default=1600, ge=1, le=2000)
    model_config_path: Path = Path.home() / ".config" / "ai-radar" / "model.json"
    cursor_secret: str = Field(default="development-only-change-me", min_length=16)
    public_assistant_secret: str | None = Field(default=None, min_length=32)
    research_agent_enabled: bool = False
    research_runtime_url: str = "http://127.0.0.1:8081"
    research_runtime_token: str | None = Field(default=None, min_length=32, repr=False)
    assistant_input_per_day: int = Field(default=200_000, ge=24_000)
    assistant_output_per_day: int = Field(default=32_000, ge=4_800)
    embedding_model_dir: Path | None = None
    embedding_model_revision: str | None = None
    embedding_threads: int = Field(default=4, ge=1, le=8)

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

    def alembic_url(self) -> str | None:
        """Render the configured database URL without masking its password."""
        url = self.sqlalchemy_url()
        if isinstance(url, URL):
            return url.render_as_string(hide_password=False)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
