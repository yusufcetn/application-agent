"""Build an application package for a job: tailored CV (PDF), cover letter, answers."""

import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from app.config import get_settings
from app.db import JobRow, PackageRow, ProfileRow, ProjectRow, SettingsRow, get_engine
from app.jobs.fetch import FetchError, fetch_posting_text
from app.llm.runner import LLMError
from app.llm.tailor import PackageDraft, tailor_package
from app.render.cv import html_to_pdf, render_cv_html
from app.schemas import Analysis, Job, Package, Profile, Project, SearchSettings

logger = logging.getLogger(__name__)

# These sources only give a snippet; the CV needs the whole posting.
SNIPPET_SOURCES = {"adzuna", "email", "web"}
MIN_DESCRIPTION_CHARS = 1500


class PackageError(RuntimeError):
    """A failure with a message that is safe and useful to show the user."""


def cv_pdf_path(job_id: str) -> Path:
    return get_settings().data_dir / "packages" / job_id / "cv.pdf"


def load_profile(session: Session) -> Profile:
    row = session.get(ProfileRow, 1)
    return Profile.model_validate(row.data) if row else Profile()


def load_search_settings(session: Session) -> SearchSettings:
    row = session.get(SettingsRow, 1)
    return SearchSettings.model_validate(row.data) if row else SearchSettings()


def generate_package(job_id: str) -> None:
    """Runs in the background; the job's package_status is already 'generating'."""
    # No autoflush: changes wait for the final commit, so the database isn't held locked
    # while the LLM works (a search run may be saving jobs at the same time).
    with Session(get_engine(), autoflush=False) as session:
        job_row = session.get(JobRow, job_id)
        if not job_row:
            return
        try:
            profile = load_profile(session)
            projects = [
                Project.model_validate(r.data) for r in session.exec(select(ProjectRow)).all()
            ]
            if (
                job_row.source in SNIPPET_SOURCES
                and not job_row.description_pasted
                and len(job_row.description) < MIN_DESCRIPTION_CHARS
            ):
                try:
                    job_row.description = fetch_posting_text(job_row.url)
                except FetchError as e:
                    raise PackageError(
                        "İlanın tam metni okunamadı. İlan metnini kopyalayıp ilana ekle, "
                        "sonra paketi yeniden oluştur."
                    ) from e
            job = Job.model_validate(job_row, from_attributes=True)
            cv_language = load_search_settings(session).cv_language

            draft = tailor_package(profile, projects, job, cv_language)
            html_to_pdf(render_cv_html(profile, projects, draft), cv_pdf_path(job_id))

            package = Package(
                job_id=job_id,
                generated_at=datetime.now(UTC),
                cv_pdf_url=f"/api/jobs/{job_id}/cv.pdf",
                cv_language=draft.language,
                cover_letter=draft.cover_letter,
                answers=draft.answers,
                analysis=Analysis(
                    score=draft.score,
                    matched_skills=draft.matched_skills,
                    missing_skills=draft.missing_skills,
                    highlighted_projects=[p.id for p in draft.projects],
                    highlighted_experience=[e.id for e in draft.experience],
                    tips=draft.tips,
                ),
            )
            data = {**package.model_dump(mode="json"), "tailored_cv": draft.model_dump(mode="json")}
            row = session.get(PackageRow, job_id) or PackageRow(job_id=job_id, data={})
            row.data = data
            session.add(row)

            job_row.score = draft.score
            job_row.score_reason = draft.score_reason
            job_row.package_status = "ready"
            job_row.package_error = None
        except (PackageError, LLMError) as e:
            logger.warning("Package generation failed for job %s: %s", job_id, e)
            job_row.package_status = "failed"
            job_row.package_error = str(e)
        except Exception:
            logger.exception("Package generation failed for job %s", job_id)
            job_row.package_status = "failed"
            job_row.package_error = "Beklenmeyen bir hata oluştu, tekrar dene."
        session.add(job_row)
        session.commit()


def _saved_draft(data: dict, profile: Profile) -> PackageDraft:
    data = dict(data)
    if isinstance(data.get("skills"), list):
        # Packages from before skills were grouped: group them as the profile does.
        languages = {s.casefold() for s in profile.skills.languages}
        frameworks = {s.casefold() for s in profile.skills.frameworks}
        flat = data["skills"]
        data["skills"] = {
            "languages": [s for s in flat if s.casefold() in languages],
            "frameworks": [s for s in flat if s.casefold() in frameworks],
            "tools": [s for s in flat if s.casefold() not in languages | frameworks],
        }
    return PackageDraft.model_validate(data)


def _rerender_once() -> None:
    with Session(get_engine()) as session:
        profile = load_profile(session)
        projects = [Project.model_validate(r.data) for r in session.exec(select(ProjectRow)).all()]
        job_ids = session.exec(select(JobRow.id).where(JobRow.package_status == "ready")).all()
    for job_id in job_ids:
        with Session(get_engine()) as session:
            job = session.get(JobRow, job_id)
            package = session.get(PackageRow, job_id)
            # Checked again per job: one may be regenerating by now and write its own PDF.
            if not job or job.package_status != "ready" or not package:
                continue
            data = package.data.get("tailored_cv")
        if not data:
            continue
        try:
            draft = _saved_draft(data, profile)
            html_to_pdf(render_cv_html(profile, projects, draft), cv_pdf_path(job_id))
        except Exception:
            logger.exception("CV of job %s could not be rendered again", job_id)


_rerender_lock = threading.Lock()
_rerender_wanted = False


def rerender_cvs() -> None:
    """Print the ready CVs again with the current profile and projects, so contact details
    and links stay current. The tailored wording is kept; only regenerating a package
    rewrites it. Saves that come while a pass runs are covered by one more pass."""
    global _rerender_wanted
    _rerender_wanted = True
    while _rerender_wanted and _rerender_lock.acquire(blocking=False):
        try:
            while _rerender_wanted:
                _rerender_wanted = False
                _rerender_once()
        finally:
            _rerender_lock.release()


def reset_interrupted_packages() -> None:
    """Packages that were generating when the server stopped will never finish."""
    with Session(get_engine()) as session:
        for row in session.exec(select(JobRow).where(JobRow.package_status == "generating")):
            row.package_status = "failed"
            row.package_error = "Sunucu paket hazırlanırken yeniden başladı, tekrar dene."
            session.add(row)
        session.commit()
