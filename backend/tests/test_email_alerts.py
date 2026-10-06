from email.message import EmailMessage

import pytest

from app import config
from app.jobs.urls import normalize_url
from app.llm.alert_extract import AlertJob
from app.schemas import SearchSettings
from app.sources import email_alerts
from app.sources.base import make_client
from app.sources.email_alerts import EmailAlertSource, email_to_text
from tests.conftest import load_example

ALERT_HTML = """<html><head><style>.x{}</style></head><body>
<h2>Your job alert for backend developer</h2>
<a href="https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc&refId=x">Backend Developer</a>
<p>Örnek Firma · İstanbul (Hybrid)</p>
<a href="https://www.linkedin.com/comm/jobs/search?keywords=backend">See all jobs</a>
</body></html>"""


def make_email(msg_id: str, html: str = ALERT_HTML) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "“backend developer”: Örnek Firma - Backend Developer"
    msg["From"] = "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>"
    msg["Message-ID"] = msg_id
    msg["Date"] = "Tue, 22 Sep 2026 07:00:00 +0000"
    msg.set_content("plain fallback")
    msg.add_alternative(html, subtype="html")
    return msg


class FakeIMAP:
    """Just enough of imaplib.IMAP4_SSL for the source."""

    mailbox: list[EmailMessage] = []
    selected_readonly = None

    def __init__(self, host, port):
        pass

    def login(self, user, password):
        pass

    def select(self, folder, readonly=False):
        FakeIMAP.selected_readonly = readonly

    def search(self, charset, *criteria):
        sender = criteria[-1].strip('"')
        nums = [str(i).encode() for i, m in enumerate(self.mailbox) if sender in m["From"]]
        return "OK", [b" ".join(nums)]

    def fetch(self, num, spec):
        return "OK", [(b"1 (BODY[] {n}", bytes(self.mailbox[int(num)]))]

    def logout(self):
        pass


def test_linkedin_urls_are_normalized():
    assert (
        normalize_url("https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc")
        == "https://www.linkedin.com/jobs/view/4012345678"
    )
    assert (
        normalize_url("https://tr.linkedin.com/jobs/view/backend-developer-at-acme-4012345678?refId=1")
        == "https://www.linkedin.com/jobs/view/4012345678"
    )


def test_email_to_text_keeps_links_and_drops_styles():
    text = email_to_text(make_email("<a@x>"))
    assert "Subject: “backend developer”" in text
    assert "Backend Developer [https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc&refId=x]" in text
    assert "Örnek Firma · İstanbul (Hybrid)" in text
    assert ".x{}" not in text


@pytest.fixture
def imap(client, monkeypatch):
    monkeypatch.setenv("IMAP_USER", "me@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "app-password")
    config.get_settings.cache_clear()
    FakeIMAP.mailbox = [make_email("<first@linkedin>")]
    monkeypatch.setattr(email_alerts.imaplib, "IMAP4_SSL", FakeIMAP)
    calls = []

    def fake_extract(text):
        calls.append(text)
        return [AlertJob(title="Backend Developer", company="Örnek Firma", location="İstanbul (Hybrid)",
                         url="https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc",
                         snippet="Easy Apply")]

    monkeypatch.setattr(email_alerts, "extract_alert_jobs", fake_extract)
    return calls


def test_email_source_reads_each_email_once(imap):
    source = EmailAlertSource(make_client())
    [job] = source.fetch(SearchSettings())
    assert job.source == "email" and job.company == "Örnek Firma" and job.description == "Easy Apply"
    assert job.posted_at.year == 2026
    assert FakeIMAP.selected_readonly is True  # never marks mails as read

    assert source.fetch(SearchSettings()) == []  # already processed
    FakeIMAP.mailbox.append(make_email("<second@linkedin>"))
    assert len(source.fetch(SearchSettings())) == 1
    assert len(imap) == 2


def test_email_source_needs_credentials(client, monkeypatch):
    monkeypatch.delenv("IMAP_USER", raising=False)
    config.get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="IMAP_USER"):
        EmailAlertSource(make_client()).fetch(SearchSettings())


def test_search_run_saves_email_jobs_beyond_cap(client, imap, monkeypatch):
    from app.llm.score import JobScore
    from app.search import service

    monkeypatch.setenv("SEARCH_MAX_SCORED_PER_RUN", "0")
    config.get_settings.cache_clear()
    client.put("/api/profile", json=load_example("profile"))
    settings = load_example("settings")
    settings.update(target_roles=["Backend Developer"], locations=[], seniority=[],
                    sources={**settings["sources"], "greenhouse": [], "lever": [],
                             "remoteok": False, "remotive": False, "arbeitnow": False,
                             "email_alerts": True})
    client.put("/api/settings", json=settings)
    monkeypatch.setattr(service, "score_jobs", lambda p, pr, jobs: [
        JobScore(index=i, score=50, score_reason="Tam ilan metni yok.") for i, _ in enumerate(jobs)])

    client.post("/api/search/run")
    [job] = client.get("/api/jobs").json()
    assert job["source"] == "email"
    assert job["url"] == "https://www.linkedin.com/jobs/view/4012345678"
