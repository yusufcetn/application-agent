"""One job search run: fetch sources, filter, score, save, then build packages."""

import logging
import threading
from datetime import UTC, datetime

from sqlmodel import Session, col, select

from app.config import get_settings
from app.db import JobRow, ProjectRow, SearchRunRow, SeenPostingRow, get_engine
from app.jobs.urls import normalize_url
from app.llm.score import score_jobs
from app.schemas import Project, SearchRun, new_id
from app.search.filters import prefilter, profile_keywords, relevance
from app.services.packages import generate_package, load_profile, load_search_settings
from app.sources.base import RawJob, make_client
from app.sources.registry import enabled_sources

logger = logging.getLogger(__name__)

_run_lock = threading.Lock()


class ProfileMissingError(RuntimeError):
    pass


def to_search_run(row: SearchRunRow) -> SearchRun:
    return SearchRun.model_validate(row, from_attributes=True)


def start_run() -> tuple[SearchRun, bool]:
    """Create a run unless one is already going. Returns (run, created)."""
    with Session(get_engine()) as session:
        running = session.exec(
            select(SearchRunRow).where(SearchRunRow.status == "running")
        ).first()
        if running:
            return to_search_run(running), False
        if not load_profile(session).full_name:
            raise ProfileMissingError("İlan taramak için önce profilini doldur.")
        row = SearchRunRow(id=new_id("run"), status="running", started_at=datetime.now(UTC))
        session.add(row)
        session.commit()
        return to_search_run(row), True


def _fetch_all(settings) -> tuple[list[RawJob], list[str]]:
    jobs, errors = [], []
    with make_client() as client:
        sources = enabled_sources(settings, client)
        for source in sources:
            try:
                found = source.fetch(settings)
                logger.info("%s: %d postings", source.name, len(found))
                jobs += found
            except Exception as e:  # one broken source shouldn't stop the run
                logger.warning("Source %s failed: %s", source.name, e)
                errors.append(f"{source.name}: {e}")
    if sources and len(errors) == len(sources):
        raise RuntimeError("Hiçbir kaynak okunamadı. " + " | ".join(errors))
    return jobs, errors


def _dedupe_new(session: Session, jobs: list[RawJob]) -> list[RawJob]:
    by_url: dict[str, RawJob] = {}
    for job in jobs:
        job.url = normalize_url(job.url)
        by_url.setdefault(job.url, job)
    urls = list(by_url)
    known = set(session.exec(select(JobRow.url).where(col(JobRow.url).in_(urls))).all())
    known |= set(
        session.exec(select(SeenPostingRow.url).where(col(SeenPostingRow.url).in_(urls))).all()
    )
    return [j for url, j in by_url.items() if url not in known]


def execute_run(run_id: str) -> None:
    if not _run_lock.acquire(blocking=False):
        return
    to_package: list[str] = []
    try:
        with Session(get_engine()) as session:
            run = session.get(SearchRunRow, run_id)
            try:
                to_package = _search(session, run)
                run.status = "done"
            except Exception as e:
                logger.exception("Search run %s failed", run_id)
                run.status = "failed"
                run.error = str(e)
            run.finished_at = datetime.now(UTC)
            session.add(run)
            session.commit()
        # The run counts as done once jobs are saved; packages keep going afterwards.
        for job_id in to_package:
            generate_package(job_id)
    finally:
        _run_lock.release()


def _search(session: Session, run: SearchRunRow) -> list[str]:
    config = get_settings()
    settings = load_search_settings(session)
    profile = load_profile(session)
    projects = [Project.model_validate(r.data) for r in session.exec(select(ProjectRow)).all()]

    raw, errors = _fetch_all(settings)
    run.jobs_found = len(raw)
    if errors:
        run.error = "Bazı kaynaklar okunamadı: " + " | ".join(errors)

    candidates = _dedupe_new(session, prefilter(raw, settings, config.search_max_age_days))
    # Only the most promising postings get an LLM call: best keyword overlap, then newest.
    keywords = profile_keywords(profile, projects, settings.target_roles)
    oldest = datetime.min.replace(tzinfo=UTC)
    candidates.sort(key=lambda j: (relevance(j, keywords), j.posted_at or oldest), reverse=True)
    # Alert-email postings are few and already chosen by the user; an email is read only
    # once, so they are never cut by the cap.
    from_email = [j for j in candidates if j.source == "email"]
    others = [j for j in candidates if j.source != "email"]
    candidates = from_email + others[: max(0, config.search_max_scored_per_run - len(from_email))]
    logger.info(
        "%d postings found, %d new after filters, scoring %d",
        len(raw), len(from_email) + len(others), len(candidates),
    )

    scores = score_jobs(profile, projects, candidates) if candidates else []
    now = datetime.now(UTC)
    to_package = []
    for job, score in zip(candidates, scores):
        if score is None:
            logger.warning("No score returned for %s; will retry next run", job.url)
            continue
        if settings.seniority and score.seniority and score.seniority not in settings.seniority:
            session.add(SeenPostingRow(url=job.url, seen_at=now))
            continue
        row = JobRow(
            id=new_id("job"),
            source=job.source,
            url=job.url,
            company=job.company,
            title=job.title,
            location=job.location,
            remote=job.remote,
            seniority=score.seniority,
            posted_at=job.posted_at,
            found_at=now,
            description=job.description,
            score=score.score,
            score_reason=score.score_reason,
        )
        run.jobs_new += 1
        if score.score >= settings.min_score:
            run.jobs_above_threshold += 1
            if settings.auto_package:
                row.package_status = "generating"
                to_package.append(row.id)
        session.add(row)
    return to_package


def fail_interrupted_runs() -> None:
    with Session(get_engine()) as session:
        for row in session.exec(select(SearchRunRow).where(SearchRunRow.status == "running")):
            row.status = "failed"
            row.error = "Sunucu tarama sırasında yeniden başladı."
            row.finished_at = datetime.now(UTC)
            session.add(row)
        session.commit()


def run_scheduled_search() -> None:
    try:
        run, created = start_run()
    except ProfileMissingError:
        logger.info("Scheduled search skipped: profile is empty")
        return
    if created:
        execute_run(run.id)
