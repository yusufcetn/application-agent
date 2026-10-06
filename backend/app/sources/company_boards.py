"""ATS job boards of specific companies (slugs come from the settings)."""

from app.schemas import SearchSettings
from app.sources.base import JobSource, RawJob, from_timestamp, looks_remote, parse_iso
from app.text import html_to_plain


def _company_name(slug: str) -> str:
    return slug.replace("-", " ").title()


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        jobs = []
        for board in settings.sources.greenhouse:
            data = self.get_json(
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", content="true"
            )
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
                    )
                )
        return jobs


class LeverSource(JobSource):
    name = "lever"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        jobs = []
        for company in settings.sources.lever:
            for j in self.get_json(f"https://api.lever.co/v0/postings/{company}", mode="json"):
                location = (j.get("categories") or {}).get("location")
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
                    )
                )
        return jobs


class AshbySource(JobSource):
    name = "ashby"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        jobs = []
        for org in settings.sources.ashby:
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
                        location=j.get("location"),
                        remote=bool(j.get("isRemote")) or j.get("workplaceType") == "Remote",
                        posted_at=parse_iso(j.get("publishedAt")),
                        description=j.get("descriptionPlain")
                        or html_to_plain(j.get("descriptionHtml", "")),
                    )
                )
        return jobs
