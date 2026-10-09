"""Render a tailored CV to HTML and PDF."""

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.llm.tailor import PackageDraft, TailoredSkills
from app.schemas import Profile, Project

LABELS = {
    "tr": {
        "summary": "Özet",
        "experience": "İş Deneyimi",
        "projects": "Projeler",
        "skills": "Teknik Yetkinlikler",
        "skill_languages": "Programlama Dilleri",
        "skill_frameworks": "Framework ve Kütüphaneler",
        "skill_tools": "Araçlar ve Teknolojiler",
        "education": "Eğitim",
        "certifications": "Sertifikalar",
        "languages": "Yabancı Dil",
        "present": "Devam ediyor",
        "expected": "beklenen",
        "gpa": "GANO",
        "months": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
                   "Eylül", "Ekim", "Kasım", "Aralık"],
    },
    "en": {
        "summary": "Summary",
        "experience": "Work Experience",
        "projects": "Projects",
        "skills": "Technical Skills",
        "skill_languages": "Languages",
        "skill_frameworks": "Frameworks & Libraries",
        "skill_tools": "Tools & Technologies",
        "education": "Education",
        "certifications": "Certifications",
        "languages": "Languages",
        "present": "Present",
        "expected": "expected",
        "gpa": "GPA",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"],
    },
}


def _date_range(start: str | None, end: str | None, t: dict) -> str:
    """Years only, e.g. "2024 - 2025"; a future end reads "2022 - June 2027 (expected)"."""
    start_year = start[:4] if start else ""
    if not end:
        end_text = t["present"]
    else:
        year, _, month = end.partition("-")
        if month and end > date.today().strftime("%Y-%m"):
            end_text = f"{t['months'][int(month) - 1]} {year} ({t['expected']})"
        else:
            end_text = year
    return f"{start_year} - {end_text}" if start_year else end_text


def _grouped_skills(skills: TailoredSkills, t: dict) -> list[tuple[str, list[str]]]:
    return [
        (t[f"skill_{key}"], names)
        for key in ("languages", "frameworks", "tools")
        if (names := getattr(skills, key))
    ]


def _display_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _link_href(url: str) -> str:
    """Profiles often hold "github.com/user"; without a scheme the PDF link goes nowhere."""
    return url if "://" in url or url.startswith("mailto:") else f"https://{url}"


_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
)
_env.filters["display_url"] = _display_url
_env.filters["link_href"] = _link_href
# Names are Turkish whatever the CV language: "Çetin" -> "ÇETİN", not "ÇETIN".
_env.filters["upper_tr"] = lambda s: s.replace("i", "İ").replace("ı", "I").upper()


def render_cv_html(profile: Profile, projects: list[Project], cv: PackageDraft) -> str:
    """Facts (employer, title, dates, education) come from the profile;
    only the wording and selection come from the tailored draft."""
    exp_by_id = {e.id: e for e in profile.experience}
    # Ids are checked again: a saved draft is printed again after the profile changes.
    experience = [
        {**exp_by_id[item.id].model_dump(), "title": item.title, "bullets": item.bullets}
        for item in cv.experience
        if item.id in exp_by_id
    ]
    translated_edu = {e.id: e for e in cv.education}
    education = []
    for ed in profile.education:
        entry = ed.model_dump()
        if t := translated_edu.get(ed.id):
            entry.update(
                school=t.school or ed.school, degree=t.degree or ed.degree, field=t.field or ed.field
            )
        education.append(entry)
    languages = cv.languages or [f"{lang.name} ({lang.level})" for lang in profile.languages]
    project_by_id = {p.id: p for p in projects}
    selected_projects = [
        {
            **project_by_id[item.id].model_dump(),
            "name": item.name or project_by_id[item.id].name,
            "bullets": item.bullets,
        }
        for item in cv.projects
        if item.id in project_by_id
    ]
    labels = LABELS[cv.language]
    for entry in (*experience, *education):
        entry["dates"] = _date_range(entry["start_date"], entry["end_date"], labels)
    return _env.get_template("cv.html.j2").render(
        p=profile,
        cv=cv,
        experience=experience,
        projects=selected_projects,
        education=education,
        languages=languages,
        skill_groups=_grouped_skills(cv.skills, labels),
        t=labels,
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
