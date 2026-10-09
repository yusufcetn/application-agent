"""The daily report email: what a search run found, what closed, what needs action."""

import html
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from app.config import get_settings
from app.db import JobRow, SearchRunRow
from app.services.mailer import send_email
from app.services.packages import load_search_settings

DEADLINE_DAYS = 3
WAITING_LIMIT = 10


def _status_note(job: JobRow) -> str:
    parts = []
    if job.posting_status == "open":
        parts.append("açık ✓")
    elif job.posting_status == "closed":
        parts.append("kapandı")
    if job.application_deadline:
        parts.append(f"son başvuru {job.application_deadline:%d.%m.%Y}")
    return ", ".join(parts)


def _job_line(job: JobRow, app_url: str | None) -> tuple[str, str]:
    score = f"{job.score}" if job.score is not None else "—"
    where = f" · {job.location}" if job.location else ""
    note = _status_note(job)
    note = f" ({note})" if note else ""
    text = f"[{score}] {job.title} — {job.company}{where}{note}\n    {job.url}"
    links = f'<a href="{html.escape(job.url)}">İlan</a>'
    if app_url:
        page = f"{app_url.rstrip('/')}/jobs/{job.id}"
        text += f"\n    Paket: {page}"
        links += f' · <a href="{html.escape(page)}">Başvuru paketi</a>'
    markup = (
        f"<li><b>{score}</b> · {html.escape(job.title)} — {html.escape(job.company)}"
        f"{html.escape(where)}{html.escape(note)}<br><small>{links}</small></li>"
    )
    return text, markup


def build_report(session: Session, run: SearchRunRow) -> tuple[str, str, str]:
    """Returns (subject, plain text, html)."""
    config = get_settings()
    settings = load_search_settings(session)
    summary = run.summary or {}

    def rows(ids: list[str]) -> list[JobRow]:
        found = session.exec(select(JobRow).where(col(JobRow.id).in_(ids))).all() if ids else []
        return sorted(found, key=lambda j: j.score or 0, reverse=True)

    new = [j for j in rows(summary.get("new", [])) if j.posting_status != "closed"]
    closed = rows(summary.get("closed", []))
    reopened = rows(summary.get("reopened", []))
    today = datetime.now(UTC).date()
    shown = {j.id for j in new + reopened}
    pending = session.exec(
        select(JobRow).where(JobRow.status == "new", JobRow.posting_status != "closed")
    ).all()
    waiting = sorted(
        (
            j
            for j in pending
            if j.id not in shown and j.posting_status == "open" and (j.score or 0) >= settings.min_score
        ),
        key=lambda j: j.score or 0,
        reverse=True,
    )[:WAITING_LIMIT]
    due = sorted(
        (
            j
            for j in pending
            if j.application_deadline
            and today <= j.application_deadline <= today + timedelta(days=DEADLINE_DAYS)
        ),
        key=lambda j: j.application_deadline,
    )

    sections = [
        ("Yeni bulunan ilanlar", new),
        ("Yeniden açılan ilanlar", reopened),
        ("Son başvurusu yaklaşanlar", due),
        ("Başvurmadığın açık ilanlar", waiting),
        ("Kapanan kayıtlı ilanlar", closed),
    ]
    text_parts, html_parts = [], []
    for title, jobs in sections:
        if not jobs:
            continue
        lines = [_job_line(j, config.app_url) for j in jobs]
        text_parts.append(f"{title} ({len(jobs)})\n" + "\n".join(t for t, _ in lines))
        html_parts.append(f"<h3>{html.escape(title)} ({len(jobs)})</h3><ul>{''.join(m for _, m in lines)}</ul>")
    if not text_parts:
        text_parts.append("Bugün bildirilecek yeni ya da açık ilan yok.")
        html_parts.append("<p>Bugün bildirilecek yeni ya da açık ilan yok.</p>")

    footer = (
        f"Tarama: {run.jobs_found} ilan tarandı, {run.jobs_new} yeni kaydedildi, "
        f"{run.jobs_above_threshold} eşik üstünde, {run.jobs_closed} kapandı."
    )
    if run.error:
        footer += f"\nUyarı: {run.error}"
    open_count = len(new) + len(reopened) + len(waiting)
    subject = f"Apply Agent · {today:%d.%m.%Y}: {open_count} ilan, {len(due)} son başvuru yaklaşıyor"
    text = "\n\n".join([*text_parts, footer])
    body = "".join(html_parts) + f"<p style=\"color:#5b6478\">{html.escape(footer).replace(chr(10), '<br>')}</p>"
    return subject, text, f'<div style="font-family:Arial,sans-serif;font-size:14px">{body}</div>'


def send_run_report(session: Session, run: SearchRunRow) -> str:
    """Sends the report for a finished run; returns the recipient."""
    subject, text, markup = build_report(session, run)
    return send_email(subject, text, markup)
