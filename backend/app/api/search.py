from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlmodel import Session, col, select

from app.db import SearchRunRow, get_session
from app.schemas import SearchRun
from app.search.report import send_run_report
from app.search.service import ProfileMissingError, execute_run, start_run, to_search_run
from app.services.mailer import MailError, MailNotConfiguredError

router = APIRouter(tags=["search"])


@router.post("/search/run", status_code=202)
def run_search(background: BackgroundTasks, response: Response) -> SearchRun:
    """Starts a search, or returns the one already running (200)."""
    try:
        run, created = start_run()
    except ProfileMissingError as e:
        raise HTTPException(409, str(e)) from e
    if created:
        background.add_task(execute_run, run.id)
    else:
        response.status_code = 200
    return run


@router.get("/search/runs")
def list_runs(
    limit: int = Query(10, ge=1, le=100), session: Session = Depends(get_session)
) -> list[SearchRun]:
    """Latest first; `?limit=1` gives the last run for the sidebar."""
    stmt = select(SearchRunRow).order_by(col(SearchRunRow.started_at).desc()).limit(limit)
    return [to_search_run(r) for r in session.exec(stmt).all()]


@router.get("/search/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> SearchRun:
    row = session.get(SearchRunRow, run_id)
    if not row:
        raise HTTPException(404, "Tarama bulunamadı.")
    return to_search_run(row)


@router.post("/search/runs/{run_id}/report")
def send_report(run_id: str, session: Session = Depends(get_session)) -> dict:
    """Emails the daily report for this run now (e.g. to try the email settings)."""
    row = session.get(SearchRunRow, run_id)
    if not row:
        raise HTTPException(404, "Tarama bulunamadı.")
    if row.status == "running":
        raise HTTPException(409, "Tarama bitmeden rapor gönderilemez.")
    try:
        return {"sent_to": send_run_report(session, row)}
    except MailNotConfiguredError as e:
        raise HTTPException(409, str(e)) from e
    except MailError as e:
        raise HTTPException(502, str(e)) from e
