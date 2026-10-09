"""Postings an LLM agent found by searching the web (see app.llm.web_discovery)."""

import logging
from datetime import UTC, datetime, time

from sqlmodel import Session

from app.db import get_engine
from app.llm.web_discovery import discover_postings, parse_day
from app.schemas import SearchSettings
from app.services.packages import load_profile
from app.sources.base import JobSource, RawJob, looks_remote

logger = logging.getLogger(__name__)


class WebSearchSource(JobSource):
    name = "web"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        with Session(get_engine()) as session:
            profile = load_profile(session)
        found = discover_postings(settings, profile, self.client)
        logger.info("Web searches: %s", " | ".join(found.queries))
        jobs = []
        for p in found.postings:
            # Search results are often stale; only postings shown to take applications count.
            if p.status != "open":
                continue
            posted = parse_day(p.posted_at)
            jobs.append(
                RawJob(
                    source=self.name,
                    url=p.url,
                    company=p.company.strip(),
                    title=p.title.strip(),
                    location=p.location,
                    remote=p.remote if p.remote is not None else looks_remote(p.location),
                    posted_at=datetime.combine(posted, time.min, UTC) if posted else None,
                    description=p.description,
                    employment_type=p.employment_type,
                    posting_status=p.status,
                    verification_reason=p.evidence,
                    application_deadline=parse_day(p.application_deadline),
                )
            )
        return jobs
