from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.schemas import SearchSettings

USER_AGENT = "Mozilla/5.0 (compatible; apply-agent/0.1; personal job search)"


@dataclass
class RawJob:
    source: str
    url: str
    company: str
    title: str
    location: str | None
    remote: bool | None
    posted_at: datetime | None
    description: str


class JobSource(ABC):
    name: str

    def __init__(self, client: httpx.Client):
        self.client = client

    @abstractmethod
    def fetch(self, settings: SearchSettings) -> list[RawJob]: ...

    def get_json(self, url: str, **params):
        res = self.client.get(url, params=params or None)
        res.raise_for_status()
        return res.json()


def make_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def from_timestamp(value, millis: bool = False) -> datetime | None:
    try:
        seconds = float(value) / (1000 if millis else 1)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, UTC)


def looks_remote(*texts: str | None) -> bool:
    joined = " ".join(t for t in texts if t).casefold()
    return any(w in joined for w in ("remote", "anywhere", "worldwide", "uzaktan"))
