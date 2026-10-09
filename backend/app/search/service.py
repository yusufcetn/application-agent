"""One job search run: fetch sources, filter, score and save in batches, build packages."""

import logging
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from app.config import get_settings
from app.db import JobRow, ProjectRow, SearchRunRow, SeenPostingRow, get_engine
from app.llm.runner import LLMError, LLMNotConfiguredError
from app.jobs.urls import normalize_url
from app.llm.score import BATCH_SIZE as SCORE_BATCH
from app.llm.score import score_jobs
from app.schemas import Profile, Project, SearchRun, SearchSettings, new_id
from app.search.filters import (
    COMPANY_BOARD_SOURCES,
    posting_key,
    prefilter,
    profile_keywords,
    relevance,
)
from app.search.report import send_run_report
from app.search.verify import Check, check_posting
from app.services.packages import generate_package, load_profile, load_search_settings
from app.sources.base import RawJob, make_client
from app.sources.registry import enabled_sources
from app.text import fold

logger = logging.getLogger(__name__)

_run_lock = threading.Lock()
# Packages are built one at a time in the background, while the run keeps going.
_packages = ThreadPoolExecutor(max_workers=1, thread_name_prefix="package")
# Sources that take minutes (an LLM agent browsing the web) are read beside the fast ones.
SLOW_SOURCES = {"web"}
# After this many failed scoring calls a run stops scoring (the LLM is likely out of quota);
# the postings left are scored next run.
MAX_SCORE_FAILURES = 2


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


# Saved postings are re-checked at most this often, and only this many pages per run.
RECHECK_AFTER = timedelta(hours=20)
MAX_PAGE_CHECKS = 40


def _fetch(sources: list, settings) -> tuple[list[RawJob], list[str], set[str]]:
    """Returns the postings, the error messages and the names of the sources that were read."""
    jobs, errors, read = [], [], set()
    for source in sources:
        try:
            found = source.fetch(settings)
            logger.info("%s: %d postings", source.name, len(found))
            jobs += found
            read.add(source.name)
        except Exception as e:  # one broken source shouldn't stop the run
            logger.warning("Source %s failed: %s", source.name, e)
            errors.append(f"{source.name}: {e}")
    return jobs, errors, read


def _apply_check(row: JobRow, check: Check, now: datetime, closed: list[str], reopened: list[str]) -> None:
    if check.deadline:
        row.application_deadline = check.deadline
    if check.status is None:
        if row.posting_status == "unknown":
            row.verification_reason = check.reason
        return
    if check.status == "closed" and row.posting_status != "closed":
        closed.append(row.id)
    if check.status == "open" and row.posting_status == "closed":
        reopened.append(row.id)
    row.posting_status = check.status
    row.verification_reason = check.reason
    row.last_verified_at = now


def _verify_saved(
    session: Session, raw: list[RawJob], fetched: set[str], now: datetime
) -> tuple[list[str], list[str]]:
    """Update posting_status of jobs still waiting for an application.
    Returns the ids that closed and the ids that reopened."""
    listed: dict[str, set[str]] = defaultdict(set)
    companies: dict[str, set[str]] = defaultdict(set)
    seen_open: dict[str, str] = {}
    for job in raw:
        url = normalize_url(job.url)
        if job.source in COMPANY_BOARD_SOURCES:
            listed[job.source].add(url)
            companies[job.source].add(fold(job.company))
        if job.posting_status == "open":
            seen_open[url] = job.verification_reason or "Kaynakta yayında."
    closed, reopened = [], []
    page_checks = 0
    rows = session.exec(select(JobRow).where(JobRow.status == "new")).all()
    never = datetime.min.replace(tzinfo=UTC)
    rows = sorted(rows, key=lambda r: r.last_verified_at or never)  # least recently checked first
    with make_client() as client:
        for row in rows:
            url = normalize_url(row.url)
            if url in seen_open:
                check = Check("open", seen_open[url])
            elif row.source in COMPANY_BOARD_SOURCES:
                # Only trust a missing posting when that company's board was read this run.
                if row.source not in fetched or fold(row.company) not in companies[row.source]:
                    continue
                check = Check("closed", "İlan şirketin ilan listesinden kalkmış.")
            elif row.source == "manual" and not row.url.startswith(("http://", "https://")):
                continue
            else:
                if row.last_verified_at and row.last_verified_at > now - RECHECK_AFTER:
                    continue
                if page_checks >= MAX_PAGE_CHECKS:
                    continue
                page_checks += 1
                check = check_posting(row.url, client)
            _apply_check(row, check, now, closed, reopened)
            session.add(row)
    return closed, reopened


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
    # The same posting from another source (a board, an alert email, a web search) comes with
    # another URL. Within one source the same title can be a second posting (another
    # location, a repost), so only copies from different sources are dropped. A closed
    # posting doesn't count: the company may have opened the role again.
    saved: dict[str, set[str]] = defaultdict(set)
    for company, title, source in session.exec(
        select(JobRow.company, JobRow.title, JobRow.source).where(JobRow.posting_status != "closed")
    ).all():
        saved[posting_key(company, title)].add(source)
    groups: dict[str, list[RawJob]] = defaultdict(list)
    for url, job in by_url.items():
        key = posting_key(job.company, job.title)
        if url in known or (saved[key] and job.source not in saved[key]):
            continue
        groups[key].append(job)
    # Within this run, keep the source with the fullest description (a board over an email snippet).
    fresh = []
    for group in groups.values():
        best = max(group, key=lambda j: len(j.description)).source
        fresh += [j for j in group if j.source == best]
    return fresh


def execute_run(run_id: str, send_report: bool = False) -> None:
    """`send_report` emails the daily report afterwards, if it is turned on in the settings."""
    if not _run_lock.acquire(blocking=False):
        return
    try:
        with Session(get_engine()) as session:
            run = session.get(SearchRunRow, run_id)
            _search(session, run)
            run.status = "done"
            run.finished_at = datetime.now(UTC)
            session.add(run)
            session.commit()
            if send_report and load_search_settings(session).daily_report:
                try:
                    send_run_report(session, run)
                except Exception as e:  # the search itself is done; don't lose it over email
                    logger.warning("Daily report was not sent: %s", e)
    except Exception as e:
        # Batches saved so far stay; closing the session dropped the unfinished one.
        logger.exception("Search run %s failed", run_id)
        _mark_failed(run_id, str(e))
    finally:
        _run_lock.release()


def _mark_failed(run_id: str, error: str) -> None:
    """In a fresh session, so a run is never left "running" whatever broke the first one."""
    for attempt in range(3):
        try:
            with Session(get_engine()) as session:
                run = session.get(SearchRunRow, run_id)
                run.status = "failed"
                run.error = error
                run.finished_at = datetime.now(UTC)
                session.add(run)
                session.commit()
                return
        except Exception:
            logger.exception("Could not mark search run %s as failed (attempt %d)", run_id, attempt + 1)
            time.sleep(2)


def _queue_package(job_id: str) -> None:
    _packages.submit(generate_package, job_id)


@dataclass
class _RunState:
    settings: SearchSettings
    profile: Profile
    projects: list[Project]
    keywords: set[str]
    budget: int  # postings that may still be scored this run
    new_ids: list[str] = field(default_factory=list)
    source_errors: list[str] = field(default_factory=list)
    score_errors: list[str] = field(default_factory=list)


def _search(session: Session, run: SearchRunRow) -> None:
    """Saves each scored batch as soon as it is done, so jobs show up while the run goes on.
    Slow sources (the web agent) are read beside the fast ones and scored when they finish."""
    config = get_settings()
    settings = load_search_settings(session)
    profile = load_profile(session)
    projects = [Project.model_validate(r.data) for r in session.exec(select(ProjectRow)).all()]
    state = _RunState(
        settings, profile, projects,
        profile_keywords(profile, projects, settings.target_roles),
        config.search_max_scored_per_run,
    )
    raw: list[RawJob] = []
    read: set[str] = set()

    def take(fetched: tuple[list[RawJob], list[str], set[str]]) -> None:
        jobs, source_errors, source_read = fetched
        raw.extend(jobs)
        state.source_errors.extend(source_errors)
        read.update(source_read)
        run.jobs_found = len(raw)
        _set_run_error(run, state)
        session.add(run)
        session.commit()
        _score_and_save(session, run, state, jobs)

    with make_client() as fast_client, make_client() as slow_client, ThreadPoolExecutor(1) as pool:
        fast = [s for s in enabled_sources(settings, fast_client) if s.name not in SLOW_SOURCES]
        slow = [s for s in enabled_sources(settings, slow_client) if s.name in SLOW_SOURCES]
        pending = pool.submit(_fetch, slow, settings) if slow else None
        take(_fetch(fast, settings))
        if pending:
            take(pending.result())
    sources = len(fast) + len(slow)
    if sources and len(state.source_errors) == sources:
        raise RuntimeError("Hiçbir kaynak okunamadı. " + " | ".join(state.source_errors))

    closed, reopened = _verify_saved(session, raw, read, datetime.now(UTC))
    run.jobs_closed = len(closed)
    run.summary = {"new": state.new_ids, "closed": closed, "reopened": reopened}


def _set_run_error(run: SearchRunRow, state: _RunState) -> None:
    parts = []
    if state.source_errors:
        parts.append("Bazı kaynaklar okunamadı: " + " | ".join(state.source_errors))
    if state.score_errors:
        parts.append(
            "Bazı ilanlar puanlanamadı, sonraki taramada denenecek: " + " | ".join(state.score_errors)
        )
    run.error = " — ".join(parts) or None


def _score_and_save(session: Session, run: SearchRunRow, state: _RunState, jobs: list[RawJob]) -> None:
    config = get_settings()
    settings = state.settings
    candidates = _dedupe_new(session, prefilter(jobs, settings, config.search_max_age_days))
    # Only the most promising postings get an LLM call: best keyword overlap, then newest.
    oldest = datetime.min.replace(tzinfo=UTC)
    candidates.sort(key=lambda j: (relevance(j, state.keywords), j.posted_at or oldest), reverse=True)
    # Alert-email postings are few and already chosen by the user, so they are never cut
    # by the cap.
    from_email = [j for j in candidates if j.source == "email"]
    others = [j for j in candidates if j.source != "email"]
    candidates = from_email + others[: max(0, state.budget - len(from_email))]
    state.budget -= len(candidates)
    logger.info(
        "%d postings found, %d new after filters, scoring %d",
        len(jobs), len(from_email) + len(others), len(candidates),
    )
    for start in range(0, len(candidates), SCORE_BATCH):
        if len(state.score_errors) >= MAX_SCORE_FAILURES:
            break
        batch = candidates[start : start + SCORE_BATCH]
        try:
            scores = score_jobs(state.profile, state.projects, batch)
        except LLMNotConfiguredError:
            raise
        except LLMError as e:
            # Nothing is marked seen, so these postings are scored again next run.
            logger.warning("Scoring %d postings failed: %s", len(batch), e)
            state.score_errors.append(str(e))
            _set_run_error(run, state)
            session.add(run)
            session.commit()
            continue
        now = datetime.now(UTC)
        to_package = []
        for job, score in zip(batch, scores):
            if score is None:
                logger.warning("No score returned for %s; will retry next run", job.url)
                continue
            wrong_level = (
                settings.seniority and score.seniority and score.seniority not in settings.seniority
            )
            if wrong_level or score.score < config.search_min_score_to_keep:
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
                employment_type=job.employment_type or score.employment_type,
                posted_at=job.posted_at,
                found_at=now,
                description=job.description,
                posting_status=job.posting_status,
                last_verified_at=now if job.posting_status != "unknown" else None,
                application_deadline=job.application_deadline,
                verification_reason=job.verification_reason,
                score=score.score,
                score_reason=score.score_reason,
            )
            run.jobs_new += 1
            state.new_ids.append(row.id)
            if score.score >= settings.min_score:
                run.jobs_above_threshold += 1
                if settings.auto_package:
                    row.package_status = "generating"
                    to_package.append(row.id)
            session.add(row)
        run.jobs_scored += len(batch)
        session.add(run)
        session.commit()
        for job_id in to_package:
            _queue_package(job_id)


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
        execute_run(run.id, send_report=True)
