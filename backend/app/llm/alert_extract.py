"""Pull the individual job postings out of a job alert email."""

from pydantic import BaseModel

from app.llm.runner import run_structured

SYSTEM_PROMPT = """\
You read job alert emails (LinkedIn, Kariyer.net, Indeed, Glassdoor and similar) and \
list the job postings they contain. The email text is inside <email> tags; links are \
written as "link text [URL]".

Rules:
- One entry per job posting. Skip ads, courses, "see all jobs" / "view more" links, \
settings and unsubscribe links, and anything that isn't a specific posting.
- url: the link that opens that specific posting, copied exactly.
- title, company, location: as written in the email. location null if not shown.
- snippet: any extra text the email shows about that posting (salary, "Easy Apply", \
short description), or null.
- Never invent postings or details. An email with no postings gives an empty list.
"""


class AlertJob(BaseModel):
    title: str
    company: str
    location: str | None = None
    url: str
    snippet: str | None = None


class AlertJobs(BaseModel):
    jobs: list[AlertJob]


def extract_alert_jobs(email_text: str) -> list[AlertJob]:
    result = run_structured(
        SYSTEM_PROMPT,
        f"<email>\n{email_text}\n</email>\n\nList the job postings in this email.",
        AlertJobs,
    )
    return result.jobs
