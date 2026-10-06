import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = re.compile(r"^(utm_|gh_src$|ref$|source$|trk)", re.I)
_LINKEDIN_JOB = re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(?:[^/?#]*-)?(\d+)", re.I)


def normalize_url(url: str) -> str:
    """Same posting shared with different tracking params should be one job."""
    if match := _LINKEDIN_JOB.search(url):
        return f"https://www.linkedin.com/jobs/view/{match.group(1)}"
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING_PARAMS.match(k)]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), "")
    )
