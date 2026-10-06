"""Read the structured details of a job posting out of raw page text."""

from typing import Literal

from pydantic import BaseModel

from app.llm.runner import run_structured
from app.schemas import Seniority

SYSTEM_PROMPT = """\
You read job posting pages and extract the posting's details. The page text is inside \
<page> tags; it may include navigation, cookie banners and other noise.

Rules:
- is_job_posting is false when the page is not a single job posting (a login wall, a \
search results page, an expired or missing posting). Then fill the other fields with \
empty values.
- description: the full posting (about the role, responsibilities, requirements, nice to \
have, benefits) as clean Markdown, in the posting's original language. Keep all the \
content; drop only page noise. Do not summarize.
- seniority: infer from the title and requirements; null if unclear.
- remote: true for fully remote, false for on-site or hybrid, null if not stated.
- posted_at: ISO date (YYYY-MM-DD) if the page states it, otherwise null.
- Never invent details that are not on the page.
"""


class ExtractedJob(BaseModel):
    is_job_posting: bool
    company: str
    title: str
    location: str | None = None
    remote: bool | None = None
    seniority: Seniority | None = None
    posted_at: str | None = None
    language: Literal["tr", "en", "other"]
    description: str


def extract_job(page_text: str, url: str) -> ExtractedJob:
    return run_structured(
        SYSTEM_PROMPT,
        f"URL: {url}\n\n<page>\n{page_text}\n</page>\n\nExtract the job posting.",
        ExtractedJob,
    )
