from datetime import UTC, date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, col, select

from app.db import JobRow, PackageRow, get_session
from app.jobs.fetch import FetchError, fetch_posting_text
from app.jobs.urls import normalize_url
from app.llm.job_extract import extract_job
from app.schemas import (
    Job,
    JobStatus,
    JobUpdate,
    ManualJobIn,
    Package,
    PackageAccepted,
    new_id,
)
from app.text import fold
from app.services.packages import (
    cv_pdf_path,
    generate_package,
    load_profile,
    load_search_settings,
)

router = APIRouter(tags=["jobs"])

def _get_job_row(session: Session, job_id: str) -> JobRow:
    row = session.get(JobRow, job_id)
    if not row:
        raise HTTPException(404, "İlan bulunamadı.")
    return row


def _to_job(row: JobRow) -> Job:
    return Job.model_validate(row, from_attributes=True)


def _parse_date(value: str | None) -> datetime | None:
    try:
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), UTC) if value else None
    except ValueError:
        return None


def _start_package(row: JobRow, session: Session, background: BackgroundTasks) -> None:
    if not load_profile(session).full_name:
        raise HTTPException(409, "Paket hazırlamak için önce profilini doldur.")
    row.package_status = "generating"
    row.package_error = None
    session.add(row)
    session.commit()
    background.add_task(generate_package, row.id)


@router.get("/jobs")
def list_jobs(
    status: list[JobStatus] | None = Query(None),
    min_score: int | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
) -> list[Job]:
    """Descriptions are left out of the list to keep it light; fetch /jobs/{id} for them."""
    stmt = select(JobRow)
    if status:
        stmt = stmt.where(col(JobRow.status).in_(status))
    if min_score is not None:
        stmt = stmt.where(col(JobRow.score) >= min_score)
    stmt = stmt.order_by(col(JobRow.score).desc().nulls_last(), col(JobRow.found_at).desc())
    rows = session.exec(stmt).all()
    if q:
        # Filtered in Python: SQLite LIKE only ignores case for ASCII ("örnek" vs "Örnek").
        needle = fold(q)
        rows = [r for r in rows if needle in fold(f"{r.company} {r.title}")]
    return [_to_job(r).model_copy(update={"description": ""}) for r in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, session: Session = Depends(get_session)) -> Job:
    return _to_job(_get_job_row(session, job_id))


@router.post("/jobs/manual", status_code=201)
def add_manual_job(
    body: ManualJobIn,
    response: Response,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Job:
    url = normalize_url(body.url)
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "Geçerli bir ilan linki girin.")
    existing = session.exec(select(JobRow).where(JobRow.url == url)).first()
    if existing:
        response.status_code = 200
        return _to_job(existing)

    try:
        page_text = body.text or fetch_posting_text(url)
    except FetchError as e:
        raise HTTPException(422, f"{e} İlan metnini kopyalayıp yapıştırarak tekrar dene.") from e
    extracted = extract_job(page_text, url)
    if not extracted.is_job_posting:
        raise HTTPException(
            422,
            "Bu sayfada bir iş ilanı bulunamadı (giriş ekranı veya süresi dolmuş ilan olabilir). "
            "İlan metnini kopyalayıp yapıştırarak tekrar dene.",
        )

    row = JobRow(
        id=new_id("job"),
        source="manual",
        url=url,
        company=extracted.company,
        title=extracted.title,
        location=extracted.location,
        remote=extracted.remote,
        seniority=extracted.seniority,
        posted_at=_parse_date(extracted.posted_at),
        found_at=datetime.now(UTC),
        description=extracted.description,
    )
    session.add(row)
    session.commit()
    if load_search_settings(session).auto_package and load_profile(session).full_name:
        _start_package(row, session, background)
    return _to_job(row)


@router.patch("/jobs/{job_id}")
def update_job(job_id: str, body: JobUpdate, session: Session = Depends(get_session)) -> Job:
    row = _get_job_row(session, job_id)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(row, field, value)
    if body.description:
        row.description_pasted = True
    session.add(row)
    session.commit()
    return _to_job(row)


@router.post("/jobs/{job_id}/package", status_code=202)
def create_package(
    job_id: str, background: BackgroundTasks, session: Session = Depends(get_session)
) -> PackageAccepted:
    row = _get_job_row(session, job_id)
    if row.package_status != "generating":
        _start_package(row, session, background)
    return PackageAccepted(job_id=job_id, package_status=row.package_status)


@router.get("/jobs/{job_id}/package")
def get_package(job_id: str, session: Session = Depends(get_session)) -> Package:
    _get_job_row(session, job_id)
    row = session.get(PackageRow, job_id)
    if not row:
        raise HTTPException(404, "Bu ilan için henüz paket yok.")
    return Package.model_validate(row.data)


@router.get("/jobs/{job_id}/cv.pdf")
def get_cv_pdf(job_id: str, session: Session = Depends(get_session)) -> FileResponse:
    job = _get_job_row(session, job_id)
    path = cv_pdf_path(job_id)
    if not path.exists():
        raise HTTPException(404, "Bu ilan için henüz CV yok.")
    name = load_profile(session).full_name or "CV"
    # inline so the browser can preview it in an iframe; <a download> still saves it.
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{name} - {job.company} CV.pdf",
        content_disposition_type="inline",
    )
