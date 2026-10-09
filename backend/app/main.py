import logging
from contextlib import asynccontextmanager

from sqlmodel import Session

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app import auth
from app.api import jobs, profile, projects, search, settings
from app.config import allowed_hosts, get_settings
from app.db import get_engine, init_db
from app.frontend import mount_frontend
from app.llm.runner import LLMError, LLMNotConfiguredError
from app.search import scheduler
from app.search.service import fail_interrupted_runs
from app.services.packages import load_search_settings, reset_interrupted_packages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    reset_interrupted_packages()
    fail_interrupted_runs()
    if get_settings().scheduler_enabled:
        with Session(get_engine()) as session:
            scheduler.start(load_search_settings(session).schedule_cron)
    yield
    scheduler.shutdown()


app = FastAPI(title="Apply Agent", lifespan=lifespan)
app.middleware("http")(auth.require_token)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last so it runs first: a request for an unknown host never reaches the API.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts(get_settings()))


@app.exception_handler(LLMNotConfiguredError)
def llm_not_configured_handler(_: Request, exc: LLMNotConfiguredError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(LLMError)
def llm_error_handler(_: Request, exc: LLMError) -> JSONResponse:
    logger.error("LLM call failed: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(profile.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
# Last: catches every non-API path for the single-page app.
mount_frontend(app, get_settings().frontend_dist)
