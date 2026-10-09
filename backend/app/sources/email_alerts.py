"""Job alert emails (LinkedIn, Kariyer.net, ...) read over IMAP.

Only the mailbox is read; job sites are not crawled. The full posting page is opened
later, once, if a package is generated for that job.
"""

import email
import imaplib
import logging
import re
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from sqlmodel import Session, col, delete, select

from app.config import get_settings
from app.db import AlertEmailRow, AlertPostingRow, get_engine
from app.jobs.urls import normalize_url
from app.llm.alert_extract import extract_alert_jobs
from app.llm.runner import LLMError
from app.schemas import SearchSettings
from app.sources.base import JobSource, RawJob, looks_remote

logger = logging.getLogger(__name__)

MAX_EMAIL_CHARS = 30_000
MAX_EMAILS_PER_RUN = 20
FORGET_MARGIN_DAYS = 2
_URL = re.compile(r"https?://[^\s<>\"')\]]+")


def email_to_text(msg: EmailMessage) -> tuple[str, dict[str, str]]:
    """Email body as text, with each link written as "text [L1]", and the URL of each id."""
    links: dict[str, str] = {}
    ids: dict[str, str] = {}

    def link_id(url: str) -> str:
        if url not in ids:
            ids[url] = f"L{len(ids) + 1}"
            links[ids[url]] = url
        return ids[url]

    html_part = msg.get_body(preferencelist=("html",))
    if html_part is not None:
        soup = BeautifulSoup(html_part.get_content(), "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            ref = link_id(a["href"])
            a.replace_with(f" {label} [{ref}] " if label else f" [{ref}] ")
        lines = [line.strip() for line in soup.get_text("\n").splitlines()]
        text = "\n".join(line for line in lines if line)
    else:
        plain = msg.get_body(preferencelist=("plain",))
        text = plain.get_content() if plain is not None else ""
        text = _URL.sub(lambda m: f"[{link_id(m.group(0))}]", text)
    subject = msg.get("Subject", "")
    return f"Subject: {subject}\n\n{text}"[:MAX_EMAIL_CHARS], links


def _message_date(msg: EmailMessage) -> datetime | None:
    try:
        return parsedate_to_datetime(msg["Date"]).astimezone(UTC)
    except (TypeError, ValueError):
        return None


class EmailAlertSource(JobSource):
    name = "email"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        """Every posting from the alert emails of the last EMAIL_LOOKBACK_DAYS days, not
        only those of new emails: the search filters them again with today's settings, and
        drops the ones already saved or scored."""
        config = get_settings()
        if not (config.imap_user and config.imap_password):
            raise RuntimeError("IMAP_USER / IMAP_PASSWORD ayarlanmamış (.env).")

        self.errors = []
        with Session(get_engine()) as session:
            self._forget_old(session)
            for msg in self._new_messages(session):
                # One bad email shouldn't hold back the others. It stays unread, so the next
                # run tries it again.
                try:
                    self._store_postings(session, msg)
                except LLMError as e:
                    logger.warning("Could not extract alert email %s: %s", msg["Message-ID"], e)
                    self.errors.append(f"{msg['Subject'] or msg['Message-ID']}: {e}")
            rows = session.exec(select(AlertPostingRow)).all()
        return [
            RawJob(
                source=self.name, url=row.url, company=row.company, title=row.title,
                location=row.location, remote=row.remote, posted_at=row.received_at,
                description=row.description,
            )
            for row in rows
        ]

    def _store_postings(self, session: Session, msg: EmailMessage) -> None:
        msg_id = msg["Message-ID"]
        received = _message_date(msg)
        jobs = extract_alert_jobs(*email_to_text(msg))
        for url, job in {normalize_url(self._resolve(job.url)): job for job in jobs}.items():
            row = session.get(AlertPostingRow, url)
            if row:
                row.message_id = msg_id  # keep it as long as its newest email
            else:
                row = AlertPostingRow(
                    url=url, message_id=msg_id, company=job.company, title=job.title,
                    location=job.location, remote=looks_remote(job.location, job.snippet),
                    received_at=received, description=job.snippet or "",
                )
            session.add(row)
        # Mark the email read for us only after its jobs were extracted.
        session.add(AlertEmailRow(message_id=msg_id, read_at=datetime.now(UTC)))
        session.commit()

    def _forget_old(self, session: Session) -> None:
        """Drop emails that fell out of the lookback window, with their postings. The extra
        days keep an email the mailbox still lists from being extracted again."""
        days = get_settings().email_lookback_days + FORGET_MARGIN_DAYS
        cutoff = datetime.now(UTC) - timedelta(days=days)
        session.exec(delete(AlertEmailRow).where(col(AlertEmailRow.read_at) < cutoff))
        kept = select(AlertEmailRow.message_id)
        session.exec(delete(AlertPostingRow).where(col(AlertPostingRow.message_id).not_in(kept)))
        session.commit()

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
                select(AlertEmailRow.message_id).where(col(AlertEmailRow.message_id).in_(list(messages)))
            ).all()
        )
        new = [m for mid, m in messages.items() if mid not in seen]
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
