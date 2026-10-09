from datetime import UTC, datetime, timedelta

import httpx

from app import config
from app.llm import web_discovery
from app.llm.web_discovery import WebCandidate, WebDiscovery, WebPosting, WebSearchResult
from app.schemas import Profile, SearchSettings
from app.search.verify import Check, check_page, check_posting
from app.sources import web_search
from app.sources.base import RawJob
from app.sources.web_search import WebSearchSource


def _json_ld(valid_through: str) -> str:
    return (
        '<script type="application/ld+json">{"@type": "JobPosting", "title": "Backend", '
        f'"validThrough": "{valid_through}"}}</script>'
    )


def test_page_with_future_deadline_is_open():
    future = (datetime.now(UTC) + timedelta(days=5)).date()
    check = check_page("https://a.com/1", _json_ld(future.isoformat()) + "<p>Apply now</p>", "https://a.com/1")
    assert check.status == "open" and check.deadline == future


def test_page_with_past_deadline_or_closed_text_is_closed():
    assert check_page("u", _json_ld("2020-01-01T00:00:00Z"), "u").status == "closed"
    check = check_page("u", "<h1>Backend</h1><p>BAŞVURULAR KAPANDI</p>", "u")
    assert check.status == "closed" and "başvurular kapandı" in check.reason
    assert check_page("u", "<p>No longer accepting applications</p>", "u").status == "closed"
    assert check_page("u", "<p>Backend</p>", "https://boards.greenhouse.io/x?error=true").status == "closed"


def test_page_without_signals_is_inconclusive():
    assert check_page("u", "<p>Backend Developer, Python</p>", "u").status is None


def test_check_posting_reads_status_codes_and_skips_linkedin():
    def handler(request):
        return httpx.Response(404 if request.url.path == "/gone" else 403, text="")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert check_posting("https://a.com/gone", client).status == "closed"
    assert check_posting("https://a.com/blocked", client).status is None
    linkedin = check_posting("https://www.linkedin.com/jobs/view/1", client)
    assert linkedin.status is None and "LinkedIn" in linkedin.reason


def _candidate(**kw):
    base = dict(title="Working Student Backend", company="Firma", url="https://jobs.lever.co/firma/0f8a1c2e-1111-4a5b-9c3d-222233334444",
                location="İstanbul", remote=False, posted_at=None, employment_type="working_student",
                snippet="Python, FastAPI.")
    return WebCandidate(**{**base, **kw})


def test_discovery_reads_company_boards_and_checks_other_pages(monkeypatch):
    old = (datetime.now(UTC) - timedelta(days=90)).date().isoformat()
    search = WebSearchResult(queries=["q"], candidates=[
        _candidate(url="https://careers.firma.com/jobs/backend"),
        _candidate(url="https://a.com/unclear"),
        _candidate(url="https://a.com/gone"),
        _candidate(url="https://a.com/due"),
        _candidate(url="https://firma.com/careers"),
        _candidate(url="https://www.linkedin.com/jobs/view/9"),
        _candidate(url="https://workablehr.s3.amazonaws.com/uploads/account/logo/705076/logo"),
        # Two links to the same Greenhouse company and one Lever posting: two boards to read.
        _candidate(url="https://job-boards.greenhouse.io/goodjobgames"),
        _candidate(url="https://job-boards.greenhouse.io/goodjobgames/jobs/1"),
        _candidate(url="https://jobs.lever.co/firma/0f8a1c2e-1111-4a5b-9c3d-222233334444"),
        _candidate(url="not a url"),
        _candidate(url="https://a.com/old", posted_at=old),
    ])
    calls = []

    def fake_run(system, prompt, output, web=False, timeout=None, model=None):
        calls.append({"output": output, "prompt": prompt, "web": web, "model": model})
        return search

    boards = []

    def fake_board(kind, company, client, settings):
        boards.append((kind, company))
        if kind == "lever":
            raise RuntimeError("404")
        return [RawJob(source="greenhouse", url="https://job-boards.greenhouse.io/goodjobgames/jobs/1",
                       company="Good Job Games", title="Software Engineer - New Grad", location="İstanbul",
                       remote=False, posted_at=None, description="Tam metin", posting_status="open",
                       verification_reason="Şirketin ilan listesinde yayında.")]

    http = {"https://careers.firma.com/jobs/backend": Check("open", "İlan sayfası yayında."),
            "https://a.com/gone": Check("closed", "İlan sayfası artık yok (HTTP 404)."),
            "https://a.com/due": Check("open", "İlan sayfası yayında.", datetime(2024, 11, 5).date())}
    monkeypatch.setenv("WEB_SEARCH_MODEL", "fast-model")
    config.get_settings.cache_clear()
    monkeypatch.setattr(web_discovery, "run_structured", fake_run)
    monkeypatch.setattr(web_discovery, "check_posting", lambda url, client: http.get(url, Check(None, "?")))
    monkeypatch.setattr(web_discovery, "resolve_url", lambda url, client: url)
    monkeypatch.setattr(web_discovery, "fetch_board", fake_board)

    result = web_discovery.discover_postings(SearchSettings(target_roles=["Working Student"]), Profile(), None)
    by_url = {p.url: p for p in result.postings}
    # The logo image and the career home page are dropped; the Greenhouse links become that
    # company's listed postings.
    assert set(by_url) == {"https://careers.firma.com/jobs/backend", "https://a.com/unclear", "https://a.com/gone",
                           "https://a.com/due", "https://www.linkedin.com/jobs/view/9",
                           "https://job-boards.greenhouse.io/goodjobgames/jobs/1"}
    assert boards == [("greenhouse", "goodjobgames"), ("lever", "firma")]
    listed = by_url["https://job-boards.greenhouse.io/goodjobgames/jobs/1"]
    assert listed.status == "open" and listed.description == "Tam metin"
    assert by_url["https://a.com/gone"].status == "closed"
    assert by_url["https://a.com/unclear"].status == "unknown"
    assert by_url["https://www.linkedin.com/jobs/view/9"].status == "unknown"
    due = by_url["https://a.com/due"]  # an open page whose deadline has passed
    assert due.status == "closed" and "05.11.2024" in due.evidence
    # One agent call, the search; pages are checked without it.
    assert len(calls) == 1 and calls[0]["web"] and calls[0]["model"] == "fast-model"
    assert "Working Student" in calls[0]["prompt"]
    config.get_settings.cache_clear()  # drop the WEB_SEARCH_MODEL override for later tests


def test_board_links_name_the_company():
    from app.llm.web_discovery import board_of

    assert board_of("https://job-boards.greenhouse.io/goodjobgames") == ("greenhouse", "goodjobgames")
    assert board_of("https://jobs.ashbyhq.com/codeway/0f8a1c2e") == ("ashby", "codeway")
    assert board_of("https://apply.workable.com/wingieenuygun/j/3DC7AB606B") == ("workable", "wingieenuygun")
    assert board_of("https://apply.workable.com/j/3DC7AB606B") is None
    assert board_of("https://careers.smartrecruiters.com/BoschGroup") == ("smartrecruiters", "BoschGroup")
    assert board_of("https://www.kariyer.net/is-ilani/firma-4263977") is None


def _posting(**kw):
    base = dict(title="Working Student Backend", company="Firma", url="https://jobs.lever.co/firma/1",
                location="İstanbul", remote=False, posted_at=None, application_deadline="2026-10-01",
                employment_type="working_student", status="open", evidence="Başvuru butonu var.",
                description="Python, FastAPI.")
    return WebPosting(**{**base, **kw})


def test_web_source_keeps_only_postings_shown_to_be_open(client, monkeypatch):
    found = WebDiscovery(postings=[
        _posting(), _posting(url="https://a.com/2", status="unknown"), _posting(url="https://a.com/3", status="closed"),
    ])
    monkeypatch.setattr(web_search, "discover_postings", lambda settings, profile, client: found)
    jobs = WebSearchSource(None).fetch(SearchSettings())
    assert [j.url for j in jobs] == ["https://jobs.lever.co/firma/1"]
    first = jobs[0]
    assert first.source == "web" and first.posting_status == "open"
    assert first.employment_type == "working_student"
    assert first.application_deadline.isoformat() == "2026-10-01"
    assert first.verification_reason == "Başvuru butonu var."


def test_search_redirect_links_resolve_to_the_posting():
    from app.search.verify import resolve_url

    def handler(request):
        if request.url.host == "vertexaisearch.cloud.google.com":
            if request.url.path.endswith("/ok"):
                return httpx.Response(302, headers={"location": "https://firma.teamtailor.com/jobs/1"})
            return httpx.Response(404)
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    base = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
    assert resolve_url(base + "ok", client) == "https://firma.teamtailor.com/jobs/1"
    assert resolve_url(base + "broken", client) is None
    assert resolve_url("https://jobs.lever.co/firma/1", client) == "https://jobs.lever.co/firma/1"


def test_only_single_posting_links_count():
    from app.search.verify import looks_like_posting

    assert looks_like_posting("https://job-boards.greenhouse.io/goodjobgames/jobs/7574002003")
    assert not looks_like_posting("https://job-boards.greenhouse.io/goodjobgames")
    assert looks_like_posting("https://apply.workable.com/wingieenuygun/j/3DC7AB606B")
    assert not looks_like_posting("https://apply.workable.com/wingieenuygun/")
    assert not looks_like_posting("https://workablehr.s3.amazonaws.com/uploads/account/logo/705076/logo")
    assert not looks_like_posting("https://example.com/brand/logo.png")
    assert looks_like_posting("https://www.kariyer.net/is-ilani/firma-aday-muhendis-4263977")
    assert not looks_like_posting("https://www.kariyer.net/is-ilanlari/yazilim")
    assert looks_like_posting("https://careers.firma.com/jobs/backend")
    assert not looks_like_posting("https://careers.firma.com/")
    assert not looks_like_posting("https://insiderone.com/careers")
    assert not looks_like_posting("https://firma.com.tr/kariyer/")


def test_ats_postings_are_checked_through_their_public_api():
    from app.search.verify import check_ats

    def handler(request):
        url = str(request.url)
        if url == "https://boards-api.greenhouse.io/v1/boards/firma/jobs/1":
            return httpx.Response(200, json={"id": 1})
        if url == "https://apply.workable.com/api/v2/accounts/firma/jobs/ABC":
            return httpx.Response(404)
        if url == "https://api.ashbyhq.com/posting-api/job-board/firma":
            return httpx.Response(200, json={"jobs": [{"id": "0f8a1c2e-1111-4a5b-9c3d-222233334444"}]})
        if request.url.host == "api.lever.co":
            return httpx.Response(500)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert check_ats("https://job-boards.greenhouse.io/firma/jobs/1", client).status == "open"
    assert check_ats("https://job-boards.greenhouse.io/firma/jobs/2", client).status == "closed"
    assert check_ats("https://apply.workable.com/firma/j/ABC", client).status == "closed"
    assert check_ats("https://jobs.ashbyhq.com/firma/0f8a1c2e-1111-4a5b-9c3d-222233334444", client).status == "open"
    assert check_ats("https://jobs.ashbyhq.com/firma/99999999-1111-4a5b-9c3d-222233334444", client).status == "closed"
    assert check_ats("https://jobs.lever.co/firma/0f8a1c2e-1111-4a5b-9c3d-222233334444", client) is None
    assert check_ats("https://careers.firma.com/jobs/1", client) is None


def test_workable_and_smartrecruiters_boards_are_read():
    from app.sources.company_boards import SmartRecruitersSource, WorkableSource

    def handler(request):
        if request.url.host == "apply.workable.com":
            return httpx.Response(200, json={"name": "Wingie Enuygun Group", "jobs": [{
                "title": " Software Engineer ", "shortcode": "3DC7AB606B", "employment_type": "Part-time",
                "telecommuting": False, "published_on": "2026-09-20", "city": "İstanbul", "country": "Turkey"}]})
        assert request.url.params.get("country") == "tr"
        return httpx.Response(200, json={"content": [{
            "id": "744000146409534", "name": "Software Intern", "releasedDate": "2026-09-01T07:39:40.552Z",
            "location": {"city": "İstanbul", "fullLocation": "İstanbul, Turkey", "remote": False},
            "typeOfEmployment": {"label": "Intern"}, "company": {"name": "Bosch Group"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    [job] = WorkableSource(client).fetch_board("wingieenuygun")
    assert job.url == "https://apply.workable.com/wingieenuygun/j/3DC7AB606B/"
    assert (job.company, job.title, job.location, job.employment_type) == (
        "Wingie Enuygun Group", "Software Engineer", "İstanbul, Turkey", "part_time")
    assert job.posting_status == "open"
    [job] = SmartRecruitersSource(client).fetch_board("BoschGroup", "tr")
    assert job.url == "https://jobs.smartrecruiters.com/BoschGroup/744000146409534"
    assert (job.company, job.employment_type, job.posting_status) == ("Bosch Group", "internship", "open")
