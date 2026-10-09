from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlmodel import Session

from app.db import ProfileRow, get_session
from app.llm.profile_import import UnsupportedFileError, extract_profile
from app.schemas import Profile
from app.services.packages import rerender_cvs

router = APIRouter(tags=["profile"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("/profile")
def get_profile(session: Session = Depends(get_session)) -> Profile:
    row = session.get(ProfileRow, 1)
    return Profile.model_validate(row.data) if row else Profile()


@router.put("/profile")
def put_profile(
    profile: Profile, background: BackgroundTasks, session: Session = Depends(get_session)
) -> Profile:
    profile.updated_at = datetime.now(UTC)
    data = profile.model_dump(mode="json")
    row = session.get(ProfileRow, 1)
    if row:
        row.data = data
    else:
        row = ProfileRow(id=1, data=data)
    session.add(row)
    session.commit()
    background.add_task(rerender_cvs)  # contact details and links on the ready CVs
    return profile


@router.post("/profile/import")
def import_profile(file: UploadFile) -> Profile:
    """Extract a profile from an uploaded CV. Returns a preview; does not save."""
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Dosya 10 MB'tan büyük olamaz.")
    try:
        return extract_profile(content, file.filename or "")
    except UnsupportedFileError as e:
        raise HTTPException(415, str(e)) from e
