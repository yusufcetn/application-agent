"""Public job boards that list many companies."""

from app.config import get_settings
from app.schemas import SearchSettings
from app.sources.base import JobSource, RawJob, from_timestamp, looks_remote, parse_iso
from app.text import html_to_plain


class RemoteOKSource(JobSource):
    name = "remoteok"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        data = self.get_json("https://remoteok.com/api")
        return [
            RawJob(
                source=self.name,
                url=j["url"],
                company=j.get("company", ""),
                title=j.get("position", "").strip(),
                location=j.get("location") or "Remote",
                remote=True,
                posted_at=parse_iso(j.get("date")),
                description=html_to_plain(j.get("description", "")),
            )
            for j in data
            if isinstance(j, dict) and j.get("position")  # first item is a legal notice
        ]


class RemotiveSource(JobSource):
    name = "remotive"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        jobs: dict[str, RawJob] = {}
        for role in settings.target_roles or [""]:
            data = self.get_json("https://remotive.com/api/remote-jobs", search=role, limit=100)
            for j in data.get("jobs", []):
                jobs[j["url"]] = RawJob(
                    source=self.name,
                    url=j["url"],
                    company=j.get("company_name", ""),
                    title=j.get("title", "").strip(),
                    location=j.get("candidate_required_location") or "Remote",
                    remote=True,
                    posted_at=parse_iso(j.get("publication_date")),
                    description=html_to_plain(j.get("description", "")),
                )
        return list(jobs.values())


class ArbeitnowSource(JobSource):
    name = "arbeitnow"
    pages = 3

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        jobs = []
        for page in range(1, self.pages + 1):
            data = self.get_json("https://www.arbeitnow.com/api/job-board-api", page=page)
            for j in data.get("data", []):
                jobs.append(
                    RawJob(
                        source=self.name,
                        url=j["url"],
                        company=j.get("company_name", ""),
                        title=j.get("title", "").strip(),
                        location=j.get("location"),
                        remote=bool(j.get("remote")) or looks_remote(j.get("location")),
                        posted_at=from_timestamp(j.get("created_at")),
                        description=html_to_plain(j.get("description", "")),
                    )
                )
            if not (data.get("links") or {}).get("next"):
                break
        return jobs


class AdzunaSource(JobSource):
    """Needs ADZUNA_APP_ID / ADZUNA_APP_KEY. Descriptions are short snippets; the full
    posting page is fetched when a package is generated."""

    name = "adzuna"

    def fetch(self, settings: SearchSettings) -> list[RawJob]:
        config = get_settings()
        app_id, app_key = config.adzuna_app_id, config.adzuna_app_key
        if not (app_id and app_key):
            raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY ayarlanmamış.")
        country = config.adzuna_country
        locations = [loc for loc in settings.locations if not looks_remote(loc)] or [""]
        jobs: dict[str, RawJob] = {}
        for role in settings.target_roles or [""]:
            for where in locations:
                data = self.get_json(
                    f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                    app_id=app_id,
                    app_key=app_key,
                    what=role,
                    where=where,
                    results_per_page=50,
                )
                for j in data.get("results", []):
                    location = (j.get("location") or {}).get("display_name")
                    jobs[j["redirect_url"]] = RawJob(
                        source=self.name,
                        url=j["redirect_url"],
                        company=(j.get("company") or {}).get("display_name", ""),
                        title=html_to_plain(j.get("title", "")),
                        location=location,
                        remote=looks_remote(location, j.get("title")),
                        posted_at=parse_iso(j.get("created")),
                        description=html_to_plain(j.get("description", "")),
                    )
        return list(jobs.values())
