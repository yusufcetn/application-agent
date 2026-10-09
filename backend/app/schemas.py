"""API contract models. Must stay in sync with contracts/examples/*.json."""

from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


class Link(BaseModel):
    label: str
    url: str


class Experience(BaseModel):
    id: str = Field(default_factory=lambda: new_id("exp"))
    company: str
    title: str
    location: str | None = None
    start_date: str | None = None  # YYYY-MM
    end_date: str | None = None  # None = present
    bullets: list[str] = []
    skills: list[str] = []


class Education(BaseModel):
    id: str = Field(default_factory=lambda: new_id("edu"))
    school: str
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None


class Skills(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    tools: list[str] = []


class Language(BaseModel):
    name: str
    level: str


class Certification(BaseModel):
    name: str
    issuer: str | None = None
    date: str | None = None


class Profile(BaseModel):
    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[Link] = []
    summary: str = ""
    experience: list[Experience] = []
    education: list[Education] = []
    skills: Skills = Skills()
    languages: list[Language] = []
    certifications: list[Certification] = []
    updated_at: datetime | None = None


class ProjectIn(BaseModel):
    name: str
    role: str | None = None
    summary: str = ""
    bullets: list[str] = []
    tech: list[str] = []
    links: list[Link] = []
    start_date: str | None = None
    end_date: str | None = None
    featured: bool = False


class Project(ProjectIn):
    id: str


class ImportIssue(BaseModel):
    file: str
    message: str


class ProjectImportResult(BaseModel):
    created: list[Project] = []
    updated: list[Project] = []
    errors: list[ImportIssue] = []


Seniority = Literal["intern", "junior", "mid", "senior", "lead"]
SourceName = Literal[
    "manual", "greenhouse", "lever", "ashby", "remoteok", "remotive", "arbeitnow", "adzuna", "email",
    "web",
]
EmploymentType = Literal["full_time", "part_time", "working_student", "internship", "contract"]
# Whether the posting still takes applications, as last checked.
PostingStatus = Literal["open", "closed", "unknown"]


class SourceSettings(BaseModel):
    greenhouse: list[str] = []
    lever: list[str] = []
    ashby: list[str] = []
    remoteok: bool = True
    remotive: bool = True
    arbeitnow: bool = True
    adzuna: bool = False
    email_alerts: bool = False
    # An LLM agent searches the web (company career pages, Youthall, LinkedIn links, ...).
    web_search: bool = False


class SearchSettings(BaseModel):
    target_roles: list[str] = []
    locations: list[str] = []
    remote_only: bool = False
    seniority: list[Seniority] = []
    keywords_exclude: list[str] = []
    min_score: int = Field(default=70, ge=0, le=100)
    auto_package: bool = True
    cv_language: Literal["auto", "tr", "en"] = "auto"
    sources: SourceSettings = SourceSettings()
    schedule_cron: str = "0 8 * * *"
    # Email a summary after each scheduled search.
    daily_report: bool = False


JobStatus = Literal["new", "applied", "skipped", "interview", "rejected", "offer"]
PackageStatus = Literal["none", "generating", "ready", "failed"]


class Job(BaseModel):
    id: str
    source: SourceName
    url: str
    company: str
    title: str
    location: str | None = None
    remote: bool | None = None
    seniority: Seniority | None = None
    employment_type: EmploymentType | None = None
    posted_at: datetime | None = None
    found_at: datetime
    description: str = ""
    posting_status: PostingStatus = "unknown"
    last_verified_at: datetime | None = None
    application_deadline: date | None = None
    # Why posting_status is what it is, shown to the user.
    verification_reason: str | None = None
    score: int | None = None
    score_reason: str | None = None
    status: JobStatus = "new"
    package_status: PackageStatus = "none"
    # Why the last package attempt failed, shown to the user; null otherwise.
    package_error: str | None = None
    notes: str = ""
    # When the user first opened the job; null = not opened yet.
    seen_at: datetime | None = None


class ManualJobIn(BaseModel):
    url: str | None = None
    # Optional pasted posting text, for pages that can't be fetched (login walls etc.).
    text: str | None = None


class JobUpdate(BaseModel):
    status: JobStatus | None = None
    notes: str | None = None
    # Pasted posting text, for postings whose page couldn't be read.
    description: str | None = None
    # true marks the job opened (the first time is kept), false marks it unopened again.
    seen: bool | None = None


class PackageAccepted(BaseModel):
    job_id: str
    package_status: PackageStatus


class Answer(BaseModel):
    question: str
    answer: str


class Analysis(BaseModel):
    score: int = Field(ge=0, le=100)
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    highlighted_projects: list[str] = []
    highlighted_experience: list[str] = []
    tips: list[str] = []


class Package(BaseModel):
    job_id: str
    generated_at: datetime
    cv_pdf_url: str
    cv_language: Literal["tr", "en"]
    cover_letter: str
    answers: list[Answer] = []
    analysis: Analysis


class SearchRun(BaseModel):
    id: str
    status: Literal["running", "done", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    jobs_found: int = 0
    # Updated after every scored batch while the run is going.
    jobs_scored: int = 0
    jobs_new: int = 0
    jobs_above_threshold: int = 0
    # Saved postings found closed during this run.
    jobs_closed: int = 0
    # On "done" this can still hold a warning, e.g. a source that couldn't be read.
    error: str | None = None
