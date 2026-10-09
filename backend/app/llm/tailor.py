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
users", "other teams"), how people worked ("partnered with stakeholders", "code reviews"), \
scope ("shared infrastructure", "company-wide", "production-grade") or impact and qualities \
beyond what is written ("reliability", "scalability", "automated pipelines"). If the \
posting wants something the candidate's data doesn't show, leave it out of the CV and list \
it under missing_skills. This applies to the cover letter and answers too.
Keep the candidate's part in each item as strong as the source says and no stronger: \
"implemented" does not become "designed" or "architected", "worked on" does not become \
"built" or "led", and a team effort stays a team effort.
Keep the concrete details: product, platform and library names (an ERP product, an API \
provider, a standard), document and feature types, team sizes and numbers. Translate them \
where they have a standard translation ("e-Fatura" -> "e-Invoice"), but never replace a \
specific name with a vague phrase ("Odoo ORM" is not "an ORM", "JWT auth with refresh \
tokens" is not "core features"), even when that technology is unrelated to the posting.

Language: the requested CV language, or for "auto" the posting's language (tr or en). \
Everything you write for the CV, the cover letter and the answers is entirely in that \
language, including project names, school, degree and field names, job titles and \
language levels. The candidate's data is often in another language: translate it. Only \
company names, personal names, product and technology names and course codes (e.g. \
"CSE3063") stay as they are.

CV:
- headline and summary: aimed at this role, 2-4 sentences for the summary. The headline \
is the candidate's professional title (e.g. "Software Engineer"), not a copy of the \
posting's title with its qualifiers ("(New Grad)", "Intern", a team name). Claim \
professional experience only for what the work experience shows; skills that come only \
from personal or course projects are presented as project work ("built a Unity game in \
C#"), not as proficiency or professional experience ("proficient in game development").
- experience: include every experience entry from the profile, referenced by its id, \
most relevant first. title is the job title translated into the CV language (same \
meaning and level; keep it as is if already in that language). Rewrite each entry's bullets (2-5 each) to highlight what \
matters for this role; start bullets with strong verbs; keep real numbers only.
- projects: pick the 2-3 projects most relevant to the posting, by id, most relevant \
first. name is the project name in the CV language: translate the descriptive parts and \
keep proper names ("Nexamind — AI Destekli Sınav Koçu" -> "Nexamind — AI-Powered Exam \
Coach", "MiniRAG (CSE3063 Grup Projesi)" -> "MiniRAG (CSE3063 Group Project)"). bullets \
are 2-3 short rewritten sentences (printed as one paragraph) that keep the project's most \
specific facts.
- The whole CV must fit on one A4 page: keep every bullet to one or two lines.
- education: every education entry by id, with school, degree and field in the CV \
language ("Marmara Üniversitesi" -> "Marmara University", "Lisans" -> "Bachelor's Degree").
- languages: the candidate's spoken languages with level, in the CV language, e.g. \
"Turkish (Native)".
- skills: about 8-15 of the candidate's skills, most relevant to the posting first, each \
written exactly as it appears in the profile or projects (nothing else), grouped by what \
they are: languages = programming, query and shader languages (Python, C#, SQL, HLSL, \
ShaderLab); frameworks = frameworks, libraries, game engines and SDKs (FastAPI, Unity, \
Flutter, FAISS); tools = databases, platforms, services, APIs and everything else \
(PostgreSQL, Docker, Git). Prefer real tools over concepts like "Design Patterns" or \
"REST API".

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
no placeholders like [Company]. Plain text with blank lines between paragraphs. Describe \
projects with the same facts as the CV; don't add what they "taught" or "gave practice \
in".
- answers: 3-5 questions this application form is likely to ask (e.g. why this \
company, a relevant project, a challenge solved, salary or notice period only if the \
posting hints at it) with ready-to-paste answers in the candidate's voice. Keep counts \
right (one game project is not "games"). A challenge or conflict story needs a problem \
and outcome the data actually describes; if there is none, ask a different question \
instead of inventing one. Do not \
make up salary numbers, start dates or personal details, and don't accept terms for the \
candidate: a salary stated in the posting is not the candidate's expectation. If \
something is unknown, write the answer as a short template with a "___" blank the \
candidate fills in.
"""


class TailoredItem(BaseModel):
    id: str
    bullets: list[str]


class TailoredExperience(TailoredItem):
    title: str


class TailoredProject(TailoredItem):
    # None keeps the name from the candidate's data.
    name: str | None = None


class TailoredEducation(BaseModel):
    id: str
    school: str | None = None
    degree: str | None = None
    field: str | None = None


class TailoredSkills(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    tools: list[str] = []


class PackageDraft(BaseModel):
    language: Literal["tr", "en"]
    headline: str
    summary: str
    experience: list[TailoredExperience]
    projects: list[TailoredProject]
    education: list[TailoredEducation]
    languages: list[str]
    skills: TailoredSkills
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
    for group in ("languages", "frameworks", "tools"):
        skills = []
        for skill in getattr(draft.skills, group):
            key = skill.casefold()
            if key in known and key not in seen:
                seen.add(key)
                skills.append(known[key])
        setattr(draft.skills, group, skills)


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
