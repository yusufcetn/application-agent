import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # APPLY_AGENT_ENV_FILE="" turns the .env file off (tests must not see personal settings).
    model_config = SettingsConfigDict(
        env_file=os.environ.get("APPLY_AGENT_ENV_FILE", str(ROOT_DIR / ".env")) or None,
        extra="ignore",
    )

    # LLM calls go through a locally logged-in CLI (subscription), not an API key.
    llm_provider: Literal["claude", "codex"] = "claude"
    llm_model: str | None = None  # None = the CLI's default model
    llm_timeout_seconds: int = 300
    llm_max_concurrency: int = 2
    search_max_age_days: int = 30
    search_max_scored_per_run: int = 40
    scheduler_enabled: bool = True
    # Job alert emails (LinkedIn, Kariyer.net, ...) over IMAP. For Gmail use an app password.
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str | None = None
    imap_password: str | None = None
    imap_folder: str = "INBOX"
    email_alert_senders: list[str] = ["linkedin.com", "kariyer.net", "indeed.com", "glassdoor.com"]
    email_lookback_days: int = 3
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    adzuna_country: str = "gb"
    claude_bin: str = "claude"
    codex_bin: str = "codex"
    data_dir: Path = ROOT_DIR / "data"
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'app.db'}"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Required for access from other devices (phone over Tailscale). Unset = this computer only.
    api_token: str | None = None
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
