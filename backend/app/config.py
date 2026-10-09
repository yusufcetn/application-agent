import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # APPLY_AGENT_ENV_FILE="" turns the .env file off (tests must not see personal settings).
    model_config = SettingsConfigDict(
        env_file=os.environ.get("APPLY_AGENT_ENV_FILE", str(ROOT_DIR / ".env")) or None,
        extra="ignore",
    )

    # LLM calls go through a locally logged-in CLI (subscription), not an API key.
    llm_provider: Literal["antigravity", "claude", "codex"] = "antigravity"
    # None = gemini-3.8-flash-medium for antigravity, the CLI's own default for claude/codex
    llm_model: str | None = None
    llm_timeout_seconds: int = 300
    # Web discovery searches and opens pages, so it gets more time and a result cap.
    web_search_timeout_seconds: int = 900
    web_search_max_results: int = 15
    # None = LLM_MODEL. A faster model keeps the many search/read turns short.
    web_search_model: str | None = None
    llm_max_concurrency: int = 2
    search_max_age_days: int = 30
    search_max_scored_per_run: int = 40
    # Postings scored below this are not saved (and not scored again).
    search_min_score_to_keep: int = 50
    scheduler_enabled: bool = True
    # Job alert emails (LinkedIn, Kariyer.net, ...) over IMAP. For Gmail use an app password.
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str | None = None
    imap_password: str | None = None
    imap_folder: str = "INBOX"
    # Daily report email. SMTP login defaults to the IMAP account, the recipient to that address.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str | None = None
    smtp_password: str | None = None
    report_email_to: str | None = None
    # Public address of the app (e.g. the Tailscale URL), for links in the report.
    app_url: str | None = None
    email_alert_senders: list[str] = ["linkedin.com", "kariyer.net", "indeed.com", "glassdoor.com"]
    # Alert emails of this many days are read, and their postings filtered again every run.
    email_lookback_days: int = 14
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    adzuna_country: str = "gb"
    antigravity_bin: str = "agy"
    claude_bin: str = "claude"
    codex_bin: str = "codex"
    data_dir: Path = ROOT_DIR / "data"
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'app.db'}"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Host headers the app answers to (the APP_URL host is added). Anything else is refused, so a
    # web page that points its own domain at 127.0.0.1 (DNS rebinding) can't read the API.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "*.ts.net"]
    # Required for access from other devices (phone over Tailscale). Unset = this computer only.
    api_token: str | None = None
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def allowed_hosts(settings: Settings) -> list[str]:
    hosts = list(settings.allowed_hosts)
    if settings.app_url and (host := urlparse(settings.app_url).hostname):
        hosts.append(host)
    return hosts
