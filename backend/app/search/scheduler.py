"""Daily search on the cron expression from the settings (only while the server runs)."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.search.service import run_scheduled_search

logger = logging.getLogger(__name__)

JOB_ID = "daily-search"
_scheduler: BackgroundScheduler | None = None


def parse_cron(expr: str) -> CronTrigger:
    """Raises ValueError for an invalid expression."""
    return CronTrigger.from_crontab(expr)


def start(cron: str) -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    reschedule(cron)


def reschedule(cron: str) -> None:
    if not _scheduler:
        return
    _scheduler.add_job(
        run_scheduled_search,
        parse_cron(cron),
        id=JOB_ID,
        replace_existing=True,
        coalesce=True,
        # If the computer was asleep at the scheduled time, still run once within 12 hours.
        misfire_grace_time=12 * 3600,
        max_instances=1,
    )
    logger.info("Daily search scheduled: %s", cron)


def shutdown() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
