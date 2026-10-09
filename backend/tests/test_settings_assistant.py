import httpx
import pytest

from app.llm import settings_assistant as assistant
from app.llm.runner import LLMError, LLMNotConfiguredError


def test_role_suggestions_normalize_and_do_not_save(client, monkeypatch):
    before = client.get("/api/settings").json()
    calls = []

    def run(system, prompt, schema, **kwargs):
        calls.append((system, prompt, schema, kwargs))
        return assistant.RoleSuggestions(target_roles=[
            " Python  Developer ", "python developer", "", "x" * 81, "Backend Engineer",
        ])

    monkeypatch.setattr(assistant, "run_structured", run)
    response = client.post("/api/settings/suggest-roles", json={"description": " Python backend "})
    assert response.status_code == 200
    assert response.json() == {"target_roles": ["Python Developer", "Backend Engineer"]}
    assert calls[0][3] == {}  # role suggestion cannot browse
    assert '"description": "Python backend"' in calls[0][1]
    assert client.get("/api/settings").json() == before


def test_empty_role_answer_is_asked_again_once(client, monkeypatch):
    calls = []

    def run(system, prompt, schema, **kwargs):
        calls.append(system)
        return assistant.RoleSuggestions(target_roles=[] if len(calls) == 1 else ["AI Engineer"])

    monkeypatch.setattr(assistant, "run_structured", run)
    response = client.post("/api/settings/suggest-roles", json={"description": "yazılım, ai engineer"})
    assert response.json() == {"target_roles": ["AI Engineer"]}
    assert len(calls) == 2 and assistant.EMPTY_ROLES_RETRY in calls[1]

    calls.clear()
    monkeypatch.setattr(assistant, "run_structured", lambda system, *a, **k: calls.append(system) or assistant.RoleSuggestions())
    assert client.post("/api/settings/suggest-roles", json={"description": "bilmiyorum"}).json() == {"target_roles": []}
    assert len(calls) == 2


@pytest.mark.parametrize("description", ["", "  ", "ab", "x" * 2001])
@pytest.mark.parametrize("endpoint", ["suggest-roles", "discover-companies"])
def test_invalid_input_never_calls_model(client, monkeypatch, description, endpoint):
    def run(*args, **kwargs):
        pytest.fail("invalid request reached the model")

    monkeypatch.setattr(assistant, "run_structured", run)
    assert client.post(f"/api/settings/{endpoint}", json={"description": description}).status_code == 422


def test_company_context_is_bounded(client):
    for change in [{"locations": ["x" * 121]}, {"target_roles": ["Backend"] * 31}]:
        response = client.post("/api/settings/discover-companies", json={"description": "Games", **change})
        assert response.status_code == 422


@pytest.mark.parametrize("url", [
    "https://jobs.lever.co.evil.test/acme", "https://evil.jobs.lever.co/acme",
    "http://jobs.lever.co/acme", "https://user:pass@jobs.lever.co/acme",
    "https://jobs.lever.co:8080/acme", "https://jobs.lever.co:bad/acme",
    "https://jobs.lever.co/%2e%2e", "https://jobs.lever.co/..",
    "https://jobs.lever.co/", "https://boards.greenhouse.io/embed/job_board?for=acme",
    "https://jobs.eu.lever.co/acme", "file:///acme",
])
def test_board_parser_rejects_unsupported_and_unsafe_urls(url):
    assert assistant.parse_board(url) is None


def test_board_parser_canonicalizes_posting_links():
    assert assistant.parse_board("https://boards.greenhouse.io/acme/jobs/123?x=1#apply") == (
        "greenhouse", "acme", "https://job-boards.greenhouse.io/acme",
    )
    assert assistant.parse_board("https://jobs.ashbyhq.com/Acme-Co/uuid") == (
        "ashby", "Acme-Co", "https://jobs.ashbyhq.com/Acme-Co",
    )


def test_discovery_checks_fixed_api_urls_deduplicates_and_keeps_partial_results(client, monkeypatch):
    before = client.get("/api/settings").json()
    companies = [
        assistant.CompanyCandidate(name="Acme", url="https://jobs.lever.co/acme/123", reason="Oyun şirketi."),
        assistant.CompanyCandidate(name="Acme", url="https://jobs.lever.co/acme", reason="Oyun şirketi."),
        assistant.CompanyCandidate(name="Empty", url="https://jobs.lever.co/empty", reason="Oyun."),
        assistant.CompanyCandidate(name="Ash", url="https://jobs.ashbyhq.com/ash", reason="Oyun."),
        assistant.CompanyCandidate(name="Bad", url="https://evil.test/bad", reason="Oyun."),
        assistant.CompanyCandidate(name="Gone", url="https://boards.greenhouse.io/gone", reason="Oyun."),
    ]
    calls = []
    visited = []

    def run(system, prompt, schema, **kwargs):
        calls.append((prompt, kwargs))
        return assistant.CompanySearchResult(companies=companies)

    def handler(request):
        visited.append(str(request.url))
        if request.url.host == "api.ashbyhq.com":
            return httpx.Response(200, json={"jobs": []})
        if request.url.path.endswith("/acme"):
            return httpx.Response(200, json=[{"hostedUrl": "https://jobs.lever.co/acme/1", "text": "Engineer"}])
        if request.url.path.endswith("/empty"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    original_client = httpx.Client
    monkeypatch.setattr(assistant, "run_structured", run)
    monkeypatch.setattr(assistant.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler), **kwargs,
    ))
    response = client.post("/api/settings/discover-companies", json={
        "description": "Türkiye oyun şirketleri", "target_roles": ["Backend"],
        "locations": ["Türkiye"], "remote_only": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert [(c["source"], c["slug"]) for c in data["companies"]] == [("lever", "acme"), ("ashby", "ash")]
    assert data["companies"][0]["url"] == "https://jobs.lever.co/acme"
    assert "3 aday" in data["warnings"][0]
    assert len(visited) == 4 and all("evil" not in url for url in visited)
    assert calls[0][1]["web"] is True
    assert '"remote_only":true' in calls[0][0]
    assert client.get("/api/settings").json() == before


@pytest.mark.parametrize("response", [
    httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"}),
    httpx.Response(200, text="not json"), httpx.Response(200, json={"jobs": None}),
    httpx.Response(200, json={"jobs": [], "error": "not found"}),
])
def test_verification_rejects_redirects_and_bad_responses(response):
    visited = []

    def handler(request):
        visited.append(request.url)
        return response

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        assert assistant._verify_board(client, "greenhouse", "acme") is False
    assert len(visited) == 1


def test_verification_timeout_is_partial_failure():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert assistant._verify_board(client, "lever", "acme") is False


def test_no_matches_has_clear_message(client, monkeypatch):
    monkeypatch.setattr(assistant, "run_structured", lambda *args, **kwargs: assistant.CompanySearchResult())
    response = client.post("/api/settings/discover-companies", json={"description": "Games"})
    assert response.json()["companies"] == []
    assert "bulunamadı" in response.json()["warnings"][0]


@pytest.mark.parametrize("error,status", [(LLMError("Model hatası"), 502), (LLMNotConfiguredError("CLI kurulu değil"), 503)])
def test_provider_errors_use_existing_api_handlers(client, monkeypatch, error, status):
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr(assistant, "run_structured", run)
    response = client.post("/api/settings/suggest-roles", json={"description": "Backend"})
    assert response.status_code == status
    assert response.json()["detail"] == str(error)
