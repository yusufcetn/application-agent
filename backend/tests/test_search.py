import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.llm.score import JobScore
from app.schemas import SearchSettings, SourceSettings
from app.search import filters, service
from app.sources.base import JobSource, RawJob
from app.sources.company_boards import AshbySource, GreenhouseSource, LeverSource
from app.sources.job_boards import ArbeitnowSource, RemoteOKSource, RemotiveSource
from tests.conftest import load_example

NOW = datetime.now(UTC)


def raw(title="Backend Developer", url="https://x.com/1", location="İstanbul", remote=False, days_old=1):
    return RawJob(
        source="remotive", url=url, company="Firma", title=title, location=location,
        remote=remote, posted_at=NOW - timedelta(days=days_old), description="Python",
    )


# --- filters ----------------------------------------------------------------


@pytest.mark.parametrize(
    "title,roles,expected",
    [
        ("Senior Back-End Engineer", ["Backend Developer"], True),
        ("Backend Geliştirici", ["Backend Developer"], True),
        ("Frontend Developer", ["Backend Developer"], False),
        ("Python Developer (Django)", ["Backend Developer", "Python Developer"], True),
        ("Software Engineer, Payments", ["Software Engineer"], True),
        ("Software Architect", ["Software Engineer"], False),
        ("KIDEMLİ YAZILIM MÜHENDİSİ", ["Yazılım Mühendisi"], True),
        ("Anything", [], True),
    ],
)
def test_matches_role(title, roles, expected):
    assert filters.matches_role(title, roles) is expected


def test_location_rules():
    s = SearchSettings(locations=["İstanbul", "Remote"])
    assert filters.matches_location(raw(location="İstanbul, Türkiye"), s)
    assert filters.matches_location(raw(location="Berlin", remote=True), s)
    assert not filters.matches_location(raw(location="Berlin"), s)
    assert filters.matches_location(raw(location="Berlin"), SearchSettings())
    assert not filters.matches_location(raw(location="İstanbul"), SearchSettings(remote_only=True))
    assert filters.matches_location(raw(location="Remote - EMEA"), SearchSettings(remote_only=True))


@pytest.mark.parametrize(
    "wanted,job_location",
    [
        ("İstanbul", "Istanbul, Turkey"),
        ("istanbul", "İSTANBUL, TÜRKİYE"),
        ("Türkiye", "Ankara, Turkey"),
        ("Turkey", "İzmir, Türkiye"),
    ],
)
def test_location_matches_across_turkish_and_english_spellings(wanted, job_location):
    assert filters.matches_location(raw(location=job_location), SearchSettings(locations=[wanted]))


def test_role_matches_without_turkish_characters():
    assert filters.matches_role("Kidemli Yazilim Muhendisi", ["Yazılım Mühendisi"])
    assert filters.matches_role("Backend Gelistirici", ["Backend Developer"])


def test_prefilter_combines_rules():
    s = SearchSettings(target_roles=["Backend Developer"], keywords_exclude=["Principal"])
    jobs = [
        raw(),
        raw(title="Principal Backend Developer"),
        raw(title="Designer"),
        raw(days_old=60),
    ]
    assert filters.prefilter(jobs, s, max_age_days=30) == [jobs[0]]


def test_relevance_prefers_matching_skills():
    from app.schemas import Profile

    profile = Profile.model_validate(load_example("profile"))
    keywords = filters.profile_keywords(profile, [], ["Backend Developer"])
    python_job = raw(title="Backend Engineer (Python)")
    python_job.description = "FastAPI, PostgreSQL and Docker"
    cpp_job = raw(title="Software Engineer")
    cpp_job.description = "C++ and embedded systems"
    assert filters.relevance(python_job, keywords) > filters.relevance(cpp_job, keywords)


# --- sources (fake HTTP) ----------------------------------------------------


def client_returning(payloads: dict[str, object]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        for fragment, body in payloads.items():
            if fragment in str(request.url):
                return httpx.Response(200, json=body)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_greenhouse_parses_escaped_html():
    client = client_returning({"boards/acme/jobs": {"jobs": [{
        "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
        "title": " Backend Engineer ", "company_name": "Acme",
        "location": {"name": "Remote - Europe"}, "metadata": [],
        "first_published": "2026-09-17T13:05:33-04:00",
        "content": "&lt;h2&gt;About&lt;/h2&gt;&lt;p&gt;Python &amp;amp; Go&lt;/p&gt;",
    }]}})
    [job] = GreenhouseSource(client).fetch(SearchSettings(sources=SourceSettings(greenhouse=["acme"])))
    assert job.title == "Backend Engineer" and job.company == "Acme" and job.remote
    assert job.description == "About\nPython & Go"
    assert job.posted_at.tzinfo is not None


def test_lever_joins_description_parts():
    client = client_returning({"postings/acme": [{
        "hostedUrl": "https://jobs.lever.co/acme/1", "text": "Backend Engineer",
        "categories": {"location": "London"}, "workplaceType": "remote",
        "createdAt": 1711403416463, "descriptionPlain": "Intro",
        "lists": [{"text": "Requirements", "content": "<li>Python</li>"}],
        "additionalPlain": "Benefits",
    }]})
    [job] = LeverSource(client).fetch(SearchSettings(sources=SourceSettings(lever=["acme"])))
    assert job.company == "Acme" and job.remote
    assert job.description == "Intro\n\nRequirements\nPython\n\nBenefits"
    assert job.posted_at.year == 2024


def test_ashby_skips_unlisted():
    client = client_returning({"job-board/acme": {"jobs": [
        {"jobUrl": "https://jobs.ashbyhq.com/acme/1", "title": "Backend", "isListed": True,
         "isRemote": True, "location": "NY", "publishedAt": "2026-09-01T00:00:00+00:00",
         "descriptionPlain": "Text"},
        {"jobUrl": "https://jobs.ashbyhq.com/acme/2", "title": "Hidden", "isListed": False},
    ]}})
    jobs = AshbySource(client).fetch(SearchSettings(sources=SourceSettings(ashby=["acme"])))
    assert [j.title for j in jobs] == ["Backend"]


def test_remoteok_skips_legal_notice():
    client = client_returning({"remoteok.com/api": [
        {"legal": "API terms"},
        {"url": "https://remoteok.com/remote-jobs/1", "company": "Acme", "position": "Backend Dev",
         "location": "", "date": "2026-09-21T16:00:11+00:00", "description": "<p>Go</p>"},
    ]})
    [job] = RemoteOKSource(client).fetch(SearchSettings())
    assert job.remote and job.location == "Remote" and job.description == "Go"


def test_remotive_dedupes_across_roles():
    posting = {"url": "https://remotive.com/1", "title": "Backend", "company_name": "Acme",
               "candidate_required_location": "Europe", "publication_date": "2026-09-18T16:43:22",
               "description": "<p>x</p>"}
    client = client_returning({"remote-jobs": {"jobs": [posting]}})
    jobs = RemotiveSource(client).fetch(SearchSettings(target_roles=["Backend", "Python"]))
    assert len(jobs) == 1 and jobs[0].posted_at.tzinfo is not None


def test_arbeitnow_stops_without_next_page():
    client = client_returning({"job-board-api": {"data": [
        {"url": "https://arbeitnow.com/1", "title": "Backend", "company_name": "Acme",
         "location": "Berlin", "remote": False, "created_at": 1790099717, "description": "x"},
    ], "links": {"next": None}}})
    assert len(ArbeitnowSource(client).fetch(SearchSettings())) == 1


# --- search run -------------------------------------------------------------


class FakeSource(JobSource):
    name = "fake"
    jobs: list[RawJob] = []
    error: Exception | None = None

    def fetch(self, settings):
        if self.error:
            raise self.error
        return list(self.jobs)


@pytest.fixture
def search_env(client, monkeypatch):
    client.put("/api/profile", json=load_example("profile"))
    settings = load_example("settings")
    settings.update(target_roles=["Backend Developer"], locations=[], seniority=["junior", "mid"],
                    keywords_exclude=[], min_score=70)
    client.put("/api/settings", json=settings)

    FakeSource.jobs = [
        raw(title="Backend Developer", url="https://x.com/good?utm_source=a"),
        raw(title="Backend Developer", url="https://x.com/weak"),
        raw(title="Senior Backend Engineer", url="https://x.com/senior"),
        raw(title="Designer", url="https://x.com/designer"),
    ]
    FakeSource.error = None
    sources = [FakeSource(None)]
    monkeypatch.setattr(service, "enabled_sources", lambda settings, client: sources)

    scored = {"https://x.com/good": (85, "mid"), "https://x.com/weak": (40, "junior"),
              "https://x.com/senior": (90, "senior")}
    calls = []

    def fake_score(profile, projects, jobs):
        calls.append([j.url for j in jobs])
        return [JobScore(index=i, score=scored[j.url][0], score_reason="neden",
                         seniority=scored[j.url][1]) for i, j in enumerate(jobs)]

    packaged = []
    monkeypatch.setattr(service, "score_jobs", fake_score)
    monkeypatch.setattr(service, "generate_package", packaged.append)
    return {"sources": sources, "calls": calls, "packaged": packaged}


def test_search_run_end_to_end(client, search_env):
    res = client.post("/api/search/run")
    assert res.status_code == 202
    run = client.get(f"/api/search/runs/{res.json()['id']}").json()
    assert run["status"] == "done" and run["error"] is None
    assert (run["jobs_found"], run["jobs_new"], run["jobs_above_threshold"]) == (4, 2, 1)

    # designer filtered by rules, senior filtered by seniority after scoring
    assert sorted(search_env["calls"][0]) == ["https://x.com/good", "https://x.com/senior", "https://x.com/weak"]
    jobs = client.get("/api/jobs").json()
    assert [(j["url"], j["score"]) for j in jobs] == [("https://x.com/good", 85), ("https://x.com/weak", 40)]
    good = jobs[0]
    assert good["package_status"] == "generating" and good["seniority"] == "mid"
    assert search_env["packaged"] == [good["id"]]

    # A second run finds nothing new and doesn't re-score the senior posting.
    client.post("/api/search/run")
    assert len(search_env["calls"]) == 1
    runs = client.get("/api/search/runs").json()
    assert len(runs) == 2 and runs[0]["jobs_new"] == 0
    assert client.get("/api/search/runs", params={"limit": 1}).json()[0]["id"] == runs[0]["id"]


def test_search_run_reports_broken_source(client, search_env):
    broken = FakeSource(None)
    broken.name = "broken"
    broken.error = RuntimeError("timeout")
    search_env["sources"].append(broken)

    run = client.post("/api/search/run").json()
    run = client.get(f"/api/search/runs/{run['id']}").json()
    assert run["status"] == "done"
    assert "broken: timeout" in run["error"]


def test_search_run_fails_when_all_sources_fail(client, search_env):
    FakeSource.error = RuntimeError("down")
    run = client.post("/api/search/run").json()
    run = client.get(f"/api/search/runs/{run['id']}").json()
    assert run["status"] == "failed" and "down" in run["error"]


def test_search_requires_profile(client):
    assert client.post("/api/search/run").status_code == 409


def test_invalid_cron_is_rejected(client):
    settings = load_example("settings")
    settings["schedule_cron"] = "every morning"
    assert client.put("/api/settings", json=settings).status_code == 422
