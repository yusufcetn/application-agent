import io

import pytest
from pypdf import PdfReader

from app.api import jobs as jobs_api
from app.jobs.fetch import html_to_text
from app.llm.job_extract import ExtractedJob
from app.llm.tailor import (
    PackageDraft,
    TailoredEducation,
    TailoredExperience,
    TailoredProject,
    TailoredSkills,
    _enforce_facts,
)
from app.render.cv import html_to_pdf, render_cv_html
from app.schemas import Answer, Link, Profile, Project
from app.services import packages as packages_service
from tests.conftest import load_example

JOB_URL = "https://jobs.lever.co/ornekfirma/123"


def make_draft(**overrides) -> PackageDraft:
    data = dict(
        language="tr",
        headline="Backend Geliştirici",
        summary="Python ile ölçeklenebilir servisler geliştiren geliştirici.",
        experience=[
            TailoredExperience(
                id="exp_1", title="Backend Geliştirici", bullets=["Sipariş servisini FastAPI ile yeniden yazdım."]
            )
        ],
        projects=[TailoredProject(id="prj_1", bullets=["İlan toplayan tarayıcı yazdım."])],
        education=[TailoredEducation(id="edu_1", degree="Lisans", field="Bilgisayar Mühendisliği")],
        languages=["Türkçe (Ana dil)", "İngilizce (C1)"],
        skills=TailoredSkills(languages=["Python"], frameworks=["FastAPI"]),
        score=82,
        score_reason="Python ve FastAPI deneyimi güçlü eşleşiyor.",
        matched_skills=["Python"],
        missing_skills=["Kubernetes"],
        tips=["Docker deneyimini öne çıkar."],
        cover_letter="Merhaba,\n\nBaşvurmak istiyorum.",
        answers=[Answer(question="Neden biz?", answer="Çünkü...")],
    )
    data.update(overrides)
    return PackageDraft(**data)


def profile_and_projects() -> tuple[Profile, list[Project]]:
    return Profile.model_validate(load_example("profile")), [
        Project.model_validate(load_example("project"))
    ]


# --- fact enforcement -------------------------------------------------------


def test_enforce_facts_drops_invented_data():
    profile, projects = profile_and_projects()
    draft = make_draft(
        experience=[TailoredExperience(id="exp_fake", title="CTO", bullets=["Google'da çalıştım."])],
        education=[TailoredEducation(id="edu_fake", degree="PhD")],
        projects=[TailoredProject(id="prj_fake", bullets=["x"]), TailoredProject(id="prj_1", bullets=["y"])],
        skills=TailoredSkills(languages=["python", "Kubernetes"], tools=["Docker", "Python"]),
        score=140,
    )
    _enforce_facts(draft, profile, projects)

    assert [e.id for e in draft.experience] == ["exp_1"]  # fake dropped, real one kept
    assert draft.experience[0].bullets == profile.experience[0].bullets
    assert draft.experience[0].title == profile.experience[0].title
    assert draft.education == []
    assert [p.id for p in draft.projects] == ["prj_1"]
    # unknown skill dropped, canonical casing, deduped across groups
    assert draft.skills == TailoredSkills(languages=["Python"], tools=["Docker"])
    assert draft.score == 100


# --- rendering --------------------------------------------------------------


def test_render_uses_profile_facts_and_tailored_wording(tmp_path):
    profile, projects = profile_and_projects()
    html = render_cv_html(profile, projects, make_draft())
    assert "Örnek Teknoloji A.Ş." in html  # company from the profile
    assert "Sipariş servisini FastAPI ile yeniden yazdım." in html  # tailored bullet
    assert "İş Deneyimi" in html and "Devam ediyor" in html  # Turkish labels, ongoing job

    en_draft = make_draft(
        language="en",
        experience=[TailoredExperience(id="exp_1", title="Backend Developer", bullets=["Rewrote it."])],
        projects=[TailoredProject(id="prj_1", name="Application Agent (Course Project)", bullets=["Built it."])],
        education=[
            TailoredEducation(id="edu_1", school="Örnek University", degree="BSc", field="Computer Engineering")
        ],
        languages=["Turkish (Native)", "English (C1)"],
        skills=TailoredSkills(languages=["Python"], tools=["Docker"]),
    )
    en_html = render_cv_html(profile, projects, en_draft)
    assert "Experience" in en_html and "Present" in en_html
    assert "Computer Engineering" in en_html and "Bilgisayar" not in en_html
    assert "Örnek University" in en_html and "Üniversitesi" not in en_html
    assert "Application Agent (Course Project)" in en_html
    assert "Frameworks" not in en_html  # empty skill groups are left out
    assert "<strong>Tools &amp; Technologies:</strong> Docker" in en_html
    assert "Turkish (Native)" in en_html
    assert "Örnek Teknoloji A.Ş." in en_html  # company names are never translated


def test_links_without_scheme_still_open():
    profile, projects = profile_and_projects()
    profile.links = [Link(label="Web", url="yusufcetin.dev"), Link(label="GitHub", url="https://github.com/u/")]
    html = render_cv_html(profile, projects, make_draft())
    assert '<a href="https://yusufcetin.dev">yusufcetin.dev</a>' in html
    assert '<a href="https://github.com/u/">github.com/u</a>' in html


def test_pdf_is_generated_with_turkish_text(tmp_path):
    profile, projects = profile_and_projects()
    out = tmp_path / "cv.pdf"
    html_to_pdf(render_cv_html(profile, projects, make_draft()), out)
    text = PdfReader(io.BytesIO(out.read_bytes())).pages[0].extract_text()
    assert "AD SOYAD" in text
    assert "Sipariş" in text


# --- fetching ---------------------------------------------------------------


def test_html_to_text_keeps_json_ld_and_drops_noise():
    html = """<html><head><title>Backend Engineer - Örnek</title>
    <script type="application/ld+json">{"@type": "JobPosting", "title": "Backend Engineer"}</script>
    <script>var tracking = 1;</script></head>
    <body><nav>Menu</nav><h1>Backend Engineer</h1><p>Python ile çalışacaksın.</p></body></html>"""
    text = html_to_text(html)
    assert "Page title: Backend Engineer - Örnek" in text
    assert '"@type": "JobPosting"' in text
    assert "Python ile çalışacaksın." in text
    assert "tracking" not in text and "Menu" not in text


def test_normalize_url_strips_tracking():
    assert (
        jobs_api.normalize_url("HTTPS://Jobs.Lever.co/ornekfirma/123/?utm_source=x&lever-via=y#apply")
        == "https://jobs.lever.co/ornekfirma/123?lever-via=y"
    )


# --- API flow ---------------------------------------------------------------


@pytest.fixture
def fake_llm(monkeypatch):
    extracted = ExtractedJob(
        is_job_posting=True,
        company="Örnek Firma",
        title="Backend Engineer",
        location="Remote (EMEA)",
        remote=True,
        seniority="mid",
        posted_at="2026-09-20",
        language="en",
        description="## About the role\nPython and FastAPI.",
    )
    state = {"extracted": extracted, "fetched": []}

    def fake_fetch(url):
        state["fetched"].append(url)
        return "page text"

    monkeypatch.setattr(jobs_api, "fetch_posting_text", fake_fetch)
    monkeypatch.setattr(jobs_api, "extract_job", lambda text, url: state["extracted"])
    def fake_tailor(profile, projects, job, cv_language):
        draft = make_draft()
        _enforce_facts(draft, profile, projects)
        return draft

    monkeypatch.setattr(packages_service, "tailor_package", fake_tailor)
    return state


def save_profile_and_project(client):
    client.put("/api/profile", json=load_example("profile"))
    project = load_example("project")
    del project["id"]
    return client.post("/api/projects", json=project).json()["id"]


def test_manual_job_to_ready_package(client, fake_llm, monkeypatch):
    project_id = save_profile_and_project(client)
    monkeypatch.setattr(
        packages_service,
        "tailor_package",
        lambda *a: make_draft(projects=[TailoredProject(id=project_id, bullets=["İlan toplayan tarayıcı."])]),
    )

    res = client.post("/api/jobs/manual", json={"url": JOB_URL + "?utm_source=linkedin"})
    assert res.status_code == 201, res.text
    job = res.json()
    assert job["url"] == JOB_URL
    assert job["posted_at"] == "2026-09-20T00:00:00Z"
    assert job["package_status"] == "generating"

    # TestClient runs background tasks before returning, so the package is done now.
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["package_status"] == "ready"
    assert job["score"] == 82

    package = client.get(f"/api/jobs/{job['id']}/package").json()
    assert package["cv_pdf_url"] == f"/api/jobs/{job['id']}/cv.pdf"
    assert package["analysis"]["highlighted_projects"] == [project_id]
    assert "tailored_cv" not in package

    pdf = client.get(package["cv_pdf_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline")  # previewable in an iframe
    assert pdf.headers["cache-control"] == "no-cache"  # regeneration rewrites it at the same URL
    assert pdf.content.startswith(b"%PDF")


def test_same_url_returns_existing_job(client, fake_llm):
    first = client.post("/api/jobs/manual", json={"url": JOB_URL})
    again = client.post("/api/jobs/manual", json={"url": JOB_URL + "/?utm_medium=x"})
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len(fake_llm["fetched"]) == 1


def test_pasted_text_skips_fetching(client, fake_llm):
    res = client.post("/api/jobs/manual", json={"url": JOB_URL, "text": "pasted posting"})
    assert res.status_code == 201
    assert fake_llm["fetched"] == []


def test_text_only_manual_job(client, fake_llm):
    res = client.post("/api/jobs/manual", json={"text": "sadece metin ile ilan"})
    assert res.status_code == 201
    job = res.json()
    assert job["url"].startswith("manual:job_")
    assert job["source"] == "manual"
    assert fake_llm["fetched"] == []


def test_manual_job_requires_url_or_text(client, fake_llm):
    res = client.post("/api/jobs/manual", json={})
    assert res.status_code == 422
    assert "İlan bağlantısı veya ilan metni girmelisiniz" in res.json()["detail"]


def test_non_posting_page_is_rejected(client, fake_llm):
    fake_llm["extracted"] = fake_llm["extracted"].model_copy(update={"is_job_posting": False})
    res = client.post("/api/jobs/manual", json={"url": JOB_URL})
    assert res.status_code == 422
    assert client.get("/api/jobs").json() == []


def test_without_profile_job_is_added_but_not_packaged(client, fake_llm):
    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()
    assert job["package_status"] == "none"
    assert client.post(f"/api/jobs/{job['id']}/package").status_code == 409
    assert client.get(f"/api/jobs/{job['id']}/package").status_code == 404


def test_failed_generation_marks_job_failed(client, fake_llm, monkeypatch):
    save_profile_and_project(client)

    def boom(*a):
        raise RuntimeError("CLI crashed")

    monkeypatch.setattr(packages_service, "tailor_package", boom)
    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()
    assert client.get(f"/api/jobs/{job['id']}").json()["package_status"] == "failed"


def test_list_filter_and_patch(client, fake_llm):
    save_profile_and_project(client)
    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()

    listed = client.get("/api/jobs").json()
    assert [j["id"] for j in listed] == [job["id"]]
    assert listed[0]["description"] == ""  # list stays light
    assert client.get("/api/jobs", params={"min_score": 90}).json() == []
    assert client.get("/api/jobs", params={"q": "örnek"}).json() != []
    assert client.get("/api/jobs", params={"q": "ÖRNEK FİRMA"}).json() != []
    assert client.get("/api/jobs", params={"q": "frontend"}).json() == []

    patched = client.patch(f"/api/jobs/{job['id']}", json={"status": "applied", "notes": "Gönderdim"})
    assert patched.json()["status"] == "applied"
    assert client.get("/api/jobs", params={"status": ["new"]}).json() == []
    assert len(client.get("/api/jobs", params={"status": ["applied", "interview"]}).json()) == 1


def test_opening_a_job_marks_it_seen_once(client, fake_llm):
    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()
    assert job["seen_at"] is None

    first = client.patch(f"/api/jobs/{job['id']}", json={"seen": True}).json()["seen_at"]
    assert first
    # Opening it again keeps the first time; status and notes are untouched.
    again = client.patch(f"/api/jobs/{job['id']}", json={"seen": True}).json()
    assert again["seen_at"] == first and again["status"] == "new"
    assert client.get("/api/jobs").json()[0]["seen_at"] == first

    assert client.patch(f"/api/jobs/{job['id']}", json={"seen": False}).json()["seen_at"] is None


def test_delete_job_removes_package_and_keeps_posting_away(client, fake_llm):
    from sqlmodel import Session

    from app.db import JobRow, SeenPostingRow, get_engine
    from app.search.service import _dedupe_new
    from app.sources.base import RawJob

    save_profile_and_project(client)
    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()
    pdf_dir = packages_service.cv_pdf_path(job["id"]).parent
    assert pdf_dir.exists()

    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404
    assert client.get("/api/jobs").json() == []
    assert not pdf_dir.exists()
    with Session(get_engine()) as session:
        assert session.get(SeenPostingRow, JOB_URL)
        raw = RawJob(
            source="lever", url=JOB_URL, company="Örnek Firma", title="Backend Engineer",
            location=None, remote=True, posted_at=None, description="",
        )
        assert _dedupe_new(session, [raw]) == []
        assert session.get(JobRow, job["id"]) is None

    # Adding it again by hand still works.
    assert client.post("/api/jobs/manual", json={"url": JOB_URL}).status_code == 201
    assert client.delete("/api/jobs/job_missing").status_code == 404


def test_job_cannot_be_deleted_while_package_is_generating(client, fake_llm):
    from sqlmodel import Session

    from app.db import JobRow, get_engine

    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()
    with Session(get_engine()) as session:
        row = session.get(JobRow, job["id"])
        row.package_status = "generating"
        session.add(row)
        session.commit()
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 409
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200


def test_snippet_job_without_readable_page_explains_failure(client, fake_llm, monkeypatch):
    from sqlmodel import Session

    from app.db import JobRow, get_engine
    from app.jobs.fetch import FetchError

    save_profile_and_project(client)
    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()
    with Session(get_engine()) as session:  # pretend it came from an alert email
        row = session.get(JobRow, job["id"])
        row.source, row.description = "email", "Easy Apply"
        session.add(row)
        session.commit()

    def blocked(url):
        raise FetchError("authwall")

    monkeypatch.setattr(packages_service, "fetch_posting_text", blocked)
    client.post(f"/api/jobs/{job['id']}/package")
    failed = client.get(f"/api/jobs/{job['id']}").json()
    assert failed["package_status"] == "failed"
    assert "metnini" in failed["package_error"]

    # The user pastes the posting; the next attempt uses it and doesn't fetch again.
    client.patch(f"/api/jobs/{job['id']}", json={"description": "Short but pasted posting."})
    client.post(f"/api/jobs/{job['id']}/package")
    ready = client.get(f"/api/jobs/{job['id']}").json()
    assert ready["package_status"] == "ready" and ready["package_error"] is None
    assert ready["description"] == "Short but pasted posting."


def test_old_database_gets_new_columns(tmp_path):
    import sqlite3

    from sqlmodel import create_engine

    from app.db import _add_missing_columns

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE job (id VARCHAR PRIMARY KEY, title VARCHAR)")
        conn.execute("INSERT INTO job VALUES ('job_1', 'Eski ilan')")
    _add_missing_columns(create_engine(f"sqlite:///{path}"))
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(job)")}
        assert {"package_error", "description_pasted", "posting_status"} <= columns
        # Existing rows get the column default, so they still validate as jobs.
        assert conn.execute("SELECT title, posting_status FROM job").fetchone() == ("Eski ilan", "unknown")


def test_building_a_package_does_not_lock_the_database_while_the_llm_works(client, fake_llm, monkeypatch):
    import sqlite3
    from datetime import UTC, datetime

    from sqlmodel import Session

    from app.config import get_settings
    from app.db import JobRow, get_engine

    save_profile_and_project(client)
    with Session(get_engine()) as session:
        # An alert-email posting with only a snippet: its full page is fetched and stored first.
        session.add(JobRow(id="job_mail", source="email", url=JOB_URL, company="Örnek Firma",
                           title="Backend Engineer", found_at=datetime.now(UTC), description="kısa",
                           package_status="generating"))
        session.commit()
    monkeypatch.setattr(packages_service, "fetch_posting_text", lambda url: "Tam ilan metni. " * 200)
    database = get_settings().database_url.removeprefix("sqlite:///")

    def tailor(profile, projects, job, cv_language):
        # A search run saving jobs right now must get the write lock without waiting.
        other = sqlite3.connect(database, timeout=0)
        other.execute("BEGIN IMMEDIATE")
        other.rollback()
        other.close()
        draft = make_draft()
        _enforce_facts(draft, profile, projects)
        return draft

    monkeypatch.setattr(packages_service, "tailor_package", tailor)
    packages_service.generate_package("job_mail")
    job = client.get("/api/jobs/job_mail").json()
    assert job["package_status"] == "ready", job["package_error"]
    assert job["description"].startswith("Tam ilan metni.")


def test_profile_and_project_changes_print_ready_cvs_again(client, fake_llm, monkeypatch):
    project_id = save_profile_and_project(client)
    monkeypatch.setattr(
        packages_service,
        "tailor_package",
        lambda *a: make_draft(projects=[TailoredProject(id=project_id, bullets=["İlan toplayan tarayıcı."])]),
    )
    printed = {}
    monkeypatch.setattr(packages_service, "html_to_pdf", lambda html, path: printed.__setitem__(path, html))
    job = client.post("/api/jobs/manual", json={"url": JOB_URL}).json()
    path = packages_service.cv_pdf_path(job["id"])
    assert "yusufcetin.dev" not in printed[path]

    profile = load_example("profile")
    profile["links"].append({"label": "Web", "url": "yusufcetin.dev"})
    client.put("/api/profile", json=profile)
    assert '<a href="https://yusufcetin.dev">' in printed[path]
    assert "Sipariş servisini FastAPI ile yeniden yazdım." in printed[path]  # tailored wording stays

    project = client.get("/api/projects").json()[0]
    client.put(f"/api/projects/{project_id}", json={**project, "name": "Yeni Proje Adı"})
    assert "Yeni Proje Adı" in printed[path]
    client.delete(f"/api/projects/{project_id}")
    assert "Yeni Proje Adı" not in printed[path]  # a deleted project leaves the CV, no error


def test_packages_from_before_grouped_skills_print_again():
    profile, _ = profile_and_projects()
    data = make_draft().model_dump(mode="json")
    data["skills"] = ["Python", "FastAPI", "Docker", "Kubernetes"]
    draft = packages_service._saved_draft(data, profile)
    assert draft.skills.languages == ["Python"]
    assert draft.skills.frameworks == ["FastAPI"]
    assert draft.skills.tools == ["Docker", "Kubernetes"]
