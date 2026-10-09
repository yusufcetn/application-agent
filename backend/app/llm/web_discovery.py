"""Find open job postings on the web with an LLM agent that runs web searches.

1. The agent runs targeted web searches and returns candidates (no page reads).
2. A link to a company's ATS (Greenhouse, Lever, Ashby, Workable, SmartRecruiters), be it a
   posting or the job list, brings in all of that company's open postings through the ATS's
   public API: exact links, known to be open, usually with the full text.
3. Other links must be a single posting (no images or list pages) and are checked over plain
   HTTP. Only postings shown to be open are kept; pages that block bots (e.g. Kariyer.net)
   can't be checked, and letting the agent open them was too slow and unreliable.
"""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.llm.runner import run_structured
from app.schemas import EmploymentType, Profile, SearchSettings
from app.search.verify import check_posting, looks_like_posting, resolve_url
from app.sources.base import RawJob
from app.sources.company_boards import (
    AshbySource,
    GreenhouseSource,
    LeverSource,
    SmartRecruitersSource,
    WorkableSource,
)
from app.text import fold

logger = logging.getLogger(__name__)

# Company boards read per run.
MAX_BOARDS = 10
# ATS hosts whose company boards can be read; the first path part is the company.
BOARD_HOSTS = [
    ("greenhouse", ("greenhouse.io",)),
    ("lever", ("lever.co",)),
    ("ashby", ("ashbyhq.com",)),
    ("workable", ("apply.workable.com",)),
    ("smartrecruiters", ("smartrecruiters.com",)),
]
TURKEY = {"turkiye", "turkey", "istanbul", "ankara", "izmir", "kocaeli", "bursa", "antalya"}

SEARCH_PROMPT = """\
You look for job postings on the web for one candidate.

Turn the search settings and the candidate summary into {min_queries}-{max_queries} targeted \
web searches. Mix Turkish and English terms (e.g. "working student", "part time", "aday \
mühendis", "yarı zamanlı"), the target locations, and site-specific searches for company \
career pages, ATS pages (Lever, Greenhouse, Ashby, Workable, SmartRecruiters, Teamtailor), \
Youthall, Kariyer.net and LinkedIn job pages.

Use the search results only: do not open pages and never log in anywhere. Return a candidate \
for each result that is a single job posting fitting the settings (role, location, level), and \
for each company job list on Greenhouse, Lever, Ashby, Workable or SmartRecruiters that looks \
likely to have fitting roles (title: the fitting role you saw, url: the list page). When the \
same posting shows up on the company's own career or ATS page and on an aggregator or LinkedIn, \
return the company's URL. Skip postings the results show as closed or older than \
{max_age_days} days.

snippet: what the result says about the role, in its language. employment_type: full_time, \
part_time, working_student, internship or contract when stated, otherwise null. Dates as \
YYYY-MM-DD, null when not shown. Never invent postings, URLs, dates or companies.

Return at most {max_results} candidates, best matches first, and the searches you ran.
"""


class WebCandidate(BaseModel):
    title: str
    company: str
    url: str
    location: str | None = None
    remote: bool | None = None
    posted_at: str | None = None
    employment_type: EmploymentType | None = None
    snippet: str = ""


class WebSearchResult(BaseModel):
    queries: list[str] = []
    candidates: list[WebCandidate] = []


class WebPosting(BaseModel):
    title: str
    company: str
    url: str
    location: str | None = None
    remote: bool | None = None
    posted_at: str | None = None
    application_deadline: str | None = None
    employment_type: EmploymentType | None = None
    status: Literal["open", "closed", "unknown"]
    evidence: str
    description: str = ""


class WebDiscovery(BaseModel):
    queries: list[str] = []
    postings: list[WebPosting] = []


def parse_day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def _request(settings: SearchSettings, profile: Profile, today: date) -> str:
    request = {
        "today": today.isoformat(),
        "target_roles": settings.target_roles,
        "locations": settings.locations,
        "remote_only": settings.remote_only,
        "levels": settings.seniority,
        "exclude_title_words": settings.keywords_exclude,
        "candidate": {
            "headline": profile.headline,
            "location": profile.location,
            "education": [
                f"{e.degree or ''} {e.field or ''}, {e.school} ({e.start_date or '?'}-{e.end_date or 'present'})".strip()
                for e in profile.education
            ],
            "skills": [*profile.skills.languages, *profile.skills.frameworks][:15],
        },
    }
    return "Search settings and candidate:\n" + json.dumps(request, ensure_ascii=False, indent=1)


def search_candidates(settings: SearchSettings, profile: Profile) -> WebSearchResult:
    config = get_settings()
    today = datetime.now(UTC).date()
    system = SEARCH_PROMPT.format(
        min_queries=5, max_queries=8,
        max_age_days=config.search_max_age_days, max_results=config.web_search_max_results,
    )
    result = run_structured(
        system, _request(settings, profile, today), WebSearchResult,
        web=True, timeout=config.web_search_timeout_seconds, model=config.web_search_model,
    )
    oldest = today - timedelta(days=config.search_max_age_days)
    result.candidates = [
        c
        for c in result.candidates[: config.web_search_max_results]
        if c.url.startswith(("http://", "https://")) and (parse_day(c.posted_at) or today) >= oldest
    ]
    return result


def board_of(url: str) -> tuple[str, str] | None:
    """(ATS, company) when the link is on a company's ATS board, posting or list."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    parts = [p for p in parsed.path.split("/") if p]
    for kind, hosts in BOARD_HOSTS:
        if any(host == h or host.endswith("." + h) for h in hosts):
            # Workable's short links (/j/CODE) don't name the account.
            if parts and not (kind == "workable" and parts[0] == "j"):
                return kind, parts[0]
    return None


def fetch_board(kind: str, company: str, client: httpx.Client, settings: SearchSettings) -> list[RawJob]:
    if kind == "greenhouse":
        return GreenhouseSource(client).fetch_board(company)
    if kind == "lever":
        return LeverSource(client).fetch_board(company)
    if kind == "ashby":
        return AshbySource(client).fetch_board(company)
    if kind == "workable":
        return WorkableSource(client).fetch_board(company)
    # SmartRecruiters boards of big companies are huge; ask for the country when it's clear.
    places = {w for loc in settings.locations for w in fold(loc).split()}
    return SmartRecruitersSource(client).fetch_board(company, "tr" if places & TURKEY else None)


def _from_board(job: RawJob) -> WebPosting:
    return WebPosting(
        title=job.title, company=job.company, url=job.url, location=job.location, remote=job.remote,
        posted_at=job.posted_at.date().isoformat() if job.posted_at else None,
        employment_type=job.employment_type, status="open",
        evidence=job.verification_reason or "Şirketin ilan listesinde yayında.",
        description=job.description,
    )


def discover_postings(settings: SearchSettings, profile: Profile, client: httpx.Client) -> WebDiscovery:
    found = search_candidates(settings, profile)
    postings: list[WebPosting] = []
    boards: list[tuple[str, str]] = []
    for c in found.candidates:
        url = resolve_url(c.url, client)
        if not url:
            continue
        board = board_of(url)
        if board:
            if board not in boards:
                boards.append(board)
            continue
        if not looks_like_posting(url) or any(p.url == url for p in postings):
            continue
        check = check_posting(url, client)
        postings.append(
            WebPosting(
                title=c.title, company=c.company, url=url, location=c.location, remote=c.remote,
                posted_at=c.posted_at, employment_type=c.employment_type, description=c.snippet,
                status=check.status or "unknown", evidence=check.reason,
                application_deadline=check.deadline.isoformat() if check.deadline else None,
            )
        )
    logger.info(
        "Web search: %d candidates, %d company boards, %d single postings",
        len(found.candidates), len(boards), len(postings),
    )
    for kind, company in boards[:MAX_BOARDS]:
        try:
            listed = fetch_board(kind, company, client, settings)
        except Exception as e:  # a wrong guess at a company name shouldn't stop the others
            logger.warning("Board %s/%s could not be read: %s", kind, company, e)
            continue
        logger.info("Board %s/%s: %d postings", kind, company, len(listed))
        known = {p.url for p in postings}
        postings += [_from_board(j) for j in listed if j.url not in known]
    today = datetime.now(UTC).date()
    for p in postings:
        deadline = parse_day(p.application_deadline)
        if p.status != "closed" and deadline and deadline < today:
            p.status, p.evidence = "closed", f"Son başvuru tarihi geçmiş ({deadline:%d.%m.%Y})."
    return WebDiscovery(queries=found.queries, postings=postings)
