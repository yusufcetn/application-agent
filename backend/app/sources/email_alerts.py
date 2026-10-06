"""Job alert emails (LinkedIn, Kariyer.net, ...) read over IMAP.

Only the mailbox is read; job sites are not crawled. The full posting page is opened
later, once, if a package is generated for that job.
"""

import email
import imaplib
import logging
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from sqlmodel import Session, select

from app.config import get_settings
from app.db import SeenPostingRow, get_engine
from app.llm.alert_extract import extract_alert_jobs
from app.schemas import SearchSettings
from app.sources.base import JobSource, RawJob, looks_remote

logger = logging.getLogger(__name__)

MAX_EMAIL_CHARS = 30_000
MAX_EMAILS_PER_RUN = 20


def email_to_text(msg: EmailMessage) -> str:
    """Email body as text, with each link kept as "text [URL]" so the LLM can see it."""
    html_part = msg.get_body(preferencelist=("html",))
    if html_part is not None:
        soup = BeautifulSoup(html_part.get_content(), "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            a.replace_with(f" {label} [{a['href']}] " if label else f" [{a['href']}] ")
        lines = [line.strip() for line in soup.get_text("\n").splitlines()]
        text = "\n".join(line for line in lines if line)
    else:
        plain = msg.get_body(preferencelist=("plain",))
        text = plain.get_content() if plain is not None else ""
    subject = msg.get("Subject", "")
    return f"Subject: {subject}\n\n{text}"[:MAX_EMAIL_CHARS]


def _message_date(msg: EmailMessage) -> datetime | None:
    try:
        return parsedate_to_datetime(msg["Date"]).astimezone(UTC)
    except (TypeError, ValueError):
        return None


class EmailAlertSource(JobSource):
    name = "email"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        config = get_settings()
        if not (config.imap_user and config.imap_password):
            raise RuntimeError("IMAP_USER / IMAP_PASSWORD ayarlanmamış (.env).")

        jobs: list[RawJob] = []
        with Session(get_engine()) as session:
            for msg in self._new_messages(session):
                received = _message_date(msg)
                for job in extract_alert_jobs(email_to_text(msg)):
                    jobs.append(
                        RawJob(
                            source=self.name,
                            url=self._resolve(job.url),
                            company=job.company,
                            title=job.title,
                            location=job.location,
                            remote=looks_remote(job.location, job.snippet),
                            posted_at=received,
                            description=job.snippet or "",
                        )
                    )
                # Mark the email read for us only after its jobs were extracted.
                session.add(SeenPostingRow(url=f"email:{msg['Message-ID']}", seen_at=datetime.now(UTC)))
                session.commit()
        return jobs

    def _new_messages(self, session: Session) -> list[EmailMessage]:
        config = get_settings()
        since = (datetime.now(UTC) - timedelta(days=config.email_lookback_days)).strftime("%d-%b-%Y")
        messages: dict[str, EmailMessage] = {}
        imap = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
        try:
            imap.login(config.imap_user, config.imap_password)
            imap.select(config.imap_folder, readonly=True)  # never marks mails as read
            for sender in config.email_alert_senders:
                _, data = imap.search(None, "SINCE", since, "FROM", f'"{sender}"')
                for num in data[0].split():
                    _, parts = imap.fetch(num, "(BODY.PEEK[])")
                    raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                    if not raw:
                        continue
                    msg = email.message_from_bytes(raw, policy=default_policy)
                    msg_id = msg.get("Message-ID")
                    if msg_id and msg_id not in messages:
                        messages[msg_id] = msg
        finally:
            try:
                imap.logout()
            except imaplib.IMAP4.error:
                pass

        seen = set(
            session.exec(
                select(SeenPostingRow.url).where(
                    SeenPostingRow.url.in_([f"email:{m}" for m in messages])
                )
            ).all()
        )
        new = [m for mid, m in messages.items() if f"email:{mid}" not in seen]
        new.sort(key=lambda m: _message_date(m) or datetime.min.replace(tzinfo=UTC), reverse=True)
        logger.info("%d alert emails, %d new", len(messages), len(new))
        return new[:MAX_EMAILS_PER_RUN]

    def _resolve(self, url: str) -> str:
        """Alert links often go through click trackers; follow them to the real posting."""
        if "linkedin.com" in url:
            return url  # LinkedIn links carry the job id; normalize_url cleans them
        try:
            return str(self.client.head(url, follow_redirects=True).url)
        except Exception:
            return url
