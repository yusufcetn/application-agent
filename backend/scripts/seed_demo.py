"""Fill a database with demo data so the UI can be tested without any LLM.

Creates a profile, projects, settings, a finished search run and jobs in every state
(ready package with a real PDF, failed package, no package, applied, interview).

Use a separate data folder so real data is never touched:

    macOS/Linux:  DATA_DIR=../data-demo DATABASE_URL=sqlite:///../data-demo/app.db uv run python -m scripts.seed_demo
    Windows (PowerShell):
        $env:DATA_DIR="../data-demo"; $env:DATABASE_URL="sqlite:///../data-demo/app.db"
        uv run python -m scripts.seed_demo

Then start the backend with the same two variables set.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from app.config import ROOT_DIR, get_settings
from app.db import (
    JobRow,
    PackageRow,
    ProfileRow,
    ProjectRow,
    SearchRunRow,
    SettingsRow,
    get_engine,
    init_db,
)
from app.llm.tailor import PackageDraft, TailoredEducation, TailoredExperience, TailoredItem
from app.render.cv import html_to_pdf, render_cv_html
from app.schemas import Analysis, Answer, Package, Profile, Project
from app.services.packages import cv_pdf_path

EXAMPLES = ROOT_DIR / "contracts" / "examples"
NOW = datetime.now(UTC)


def load(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def job(id: str, **fields) -> JobRow:
    defaults = dict(
        source="lever",
        url=f"https://jobs.example.com/{id}",
        company="Örnek Firma",
        title="Backend Engineer",
        location="Remote (EMEA)",
        remote=True,
        seniority="mid",
        posted_at=NOW - timedelta(days=2),
        found_at=NOW - timedelta(hours=2),
        description=(
            "## About the role\nWe build Python and FastAPI services.\n\n"
            "## Requirements\n- 2+ years of Python\n- PostgreSQL, Docker\n- Kubernetes is a plus"
        ),
        status="new",
        package_status="none",
    )
    return JobRow(id=id, **{**defaults, **fields})


def main() -> None:
    config = get_settings()
    if "data-demo" not in str(config.data_dir) and "--force" not in sys.argv:
        sys.exit(
            f"DATA_DIR is {config.data_dir}. Use a separate demo folder (see the docstring) "
            "or pass --force."
        )
    init_db()
    with Session(get_engine()) as session:
        if session.exec(select(JobRow)).first() and "--force" not in sys.argv:
            sys.exit("This database already has jobs; pass --force to add demo data anyway.")

        profile = Profile.model_validate(load("profile"))
        profile.updated_at = NOW
        session.merge(ProfileRow(id=1, data=profile.model_dump(mode="json")))

        project = Project.model_validate(load("project"))
        side_project = Project(
            id="prj_2", name="Hava Durumu Botu", summary="Telegram botu.",
            bullets=["Telegram için hava durumu botu yazdım."], tech=["Go"],
        )
        for p in (project, side_project):
            session.merge(ProjectRow(id=p.id, data=p.model_dump(mode="json")))

        session.merge(SettingsRow(id=1, data=load("settings")))
        session.merge(
            SearchRunRow(
                id="run_demo", status="done", started_at=NOW - timedelta(hours=2),
                finished_at=NOW - timedelta(hours=2) + timedelta(minutes=3),
                jobs_found=57, jobs_new=5, jobs_above_threshold=2,
                error="Bazı kaynaklar okunamadı: remotive: timeout",
            )
        )

        jobs = [
            job("job_ready", score=82, package_status="ready",
                score_reason="Python/FastAPI deneyimi ve API projeleri güçlü eşleşiyor, Kubernetes eksik."),
            job("job_failed", source="email", company="Insider", title="Backend Developer (Python)",
                location="İstanbul, Türkiye (Hybrid)", remote=False,
                url="https://www.linkedin.com/jobs/view/4012345678", description="Easy Apply",
                score=74, score_reason="Başlık ve konum uygun; tam ilan metni yoktu.",
                package_status="failed",
                package_error="İlanın tam metni okunamadı. İlan metnini kopyalayıp ilana ekle, "
                              "sonra paketi yeniden oluştur."),
            job("job_none", source="remoteok", company="Mirantis", title="Software Engineer",
                score=68, score_reason="Kubernetes, Docker ve Go/Python deneyimi iyi örtüşüyor."),
            job("job_weak", source="arbeitnow", company="Reactive Markets", title="C++ Software Engineer",
                location="Remote, UK", score=15, seniority="mid",
                score_reason="UK merkezli olmak şart ve C++ deneyimi eksik."),
            job("job_applied", source="greenhouse", company="Trendyol", title="Python Developer",
                location="İstanbul", remote=False, score=76, status="applied",
                found_at=NOW - timedelta(days=3), notes="Başvurdum, İK'dan dönüş bekleniyor."),
            job("job_interview", source="ashby", company="Getir", title="Junior Backend Developer",
                location="Remote", score=91, status="interview", found_at=NOW - timedelta(days=6)),
            job("job_manual", source="manual", company="Papara", title="Software Engineer, Payments",
                location="İstanbul", remote=False, score=None, seniority=None,
                found_at=NOW - timedelta(minutes=20)),
        ]
        for j in jobs:
            session.merge(j)

        draft = PackageDraft(
            language="en",
            headline="Backend Developer",
            summary="Backend developer building scalable services with Python and FastAPI.",
            experience=[TailoredExperience(
                id=profile.experience[0].id, title="Backend Developer",
                bullets=["Rewrote the order service with FastAPI, cutting response time by 40%.",
                         "Reduced a reporting query from 3 minutes to 20 seconds with PostgreSQL tuning."])],
            projects=[TailoredItem(id=project.id, bullets=[
                "Built a crawler that collects job postings daily from ATS boards.",
                "Developed LLM-based fit scoring and CV tailoring."])],
            education=[TailoredEducation(id=profile.education[0].id, degree="BSc",
                                         field="Computer Engineering")],
            languages=["Turkish (Native)", "English (C1)"],
            skills=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
            score=82,
            score_reason="Python/FastAPI deneyimi ve API projeleri güçlü eşleşiyor, Kubernetes eksik.",
            matched_skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            missing_skills=["Kubernetes"],
            tips=["Mülakatta Kubernetes eksikliğini Docker deneyiminle dengeleyebilirsin.",
                  "Sipariş servisindeki %40 iyileşmeyi somut bir hikâye olarak hazırla."],
            cover_letter=(
                "Dear Örnek Firma Team,\n\nI'm applying for the Backend Engineer role. At Örnek "
                "Teknoloji I rewrote our order service with FastAPI and cut response time by 40%.\n\n"
                "Best regards,\nAd Soyad"
            ),
            answers=[
                Answer(question="Why do you want to work at Örnek Firma?",
                       answer="Your team builds the kind of Python services I enjoy most..."),
                Answer(question="Describe a project relevant to this role.",
                       answer="Application Agent: a FastAPI service that collects job postings..."),
                Answer(question="What is your notice period?",
                       answer="[Doldur: ör. \"Teklif sonrası X hafta içinde başlayabilirim.\"]"),
            ],
        )
        html_to_pdf(render_cv_html(profile, [project, side_project], draft), cv_pdf_path("job_ready"))
        package = Package(
            job_id="job_ready", generated_at=NOW - timedelta(hours=1),
            cv_pdf_url="/api/jobs/job_ready/cv.pdf", cv_language="en",
            cover_letter=draft.cover_letter, answers=draft.answers,
            analysis=Analysis(
                score=82, matched_skills=draft.matched_skills, missing_skills=draft.missing_skills,
                highlighted_projects=[project.id], highlighted_experience=[profile.experience[0].id],
                tips=draft.tips,
            ),
        )
        session.merge(PackageRow(
            job_id="job_ready",
            data={**package.model_dump(mode="json"), "tailored_cv": draft.model_dump(mode="json")},
        ))
        session.commit()
    print(f"Demo data written to {config.database_url} ({len(jobs)} jobs).")


if __name__ == "__main__":
    main()
