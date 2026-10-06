"""Access token for using the app from other devices (e.g. a phone over Tailscale).

Without API_TOKEN the API only answers requests made directly on this computer.
With it, every /api request needs the token, either as a Bearer header or as the
cookie set by POST /api/auth/login (so plain links like the CV PDF work too).
"""

import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_settings

COOKIE_NAME = "apply_agent_session"
COOKIE_MAX_AGE = 365 * 24 * 3600
PUBLIC_PATHS = {"/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/logout"}
# Headers added by reverse proxies such as `tailscale serve`.
PROXY_HEADERS = ("x-forwarded-for", "tailscale-user-login", "forwarded")

router = APIRouter(tags=["auth"])


def _session_value(token: str) -> str:
    # The cookie holds a hash, not the token; changing API_TOKEN logs every device out.
    return hashlib.sha256(f"apply-agent:{token}".encode()).hexdigest()


def _same(given: str, expected: str) -> bool:
    # compare_digest raises TypeError on non-ASCII str, so compare bytes instead.
    return hmac.compare_digest(given.encode(), expected.encode())


def _is_proxied(request: Request) -> bool:
    return any(h in request.headers for h in PROXY_HEADERS)


def is_authenticated(request: Request) -> bool:
    token = get_settings().api_token
    if not token:
        return not _is_proxied(request)
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer ") and _same(header[7:], token):
        return True
    cookie = request.cookies.get(COOKIE_NAME, "")
    return _same(cookie, _session_value(token))


async def require_token(request: Request, call_next):
    if request.url.path.startswith("/api") and request.url.path not in PUBLIC_PATHS:
        if not is_authenticated(request):
            if not get_settings().api_token:
                detail = "Uzaktan erişim için .env dosyasında API_TOKEN ayarlanmalı."
                return JSONResponse(status_code=403, content={"detail": detail})
            return JSONResponse(status_code=401, content={"detail": "Erişim anahtarı gerekli."})
    return await call_next(request)


class AuthStatus(BaseModel):
    token_required: bool
    authenticated: bool


class LoginIn(BaseModel):
    token: str


@router.get("/auth/status")
def auth_status(request: Request) -> AuthStatus:
    required = bool(get_settings().api_token) or _is_proxied(request)
    return AuthStatus(token_required=required, authenticated=is_authenticated(request))


@router.post("/auth/login", status_code=204)
def login(body: LoginIn, request: Request) -> Response:
    token = get_settings().api_token
    if not token:
        raise HTTPException(403, "Uzaktan erişim için .env dosyasında API_TOKEN ayarlanmalı.")
    if not _same(body.token.strip(), token):
        raise HTTPException(401, "Erişim anahtarı yanlış.")
    response = Response(status_code=204)
    response.set_cookie(
        COOKIE_NAME,
        _session_value(token),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return response


@router.post("/auth/logout", status_code=204)
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME)
    return response
