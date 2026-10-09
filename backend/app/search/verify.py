"""Check whether a posting still takes applications, without an LLM call."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.jobs.fetch import USER_AGENT
from app.text import fold

# LinkedIn doesn't allow automated access; its postings stay "unknown" unless found elsewhere.
SKIP_HOSTS = ("linkedin.com",)
# Web search results can point at redirect links (Gemini's grounding links) instead of the page.
REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)

# Search results sometimes link an image or a company's whole job list instead of a posting.
ASSET_HOSTS = ("amazonaws.com", "cloudfront.net", "googleusercontent.com")
ASSET_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".pdf")
# Last path parts of career home pages and job lists, not of a posting.
LIST_PAGES = {
    "careers", "career", "jobs", "job", "positions", "open-positions", "openings", "vacancies",
    "kariyer", "is-ilanlari", "ilanlar", "acik-pozisyonlar", "join-us", "work-with-us",
}
# What a single posting's path looks like on sites we know.
POSTING_PATHS = [
    (("greenhouse.io",), re.compile(r"^/[^/]+/jobs/\d+")),
    (("lever.co", "ashbyhq.com"), re.compile(r"^/[^/]+/[0-9a-f-]{36}")),
    (("workable.com",), re.compile(r"(^|/)j/[0-9a-z]+", re.I)),
    (("kariyer.net",), re.compile(r"^/is-ilani/.+-\d+")),
    (("linkedin.com",), re.compile(r"^/jobs/view/")),
    (("teamtailor.com",), re.compile(r"/jobs/\d+")),
    (("smartrecruiters.com",), re.compile(r"^/[^/]+/\d+")),
]

CLOSED_PHRASES = [
    (fold(p), p)
    for p in (
        "no longer accepting applications",
        "no longer available",
        "this job is no longer",
        "this position has been filled",
        "position has been filled",
        "job has expired",
        "posting has expired",
        "job posting has closed",
        "applications are closed",
        "applications have closed",
        "this job has been closed",
        "job not found",
        "başvurular kapandı",
        "başvuruları artık kabul etmiyor",
        "başvuruya kapanmıştır",
        "başvuruya kapalı",
        "ilan yayından kaldırıldı",
        "ilanın süresi doldu",
        "bu ilan artık aktif değil",
        "bu ilan yayında değil",
    )
]


@dataclass
class Check:
    # None when the page didn't tell either way.
    status: str | None
    reason: str
    deadline: date | None = None


def _json_ld_postings(soup: BeautifulSoup) -> list[dict]:
    found = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        found += [i for i in items if isinstance(i, dict) and i.get("@type") == "JobPosting"]
    return found


def _parse_deadline(value) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def check_page(url: str, html: str, final_url: str) -> Check:
    if "error=true" in final_url:  # Greenhouse sends closed postings back to the board
        return Check("closed", "İlan şirketin ilan listesinden kalkmış.")
    soup = BeautifulSoup(html, "html.parser")
    postings = _json_ld_postings(soup)
    deadline = next((d for p in postings if (d := _parse_deadline(p.get("validThrough")))), None)
    if deadline and deadline < datetime.now(UTC).date():
        return Check("closed", f"Son başvuru tarihi geçmiş ({deadline:%d.%m.%Y}).", deadline)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = fold(" ".join(soup.get_text(" ").split()))
    phrase = next((shown for key, shown in CLOSED_PHRASES if key in text), None)
    if phrase:
        return Check("closed", f"Sayfada “{phrase}” yazıyor.", deadline)
    if postings:
        return Check("open", "İlan sayfası yayında.", deadline)
    return Check(None, "Sayfa ilanın durumunu göstermiyor.", deadline)


def _on_host(url: str, hosts: tuple[str, ...]) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith("." + h) for h in hosts)


def looks_like_posting(url: str) -> bool:
    """False for images, files and job-list pages, which search results sometimes give."""
    path = urlparse(url).path
    if _on_host(url, ASSET_HOSTS) or path.lower().endswith(ASSET_EXTENSIONS) or "/logo" in path.lower():
        return False
    for hosts, pattern in POSTING_PATHS:
        if _on_host(url, hosts):
            return bool(pattern.search(path))
    last = path.strip("/").rsplit("/", 1)[-1].lower()
    return bool(last) and last not in LIST_PAGES


LISTED = "İlan şirketin ilan sisteminde yayında."
REMOVED = "İlan şirketin ilan sisteminden kalkmış."


def check_ats(url: str, client: httpx.Client) -> Check | None:
    """Exact answer from the public API of the ATS that hosts the posting; None otherwise."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    try:
        if _on_host(url, ("greenhouse.io",)) and len(parts) >= 3 and parts[1] == "jobs":
            res = client.get(f"https://boards-api.greenhouse.io/v1/boards/{parts[0]}/jobs/{parts[2]}")
        elif _on_host(url, ("lever.co",)) and len(parts) >= 2:
            api = "api.eu.lever.co" if ".eu." in (parsed.hostname or "") else "api.lever.co"
            res = client.get(f"https://{api}/v0/postings/{parts[0]}/{parts[1]}")
        elif _on_host(url, ("workable.com",)) and len(parts) >= 3 and parts[1] == "j":
            res = client.get(f"https://apply.workable.com/api/v2/accounts/{parts[0]}/jobs/{parts[2]}")
        elif _on_host(url, ("ashbyhq.com",)) and len(parts) >= 2:
            res = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}")
            if res.status_code == 200:
                jobs = res.json().get("jobs", [])
                listed = any(j.get("id") == parts[1] or parts[1] in (j.get("jobUrl") or "") for j in jobs)
                return Check("open", LISTED) if listed else Check("closed", REMOVED)
        else:
            return None
    except (httpx.HTTPError, ValueError):
        return None
    if res.status_code == 200:
        return Check("open", LISTED)
    if res.status_code == 404:
        return Check("closed", REMOVED)
    return None


def resolve_url(url: str, client: httpx.Client) -> str | None:
    """The page a search-result redirect link points to; None if it can't be resolved."""
    if not _on_host(url, REDIRECT_HOSTS):
        return url
    try:
        res = client.get(url, follow_redirects=False, timeout=20)
    except httpx.HTTPError:
        return None
    target = res.headers.get("location", "")
    return target if res.is_redirect and target.startswith(("http://", "https://")) else None


def check_posting(url: str, client: httpx.Client) -> Check:
    if not url.startswith(("http://", "https://")):
        return Check(None, "Manuel ilan bağlantısı yok.")
    if ats := check_ats(url, client):
        return ats
    if _on_host(url, SKIP_HOSTS):
        return Check(None, "LinkedIn ilanları otomatik kontrol edilmiyor.")
    try:
        res = client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=20)
    except httpx.HTTPError as e:
        return Check(None, f"Sayfa açılamadı: {e}")
    if res.status_code in (404, 410):
        return Check("closed", f"İlan sayfası artık yok (HTTP {res.status_code}).")
    if res.status_code >= 400:
        return Check(None, f"Sayfa açılamadı (HTTP {res.status_code}).")
    return check_page(url, res.text, str(res.url))
