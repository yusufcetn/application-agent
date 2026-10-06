"""Score many job postings against the candidate in a few LLM calls."""

import json

from pydantic import BaseModel

from app.llm.runner import run_structured
from app.schemas import Profile, Project, Seniority
from app.sources.base import RawJob

BATCH_SIZE = 8
DESCRIPTION_CHARS = 3000

SYSTEM_PROMPT = """\
You screen job postings for a candidate. For each posting, judge how well the \
candidate fits it, based only on the candidate data given.

For each posting return:
- index: the posting's index.
- score: 0-100 fit. 80+ strong fit (should apply), 60-79 reasonable, below 60 weak. \
Weigh required skills, years and level of experience, and domain. Be honest and strict: \
missing must-have requirements lower the score a lot.
- If the posting restricts where candidates can live or work (e.g. "US only", on-site \
in a city the candidate isn't in and no relocation mentioned) and the candidate's \
location doesn't fit, score it at most 30 and say so.
- score_reason: one short sentence in Turkish explaining the score.
- Some postings only have a short snippet instead of a full description (e.g. from job \
alert emails). Score them from what is there (title, company, location, snippet) and \
say in score_reason that the full posting wasn't available.
- seniority: the level the posting targets (intern, junior, mid, senior, lead), or null \
if unclear.

Return exactly one result per posting.
"""


class JobScore(BaseModel):
    index: int
    score: int
    score_reason: str
    seniority: Seniority | None = None


class ScoreBatch(BaseModel):
    results: list[JobScore]


def candidate_summary(profile: Profile, projects: list[Project]) -> dict:
    return {
        "headline": profile.headline,
        "location": profile.location,
        "summary": profile.summary,
        "experience": [
            {
                "title": e.title,
                "company": e.company,
                "from": e.start_date,
                "to": e.end_date or "present",
                "skills": e.skills,
                "highlights": e.bullets[:3],
            }
            for e in profile.experience
        ],
        "education": [f"{e.degree or ''} {e.field or ''}, {e.school}".strip() for e in profile.education],
        "skills": profile.skills.model_dump(),
        "languages": [f"{lang.name} ({lang.level})" for lang in profile.languages],
        "projects": [{"name": p.name, "tech": p.tech, "summary": p.summary} for p in projects],
    }


def score_jobs(profile: Profile, projects: list[Project], jobs: list[RawJob]) -> list[JobScore | None]:
    """Returns one score per job, in order; None where the model skipped a job."""
    candidate = json.dumps(candidate_summary(profile, projects), ensure_ascii=False, indent=1)
    scores: list[JobScore | None] = [None] * len(jobs)
    for start in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[start : start + BATCH_SIZE]
        postings = "\n\n".join(
            f'<posting index="{i}">\nTitle: {j.title}\nCompany: {j.company}\n'
            f"Location: {j.location or '-'}{' (remote)' if j.remote else ''}\n\n"
            f"{j.description[:DESCRIPTION_CHARS]}\n</posting>"
            for i, j in enumerate(batch)
        )
        result = run_structured(
            SYSTEM_PROMPT,
            f"<candidate>\n{candidate}\n</candidate>\n\n{postings}\n\nScore every posting.",
            ScoreBatch,
        )
        for s in result.results:
            if 0 <= s.index < len(batch):
                s.score = max(0, min(100, s.score))
                scores[start + s.index] = s
    return scores
