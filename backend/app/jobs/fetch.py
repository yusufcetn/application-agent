"""Download a job posting page and turn it into plain text for the LLM."""

import json

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
# Below this much visible text the page is probably rendered client-side.
MIN_TEXT_CHARS = 800
MAX_TEXT_CHARS = 40_000


class FetchError(RuntimeError):
    pass


def _job_posting_json_ld(soup: BeautifulSoup) -> str | None:
    """Many ATS pages embed a schema.org JobPosting; it's the cleanest source."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return json.dumps(item, ensure_ascii=False)
    return None


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    json_ld = _job_posting_json_ld(soup)
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    body = "\n".join(line for line in lines if line)
    parts = [f"Page title: {title}"] if title else []
    if json_ld:
        parts.append(f"Structured JobPosting data:\n{json_ld}")
    parts.append(body)
    return "\n\n".join(parts)[:MAX_TEXT_CHARS]


def _fetch_static(url: str) -> str:
    try:
        res = httpx.get(
            url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=20
        )
        res.raise_for_status()
    except httpx.HTTPError as e:
        raise FetchError(f"İlan sayfası açılamadı: {e}") from e
    return res.text


def _fetch_rendered(url: str) -> str:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="networkidle", timeout=30_000)
                return page.content()
            finally:
                browser.close()
    except PlaywrightError as e:
        raise FetchError(f"İlan sayfası tarayıcıda açılamadı: {e}") from e


def fetch_posting_text(url: str) -> str:
    try:
        text = html_to_text(_fetch_static(url))
    except FetchError:
        text = ""  # often a bot block; a real browser may still get through
    if len(text) < MIN_TEXT_CHARS:
        text = html_to_text(_fetch_rendered(url))
    return text
