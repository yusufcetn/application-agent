"""Render a tailored CV to HTML and PDF."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.llm.tailor import PackageDraft
from app.schemas import Profile, Project

LABELS = {
    "tr": {
        "summary": "Özet",
        "experience": "Deneyim",
        "projects": "Projeler",
        "skills": "Yetenekler",
        "education": "Eğitim",
        "certifications": "Sertifikalar",
        "languages": "Diller",
        "present": "Halen",
        "gpa": "Not ort.",
    },
    "en": {
        "summary": "Summary",
        "experience": "Experience",
        "projects": "Projects",
        "skills": "Skills",
        "education": "Education",
        "certifications": "Certifications",
        "languages": "Languages",
        "present": "Present",
        "gpa": "GPA",
    },
}


def _fmt_date(value: str | None, empty: str = "") -> str:
    if not value:
        return empty
    year, _, month = value.partition("-")
    return f"{month}/{year}" if month else year


def _display_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
)
_env.filters["fmt_date"] = _fmt_date
_env.filters["display_url"] = _display_url


def render_cv_html(profile: Profile, projects: list[Project], cv: PackageDraft) -> str:
    """Facts (employer, title, dates, education) come from the profile;
    only the wording and selection come from the tailored draft."""
    exp_by_id = {e.id: e for e in profile.experience}
    experience = [
        {**exp_by_id[item.id].model_dump(), "title": item.title, "bullets": item.bullets}
        for item in cv.experience
    ]
    translated_edu = {e.id: e for e in cv.education}
    education = []
    for ed in profile.education:
        entry = ed.model_dump()
        if t := translated_edu.get(ed.id):
            entry.update(degree=t.degree or ed.degree, field=t.field or ed.field)
        education.append(entry)
    languages = cv.languages or [f"{lang.name} ({lang.level})" for lang in profile.languages]
    project_by_id = {p.id: p for p in projects}
    selected_projects = [
        {**project_by_id[item.id].model_dump(), "bullets": item.bullets} for item in cv.projects
    ]
    return _env.get_template("cv.html.j2").render(
        p=profile,
        cv=cv,
        experience=experience,
        projects=selected_projects,
        education=education,
        languages=languages,
        t=LABELS[cv.language],
        lang=cv.language,
    )


def html_to_pdf(html: str, out_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(path=str(out_path), format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()
