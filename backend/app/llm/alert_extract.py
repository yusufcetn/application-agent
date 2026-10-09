"""Pull the individual job postings out of a job alert email."""

from pydantic import BaseModel

from app.llm.runner import extract_model, run_structured

SYSTEM_PROMPT = """\
You read job alert emails (LinkedIn, Kariyer.net, Indeed, Glassdoor and similar) and \
list the job postings they contain. The email text is inside <email> tags; each link is \
written as "link text [L<number>]", a short id standing in for its URL.

Rules:
- One entry per job posting. Skip ads, courses, "see all jobs" / "view more" links, \
settings and unsubscribe links, and anything that isn't a specific posting.
- url: the id of the link that opens that specific posting, e.g. "L12".
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


def extract_alert_jobs(email_text: str, links: dict[str, str]) -> list[AlertJob]:
    """`links` maps the link ids in `email_text` to their URLs. Alert URLs carry hundreds of
    characters of tracking tokens; copying them out made the model too slow to finish."""
    result = run_structured(
        SYSTEM_PROMPT,
        f"<email>\n{email_text}\n</email>\n\nList the job postings in this email.",
        AlertJobs,
        model=extract_model(),
    )
    jobs = []
    for job in result.jobs:
        url = links.get(job.url.strip().strip("[]"))
        if url:
            jobs.append(job.model_copy(update={"url": url}))
    return jobs
