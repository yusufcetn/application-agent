import pytest

from app import config

# What `tailscale serve` adds when it forwards a request from the phone.
VIA_TAILSCALE = {"X-Forwarded-For": "100.101.102.103", "Tailscale-User-Login": "me@example.com"}


@pytest.fixture
def with_token(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "gizli-anahtar")
    config.get_settings.cache_clear()
    return client


def test_local_use_needs_no_token(client):
    assert client.get("/api/profile").status_code == 200
    assert client.get("/api/auth/status").json() == {"token_required": False, "authenticated": True}


def test_remote_access_is_refused_without_configured_token(client):
    res = client.get("/api/profile", headers=VIA_TAILSCALE)
    assert res.status_code == 403
    assert "API_TOKEN" in res.json()["detail"]
    assert client.get("/api/auth/status", headers=VIA_TAILSCALE).json()["token_required"] is True


def test_token_required_everywhere_once_set(with_token):
    client = with_token
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile", headers=VIA_TAILSCALE).status_code == 401
    assert client.get("/api/health").status_code == 200  # stays public
    assert client.get("/api/auth/status").json() == {"token_required": True, "authenticated": False}


def test_bearer_header(with_token):
    ok = with_token.get("/api/profile", headers={"Authorization": "Bearer gizli-anahtar"})
    bad = with_token.get("/api/profile", headers={"Authorization": "Bearer yanlis"})
    assert ok.status_code == 200 and bad.status_code == 401


def test_login_sets_cookie_for_plain_links(with_token):
    client = with_token
    assert client.post("/api/auth/login", json={"token": "yanlis"}).status_code == 401

    res = client.post("/api/auth/login", json={"token": " gizli-anahtar "}, headers=VIA_TAILSCALE)
    assert res.status_code == 204
    cookie = res.cookies.get("apply_agent_session")
    assert cookie and "gizli-anahtar" not in cookie  # stores a hash, not the token

    assert client.get("/api/profile", headers=VIA_TAILSCALE).status_code == 200
    assert client.get("/api/auth/status").json()["authenticated"] is True

    client.post("/api/auth/logout")
    assert client.get("/api/profile").status_code == 401


def test_non_ascii_tokens_are_rejected_not_crashing(with_token, monkeypatch):
    client = with_token
    assert client.post("/api/auth/login", json={"token": "hatalı"}).status_code == 401

    monkeypatch.setenv("API_TOKEN", "gizli-şifre-ığü")
    config.get_settings.cache_clear()
    assert client.post("/api/auth/login", json={"token": "gizli-şifre-ığü"}).status_code == 204
    assert client.get("/api/profile").status_code == 200


def test_changing_token_invalidates_sessions(with_token, monkeypatch):
    client = with_token
    client.post("/api/auth/login", json={"token": "gizli-anahtar"})
    monkeypatch.setenv("API_TOKEN", "yeni-anahtar")
    config.get_settings.cache_clear()
    assert client.get("/api/profile").status_code == 401


def test_frontend_is_served_with_spa_fallback(client, tmp_path, monkeypatch):
    from app.frontend import mount_frontend
    from app.main import app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("gizli", encoding="utf-8")
    original_routes = list(app.router.routes)
    app.router.routes = [r for r in original_routes if getattr(r, "path", "") != "/{path:path}"]
    mount_frontend(app, dist)
    try:
        assert client.get("/").text == "<html>app</html>"
        assert client.get("/jobs/job_123").text == "<html>app</html>"  # client-side route
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert "gizli" not in client.get("/../secret.txt").text
        assert client.get("/api/does-not-exist").status_code == 404
    finally:
        app.router.routes = original_routes
