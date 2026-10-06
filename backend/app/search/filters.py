"""Cheap, rule-based filtering before any LLM call."""

import re
from datetime import UTC, datetime, timedelta

from app.schemas import Profile, Project, SearchSettings
from app.sources.base import RawJob, looks_remote
from app.text import fold

# Words that say little about the role on their own (compared after fold()).
_GENERIC_ROLE_WORDS = {
    "developer", "engineer", "software", "senior", "junior", "mid", "lead", "staff",
    "principal", "sr", "jr", "ii", "iii", "intern", "dev", "specialist", "expert",
    "geliştirici", "gelistirici", "mühendis", "mühendisi", "muhendis", "yazılım",
    "yazilim", "uzman", "uzmanı", "stajyer", "kıdemli",
}
GENERIC_ROLE_WORDS = {fold(w) for w in _GENERIC_ROLE_WORDS}

# Postings are often in English while the settings are in Turkish (after fold()).
LOCATION_ALIASES = {"turkiye": ["turkey"], "turkey": ["turkiye"]}


def _normalize(text: str) -> str:
    return re.sub(r"[-_/.,()]", " ", fold(text)).replace("back end", "backend").replace(
        "front end", "frontend"
    ).replace("full stack", "fullstack")


def _role_token_sets(target_roles: list[str]) -> list[list[str]]:
    sets = []
    for role in target_roles:
        tokens = _normalize(role).split()
        specific = [t for t in tokens if t not in GENERIC_ROLE_WORDS]
        sets.append(specific or tokens)
    return [s for s in sets if s]


def matches_role(title: str, target_roles: list[str]) -> bool:
    """'Backend Developer' matches any title containing 'backend';
    a fully generic role like 'Software Engineer' needs all of its words."""
    token_sets = _role_token_sets(target_roles)
    if not token_sets:
        return True
    words = set(_normalize(title).split())
    return any(all(t in words for t in tokens) for tokens in token_sets)


def is_excluded(title: str, keywords_exclude: list[str]) -> bool:
    folded = fold(title)
    return any(fold(k) in folded for k in keywords_exclude if k.strip())


def matches_location(job: RawJob, settings: SearchSettings) -> bool:
    remote = job.remote or looks_remote(job.location)
    if settings.remote_only:
        return bool(remote)
    wanted = [fold(loc) for loc in settings.locations if loc.strip()]
    wanted += [alias for loc in wanted for alias in LOCATION_ALIASES.get(loc, [])]
    if not wanted:
        return True
    if remote and any(looks_remote(loc) for loc in wanted):
        return True
    location = fold(job.location or "")
    return any(loc in location for loc in wanted if not looks_remote(loc))


def is_recent(job: RawJob, max_age_days: int) -> bool:
    if not job.posted_at:
        return True
    return job.posted_at >= datetime.now(UTC) - timedelta(days=max_age_days)


def prefilter(jobs: list[RawJob], settings: SearchSettings, max_age_days: int) -> list[RawJob]:
    return [
        j
        for j in jobs
        if j.title
        and matches_role(j.title, settings.target_roles)
        and not is_excluded(j.title, settings.keywords_exclude)
        and matches_location(j, settings)
        and is_recent(j, max_age_days)
    ]


def profile_keywords(profile: Profile, projects: list[Project], target_roles: list[str]) -> set[str]:
    words = [*profile.skills.languages, *profile.skills.frameworks, *profile.skills.tools]
    for exp in profile.experience:
        words += exp.skills
    for project in projects:
        words += project.tech
    for tokens in _role_token_sets(target_roles):
        words += tokens
    return {_normalize(w).strip() for w in words if len(w.strip()) > 1}


def relevance(job: RawJob, keywords: set[str]) -> int:
    """Cheap overlap score used to pick which postings are worth an LLM call."""
    title = f" {_normalize(job.title)} "
    body = f" {_normalize(job.description[:5000])} "
    title_hits = sum(1 for k in keywords if f" {k} " in title)
    body_hits = sum(1 for k in keywords if f" {k} " in body)
    return 3 * title_hits + min(body_hits, 10)
