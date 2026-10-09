import httpx

from app.schemas import SearchSettings
from app.sources.base import JobSource
from app.sources.email_alerts import EmailAlertSource
from app.sources.company_boards import AshbySource, GreenhouseSource, LeverSource
from app.sources.job_boards import AdzunaSource, ArbeitnowSource, RemoteOKSource, RemotiveSource
from app.sources.web_search import WebSearchSource


def enabled_sources(settings: SearchSettings, client: httpx.Client) -> list[JobSource]:
    s = settings.sources
    enabled = {
        GreenhouseSource: bool(s.greenhouse),
        LeverSource: bool(s.lever),
        AshbySource: bool(s.ashby),
        RemoteOKSource: s.remoteok,
        RemotiveSource: s.remotive,
        ArbeitnowSource: s.arbeitnow,
        AdzunaSource: s.adzuna,
        EmailAlertSource: s.email_alerts,
        WebSearchSource: s.web_search,
    }
    return [cls(client) for cls, on in enabled.items() if on]
