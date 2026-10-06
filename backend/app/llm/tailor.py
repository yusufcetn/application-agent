"""Tailor the CV to one job posting and write the rest of the application package."""

import json
from typing import Literal

from pydantic import BaseModel

from app.llm.runner import run_structured
from app.schemas import Answer, Job, Profile, Project

SYSTEM_PROMPT = """\
You are an expert career coach and CV writer. Given a candidate's profile, their \
projects and one job posting, you produce a tailored application package.

The most important rule: be truthful. Use only facts that are in the candidate's \
profile and projects. Never invent employers, titles, dates, metrics, technologies, \
degrees or achievements. You may rephrase, reorder, emphasize and trim, and you may \
use the posting's terminology for things the candidate actually did.
Do not add context the source doesn't state either: who used something ("non-engineering \
users", "other teams"), how people worked ("partnered with stakeholders"), scope ("shared \
infrastructure", "company-wide") or impact beyond what is written. If the posting wants \
something the candidate's data doesn't show, leave it out of the CV and list it under \
missing_skills. This applies to the cover letter and answers too.

CV:
- language: the CV language. Follow the requested CV language; for "auto", use the \
posting's language (tr or en).
- headline and summary: aimed at this role, 2-4 sentences for the summary.
- experience: include every experience entry from the profile, referenced by its id, \
most relevant first. title is the job title translated into the CV language (same \
meaning and level; keep it as is if already in that language). Rewrite each entry's bullets (2-5 each) to highlight what matters \
for this role; start bullets with strong verbs; keep real numbers only.
- projects: pick the 2-4 projects most relevant to the posting, by id, most relevant \
first, with 2-3 rewritten bullets each.
- education: every education entry by id, with degree and field translated into the CV \
language.
- languages: the candidate's spoken languages with level, in the CV language, e.g. \
"Turkish (Native)".
- skills: the candidate's skills most relevant to the posting first. Only skills that \
appear somewhere in the profile or projects.
- Translate text into the CV language when needed, without changing facts.

Analysis:
- score: 0-100 fit between the candidate and the posting. 80+ strong fit, 60-79 \
reasonable, below 60 weak. Be honest; required skills the candidate lacks lower it.
- score_reason: one sentence explaining the score, in Turkish.
- matched_skills / missing_skills: the posting's key requirements the candidate does / \
does not have.
- tips: 2-4 short, practical tips in Turkish for applying and interviewing for this role.

Application texts, in the CV language:
- cover_letter: 200-350 words, specific to this company and role, linking the \
candidate's real experience and projects to the posting's needs. No generic filler, \
no placeholders like [Company]. Plain text with blank lines between paragraphs.
- answers: 3-5 questions this application form is likely to ask (e.g. why this \
company, a relevant project, a challenge solved, salary or notice period only if the \
posting hints at it) with ready-to-paste answers in the candidate's voice. Do not \
make up salary numbers or personal details; if unknown, write the answer as a short \
template the candidate completes.
"""


class TailoredItem(BaseModel):
    id: str
    bullets: list[str]


class TailoredExperience(TailoredItem):
    title: str


class TailoredEducation(BaseModel):
    id: str
    degree: str | None = None
    field: str | None = None


class PackageDraft(BaseModel):
    language: Literal["tr", "en"]
    headline: str
    summary: str
    experience: list[TailoredExperience]
    projects: list[TailoredItem]
    education: list[TailoredEducation]
    languages: list[str]
    skills: list[str]
    score: int
    score_reason: str
    matched_skills: list[str]
    missing_skills: list[str]
    tips: list[str]
    cover_letter: str
    answers: list[Answer]


def _known_skills(profile: Profile, projects: list[Project]) -> dict[str, str]:
    names = [*profile.skills.languages, *profile.skills.frameworks, *profile.skills.tools]
    for exp in profile.experience:
        names += exp.skills
    for project in projects:
        names += project.tech
    return {n.casefold(): n for n in names}


def _enforce_facts(draft: PackageDraft, profile: Profile, projects: list[Project]) -> None:
    """Drop anything the model referenced that isn't in the candidate's data."""
    draft.score = max(0, min(100, draft.score))
    exp_ids = {e.id for e in profile.experience}
    draft.experience = [e for e in draft.experience if e.id in exp_ids]
    # Every job stays on the CV even if the model skipped it; gaps look worse than detail.
    included = {e.id for e in draft.experience}
    for exp in profile.experience:
        if exp.id not in included:
            draft.experience.append(TailoredExperience(id=exp.id, title=exp.title, bullets=exp.bullets))

    edu_ids = {e.id for e in profile.education}
    draft.education = [e for e in draft.education if e.id in edu_ids]

    project_ids = {p.id for p in projects}
    draft.projects = [p for p in draft.projects if p.id in project_ids]

    known = _known_skills(profile, projects)
    seen: set[str] = set()
    skills = []
    for skill in draft.skills:
        key = skill.casefold()
        if key in known and key not in seen:
            seen.add(key)
            skills.append(known[key])
    draft.skills = skills


def tailor_package(
    profile: Profile,
    projects: list[Project],
    job: Job,
    cv_language: Literal["auto", "tr", "en"],
) -> PackageDraft:
    candidate = {
        "profile": profile.model_dump(mode="json", exclude={"updated_at"}),
        "projects": [p.model_dump(mode="json") for p in projects],
    }
    prompt = (
        f"<candidate>\n{json.dumps(candidate, ensure_ascii=False, indent=1)}\n</candidate>\n\n"
        f"<job_posting>\nCompany: {job.company}\nTitle: {job.title}\n"
        f"Location: {job.location or '-'}\n\n{job.description}\n</job_posting>\n\n"
        f"Requested CV language: {cv_language}\n\n"
        "Produce the tailored application package."
    )
    draft = run_structured(SYSTEM_PROMPT, prompt, PackageDraft)
    _enforce_facts(draft, profile, projects)
    return draft
