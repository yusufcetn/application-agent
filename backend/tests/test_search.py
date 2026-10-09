import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.llm.score import JobScore
from app.schemas import SearchSettings, SourceSettings
from app.search import filters, service
from app.search.verify import Check
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


@pytest.mark.parametrize(
    "title,role,expected",
    [
        # Possessive forms are the generic word, not a specific one.
        ("Yazılım Stajyeri", "Yazılım Stajyeri", True),
        ("Muhasebe Stajyeri", "Yazılım Stajyeri", False),
        ("Uzun Dönem Stajyer - Yazılım", "Uzun Dönem Yazılım Stajyeri", True),
        ("Uzun Dönem Pazarlama Stajyeri", "Uzun Dönem Yazılım Stajyeri", False),
        ("Yazılım Mühendisi Stajyeri", "Yazılım Mühendisliği Stajyeri", True),
        # Work arrangements alone don't match any posting of that kind.
        ("Software Engineer (Part-Time)", "Part Time Software Engineer", True),
        ("Part-Time Sales Associate", "Part Time Software Engineer", False),
        ("Yazılım Mühendisi - Yarı Zamanlı", "Yarı Zamanlı Yazılım Mühendisi", True),
        ("Yarı Zamanlı Kasiyer", "Yarı Zamanlı Yazılım Mühendisi", False),
        ("Student Engineer - Embedded Software", "Student Engineer", True),
        ("Student Ambassador", "Student Engineer", False),
        ("Aday Mühendis (Yazılım)", "Aday Mühendis", True),
        ("Aday Satış Temsilcisi", "Aday Mühendis", False),
        ("Software Engineer Intern", "Software Engineering Intern", True),
        ("Mechanical Engineering Intern", "Software Engineering Intern", False),
        # A role with no field word needs a software word in the title.
        ("Working Student Software Development", "Working Student", True),
        ("Working Student Marketing", "Working Student", False),
        ("Backend Stajyer", "Stajyer", True),
        ("Muhasebe Stajyer", "Stajyer", False),
        ("Stajyer Yazılım Geliştirici", "Stajyer", True),
        # A specific word still decides on its own.
        ("Uzun Dönem Yapay Zeka Stajyeri", "Yapay Zeka Mühendisi", True),
        ("Data Science Intern", "Data Science Intern", True),
    ],
)
def test_role_qualifiers_and_turkish_forms(title, role, expected):
    assert filters.matches_role(title, [role]) is expected


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


def test_company_boards_drop_non_location_values():
    client = client_returning({
        "postings/peakgames": [{
            "hostedUrl": "https://jobs.lever.co/peakgames/1", "text": "Backend Engineer",
            "categories": {"location": "Full-time"}, "createdAt": 1711403416463,
        }],
        "job-board/good-job-games": {"jobs": [{
            "jobUrl": "https://jobs.ashbyhq.com/good-job-games/1", "title": "Game Developer",
            "location": "Good Job Games", "publishedAt": "2026-09-01T00:00:00+00:00",
        }]},
    })
    settings = SearchSettings(sources=SourceSettings(lever=["peakgames"], ashby=["good-job-games"]))
    [lever_job] = LeverSource(client).fetch(settings)
    [ashby_job] = AshbySource(client).fetch(settings)
    assert lever_job.location is None and ashby_job.location is None


def test_unknown_location_kept_only_for_company_boards():
    s = SearchSettings(locations=["İstanbul"])
    board_job = raw(location=None)
    board_job.source = "lever"
    assert filters.matches_location(board_job, s)
    assert not filters.matches_location(raw(location=None), s)
    assert not filters.matches_location(board_job, SearchSettings(remote_only=True))


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
    monkeypatch.setattr(service, "_queue_package", packaged.append)
    # Saved postings are re-checked over HTTP; answer from this dict instead (url -> Check).
    pages: dict[str, Check] = {}
    monkeypatch.setattr(service, "check_posting", lambda url, client: pages.get(url, Check(None, "?")))
    return {"sources": sources, "calls": calls, "packaged": packaged, "pages": pages}


def test_search_run_end_to_end(client, search_env):
    res = client.post("/api/search/run")
    assert res.status_code == 202
    run = client.get(f"/api/search/runs/{res.json()['id']}").json()
    assert run["status"] == "done" and run["error"] is None
    assert (run["jobs_found"], run["jobs_new"], run["jobs_above_threshold"]) == (4, 1, 1)

    # designer filtered by rules; after scoring, senior dropped by seniority, weak by low score
    assert sorted(search_env["calls"][0]) == ["https://x.com/good", "https://x.com/senior", "https://x.com/weak"]
    jobs = client.get("/api/jobs").json()
    assert [(j["url"], j["score"]) for j in jobs] == [("https://x.com/good", 85)]
    good = jobs[0]
    assert good["package_status"] == "generating" and good["seniority"] == "mid"
    assert search_env["packaged"] == [good["id"]]

    # A second run finds nothing new and doesn't re-score the dropped postings.
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


def _age_checks(job_id):
    """Pretend the last check was long ago, so the next run looks at the page again."""
    from sqlmodel import Session

    from app.db import JobRow, get_engine

    with Session(get_engine()) as session:
        row = session.get(JobRow, job_id)
        row.last_verified_at = datetime(2020, 1, 1, tzinfo=UTC)
        session.add(row)
        session.commit()


def test_saved_posting_that_closes_and_reopens_is_tracked(client, search_env):
    client.post("/api/search/run")
    job = client.get("/api/jobs").json()[0]
    assert job["posting_status"] == "unknown"

    search_env["pages"]["https://x.com/good"] = Check("closed", "Sayfada “başvurular kapandı” yazıyor.")
    _age_checks(job["id"])
    run = client.get(f"/api/search/runs/{client.post('/api/search/run').json()['id']}").json()
    assert run["jobs_closed"] == 1
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["posting_status"] == "closed" and "kapandı" in job["verification_reason"]

    search_env["pages"]["https://x.com/good"] = Check("open", "İlan sayfası yayında.")
    _age_checks(job["id"])
    client.post("/api/search/run")
    from sqlmodel import Session, col, select

    from app.db import SearchRunRow, get_engine

    with Session(get_engine()) as session:
        last = session.exec(select(SearchRunRow).order_by(col(SearchRunRow.started_at).desc())).first()
        assert last.summary["reopened"] == [job["id"]]
    assert client.get(f"/api/jobs/{job['id']}").json()["posting_status"] == "open"


def test_board_posting_missing_from_the_board_is_closed(client, search_env, monkeypatch):
    listed = raw(title="Backend Developer", url="https://jobs.lever.co/firma/1")
    listed.source, listed.posting_status, listed.verification_reason = "lever", "open", "Listede"
    board = FakeSource(None)
    board.name = "lever"
    board.jobs = [listed]
    search_env["sources"][:] = [board]
    search_env["calls"].clear()

    def score(profile, projects, jobs):
        return [JobScore(index=i, score=80, score_reason="iyi", seniority="mid") for i, _ in enumerate(jobs)]

    monkeypatch.setattr(service, "score_jobs", score)
    client.post("/api/search/run")
    job = client.get("/api/jobs").json()[0]
    assert job["posting_status"] == "open" and job["last_verified_at"]

    board.jobs = [raw(title="Backend Developer", url="https://jobs.lever.co/firma/2")]
    board.jobs[0].source = "lever"
    client.post("/api/search/run")
    assert client.get(f"/api/jobs/{job['id']}").json()["posting_status"] == "closed"


def test_scheduled_run_emails_the_report(client, search_env, monkeypatch):
    from app.search import report

    settings = client.get("/api/settings").json()
    client.put("/api/settings", json={**settings, "daily_report": True})
    sent = []
    monkeypatch.setattr(report, "send_email", lambda subject, text, html: sent.append((subject, text)) or "me@x.com")

    service.run_scheduled_search()
    assert len(sent) == 1
    subject, text = sent[0]
    assert "Yeni bulunan ilanlar (1)" in text and "https://x.com/good" in text
    assert "1 ilan" in subject

    # A manual run doesn't email; the report can still be sent on demand.
    client.post("/api/search/run")
    assert len(sent) == 1
    run_id = client.get("/api/search/runs", params={"limit": 1}).json()[0]["id"]
    assert client.post(f"/api/search/runs/{run_id}/report").json() == {"sent_to": "me@x.com"}


def test_report_needs_mail_settings(client, search_env):
    client.post("/api/search/run")
    run_id = client.get("/api/search/runs", params={"limit": 1}).json()[0]["id"]
    res = client.post(f"/api/search/runs/{run_id}/report")
    assert res.status_code == 409 and "IMAP_USER" in res.json()["detail"]


def _saved_urls():
    from sqlmodel import Session, select

    from app.db import JobRow, get_engine

    with Session(get_engine()) as session:
        return sorted(session.exec(select(JobRow.url)).all())


def test_each_scored_batch_is_saved_even_if_a_later_one_fails(client, search_env, monkeypatch):
    monkeypatch.setattr(service, "SCORE_BATCH", 1)
    FakeSource.jobs = [raw(title="Backend Developer", url="https://x.com/good"),
                       raw(title="Backend Developer", url="https://x.com/second")]
    calls = []

    def score(profile, projects, jobs):
        calls.append(jobs)
        if len(calls) == 2:
            raise RuntimeError("LLM düştü")
        return [JobScore(index=0, score=85, score_reason="iyi", seniority="mid")]

    monkeypatch.setattr(service, "score_jobs", score)
    run = client.post("/api/search/run").json()
    run = client.get(f"/api/search/runs/{run['id']}").json()
    assert run["status"] == "failed" and "LLM düştü" in run["error"]
    assert run["jobs_scored"] == 1 and run["jobs_new"] == 1
    assert len(_saved_urls()) == 1
    assert search_env["packaged"]  # its package started without waiting for the run


def test_fast_sources_are_saved_while_the_web_search_is_still_running(client, search_env, monkeypatch):
    import threading
    import time

    release = threading.Event()

    class SlowWeb(FakeSource):
        name = "web"

        def fetch(self, settings):
            assert release.wait(10)
            return [raw(title="Backend Developer", url="https://x.com/good")]

    FakeSource.jobs = [raw(title="Backend Developer", url="https://x.com/weak"),
                       raw(title="Backend Developer", url="https://x.com/senior")]
    search_env["sources"][:] = [FakeSource(None), SlowWeb(None)]
    scored = {"https://x.com/good": 85, "https://x.com/weak": 75, "https://x.com/senior": 90}

    def score(profile, projects, jobs):
        return [JobScore(index=i, score=scored[j.url], score_reason="iyi", seniority="mid") for i, j in enumerate(jobs)]

    monkeypatch.setattr(service, "score_jobs", score)
    try:
        run, created = service.start_run()
        worker = threading.Thread(target=service.execute_run, args=(run.id,))
        worker.start()
        for _ in range(100):  # the fast source's jobs appear before the web search returns
            if _saved_urls() == ["https://x.com/senior", "https://x.com/weak"]:
                break
            time.sleep(0.05)
        assert _saved_urls() == ["https://x.com/senior", "https://x.com/weak"]
        progress = client.get(f"/api/search/runs/{run.id}").json()
        assert progress["status"] == "running" and progress["jobs_scored"] == 2
        release.set()
        worker.join(10)
    finally:
        release.set()
    assert _saved_urls() == ["https://x.com/good", "https://x.com/senior", "https://x.com/weak"]
    done = client.get(f"/api/search/runs/{run.id}").json()
    assert done["status"] == "done" and done["jobs_new"] == 3 and done["jobs_found"] == 3


def test_database_waits_for_the_other_writer_and_reads_do_not_block(client):
    from sqlalchemy import text
    from sqlmodel import Session

    from app.db import get_engine

    with Session(get_engine()) as session:
        conn = session.connection()
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 30000


def test_a_run_that_breaks_while_failing_is_still_marked_failed(client, search_env, monkeypatch):
    def broken(session, run):
        session.close = None  # closing this session will blow up too
        raise RuntimeError("database is locked")

    monkeypatch.setattr(service, "_search", broken)
    run = client.post("/api/search/run").json()
    run = client.get(f"/api/search/runs/{run['id']}").json()
    # Before, a second failure while marking the run left it "running" for good.
    assert run["status"] == "failed" and run["finished_at"]



def test_a_scoring_failure_skips_its_postings_and_the_run_goes_on(client, search_env, monkeypatch):
    from app.llm.runner import LLMError

    monkeypatch.setattr(service, "SCORE_BATCH", 1)
    FakeSource.jobs = [raw(url=f"https://x.com/{name}") for name in "abcd"]
    calls = []
    failing = {1, 3}  # calls that time out; two failures stop scoring for the run

    def score(profile, projects, jobs):
        calls.append(jobs[0].url)
        if len(calls) in failing:
            raise LLMError("LLM yanıtı zaman aşımına uğradı.")
        return [JobScore(index=0, score=85, score_reason="iyi", seniority="mid")]

    monkeypatch.setattr(service, "score_jobs", score)
    run = client.post("/api/search/run").json()
    run = client.get(f"/api/search/runs/{run['id']}").json()
    assert run["status"] == "done" and "puanlanamadı" in run["error"]
    assert len(calls) == 3 and run["jobs_scored"] == 1 and run["jobs_new"] == 1
    assert len(_saved_urls()) == 1

    # Nothing was marked seen, so the next run scores the other three.
    failing.clear()
    client.post("/api/search/run")
    assert len(_saved_urls()) == 4


def test_the_same_posting_from_another_source_is_saved_once(client, search_env, monkeypatch):
    def posting(source, url, company, title, description="Python"):
        job = raw(title=title, url=url)
        job.source, job.company, job.description = source, company, description
        return job

    board = posting("ashby", "https://jobs.ashbyhq.com/gjg/1", "Good Job Games",
                    "Backend Developer - New Grad", "Tam ilan metni. " * 50)
    # Another location of the same role on the same board is a second posting.
    board_2 = posting("ashby", "https://jobs.ashbyhq.com/gjg/2", "Good Job Games", "Backend Developer - New Grad")
    alert = posting("email", "https://www.linkedin.com/jobs/view/1", "Good Job Games Ltd.",
                    "Backend Developer (New Grad)")
    FakeSource.jobs = [alert, board, board_2]
    scored = []

    def score(profile, projects, jobs):
        scored.extend(j.url for j in jobs)
        return [JobScore(index=i, score=80, score_reason="iyi", seniority="junior") for i, _ in enumerate(jobs)]

    monkeypatch.setattr(service, "score_jobs", score)
    client.post("/api/search/run")
    assert _saved_urls() == ["https://jobs.ashbyhq.com/gjg/1", "https://jobs.ashbyhq.com/gjg/2"]

    # A later alert email with the same posting isn't scored or saved either.
    FakeSource.jobs = [posting("email", "https://www.linkedin.com/jobs/view/2", "Good Job Games",
                               "Backend Developer - New Grad")]
    client.post("/api/search/run")
    assert len(_saved_urls()) == 2 and "linkedin" not in " ".join(scored)


def test_posting_key_ignores_punctuation_case_and_legal_form():
    assert filters.posting_key("Ingenium Yazılım Limited Şirketi", "Yazılım Mühendisi") == \
        filters.posting_key("INGENIUM YAZILIM", "Yazilim Muhendisi")
    assert filters.posting_key("Peak", "Software Engineer, Games (New Grad)") != \
        filters.posting_key("Peak", "Software Engineer, Backend (New Grad)")
