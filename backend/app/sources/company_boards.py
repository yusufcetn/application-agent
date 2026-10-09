"""ATS job boards of specific companies (slugs come from the settings or the web search)."""

from app.schemas import SearchSettings
from app.sources.base import JobSource, RawJob, from_timestamp, looks_remote, parse_iso
from app.text import html_to_plain


LISTED = "Şirketin ilan listesinde yayında."
_EMPLOYMENT = {
    "fulltime": "full_time", "full time": "full_time", "parttime": "part_time",
    "part time": "part_time", "intern": "internship", "internship": "internship",
    "contract": "contract", "contractor": "contract", "temporary": "contract",
    "working student": "working_student", "werkstudent": "working_student",
}


def _employment(value: str | None) -> str | None:
    return _EMPLOYMENT.get((value or "").replace("-", " ").replace("_", " ").strip().casefold())


def _company_name(slug: str) -> str:
    return slug.replace("-", " ").title()


# Some boards put the employment type or the company name in the location field.
_NOT_A_LOCATION = {"full time", "part time", "contract", "internship", "new grad", "fulltime"}


def _clean_location(location: str | None, company: str) -> str | None:
    """None when the field holds something other than a place (e.g. Peak Games' "Full-time")."""
    if not location:
        return None
    value = location.replace("-", " ").strip().casefold()
    if value in _NOT_A_LOCATION or value == company.casefold():
        return None
    return location


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        return [job for board in settings.sources.greenhouse for job in self.fetch_board(board)]

    def fetch_board(self, board: str) -> list[RawJob]:
        jobs = []
        data = self.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", content="true")
        for j in data.get("jobs", []):
            location = (j.get("location") or {}).get("name")
            location_type = " ".join(
                str(m.get("value")) for m in j.get("metadata") or [] if m.get("value")
            )
            jobs.append(
                RawJob(
                    source=self.name,
                    url=j["absolute_url"],
                    company=j.get("company_name") or _company_name(board),
                    title=j["title"].strip(),
                    location=location,
                    remote=looks_remote(location, location_type),
                    posted_at=parse_iso(j.get("first_published") or j.get("updated_at")),
                    description=html_to_plain(j.get("content", "")),
                    posting_status="open",
                    verification_reason=LISTED,
                )
            )
        return jobs


class LeverSource(JobSource):
    name = "lever"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        return [job for company in settings.sources.lever for job in self.fetch_board(company)]

    def fetch_board(self, company: str) -> list[RawJob]:
        jobs = []
        for j in self.get_json(f"https://api.lever.co/v0/postings/{company}", mode="json"):
            location = _clean_location(
                (j.get("categories") or {}).get("location"), _company_name(company)
            )
            lists = "\n\n".join(
                f"{item.get('text', '')}\n{html_to_plain(item.get('content', ''))}"
                for item in j.get("lists") or []
            )
            description = "\n\n".join(
                part
                for part in (j.get("descriptionPlain"), lists, j.get("additionalPlain"))
                if part
            )
            jobs.append(
                RawJob(
                    source=self.name,
                    url=j["hostedUrl"],
                    company=_company_name(company),
                    title=j["text"].strip(),
                    location=location,
                    remote=j.get("workplaceType") == "remote" or looks_remote(location),
                    posted_at=from_timestamp(j.get("createdAt"), millis=True),
                    description=description,
                    employment_type=_employment((j.get("categories") or {}).get("commitment")),
                    posting_status="open",
                    verification_reason=LISTED,
                )
            )
        return jobs


class AshbySource(JobSource):
    name = "ashby"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        return [job for org in settings.sources.ashby for job in self.fetch_board(org)]

    def fetch_board(self, org: str) -> list[RawJob]:
        jobs = []
        data = self.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
        for j in data.get("jobs", []):
            if j.get("isListed") is False:
                continue
            jobs.append(
                RawJob(
                    source=self.name,
                    url=j["jobUrl"],
                    company=_company_name(org),
                    title=j["title"].strip(),
                    location=_clean_location(j.get("location"), _company_name(org)),
                    remote=bool(j.get("isRemote")) or j.get("workplaceType") == "Remote",
                    posted_at=parse_iso(j.get("publishedAt")),
                    description=j.get("descriptionPlain")
                    or html_to_plain(j.get("descriptionHtml", "")),
                    employment_type=_employment(j.get("employmentType")),
                    posting_status="open",
                    verification_reason=LISTED,
                )
            )
        return jobs


class WorkableSource(JobSource):
    """Only used for boards the web search finds; not a setting."""

    name = "workable"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        return []

    def fetch_board(self, account: str) -> list[RawJob]:
        data = self.get_json(f"https://apply.workable.com/api/v1/widget/accounts/{account}")
        company = data.get("name") or _company_name(account)
        jobs = []
        for j in data.get("jobs", []):
            location = ", ".join(p for p in (j.get("city"), j.get("country")) if p) or None
            jobs.append(
                RawJob(
                    source=self.name,
                    # With the account in the path, the posting can be checked through the API later.
                    url=f"https://apply.workable.com/{account}/j/{j['shortcode']}/",
                    company=company,
                    title=j["title"].strip(),
                    location=location,
                    remote=bool(j.get("telecommuting")) or looks_remote(location),
                    posted_at=parse_iso(j.get("published_on") or j.get("created_at")),
                    description="",
                    employment_type=_employment(j.get("employment_type")),
                    posting_status="open",
                    verification_reason=LISTED,
                )
            )
        return jobs


class SmartRecruitersSource(JobSource):
    """Only used for boards the web search finds; not a setting."""

    name = "smartrecruiters"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        return []

    def fetch_board(self, company: str, country: str | None = None) -> list[RawJob]:
        params = {"limit": 100, **({"country": country} if country else {})}
        data = self.get_json(f"https://api.smartrecruiters.com/v1/companies/{company}/postings", **params)
        jobs = []
        for j in data.get("content", []):
            place = j.get("location") or {}
            location = place.get("fullLocation") or place.get("city")
            jobs.append(
                RawJob(
                    source=self.name,
                    url=f"https://jobs.smartrecruiters.com/{company}/{j['id']}",
                    company=(j.get("company") or {}).get("name") or _company_name(company),
                    title=j["name"].strip(),
                    location=location,
                    remote=bool(place.get("remote")) or looks_remote(location),
                    posted_at=parse_iso(j.get("releasedDate")),
                    description="",
                    employment_type=_employment((j.get("typeOfEmployment") or {}).get("label")),
                    posting_status="open",
                    verification_reason=LISTED,
                )
            )
        return jobs

