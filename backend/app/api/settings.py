from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import SettingsRow, get_session
from app.schemas import SearchSettings
from app.search import scheduler

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_search_settings(session: Session = Depends(get_session)) -> SearchSettings:
    row = session.get(SettingsRow, 1)
    return SearchSettings.model_validate(row.data) if row else SearchSettings()


@router.put("/settings")
def put_search_settings(
    body: SearchSettings, session: Session = Depends(get_session)
) -> SearchSettings:
    try:
        scheduler.parse_cron(body.schedule_cron)
    except ValueError as e:
        raise HTTPException(422, f"Geçersiz zamanlama ifadesi: {body.schedule_cron}") from e
    row = session.get(SettingsRow, 1) or SettingsRow(id=1, data={})
    row.data = body.model_dump(mode="json")
    session.add(row)
    session.commit()
    scheduler.reschedule(body.schedule_cron)
    return body
