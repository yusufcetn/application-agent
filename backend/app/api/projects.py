import json

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlmodel import Session, select

from app.db import ProjectRow, get_session
from app.schemas import ImportIssue, Project, ProjectImportResult, ProjectIn, new_id
from app.text import fold

router = APIRouter(tags=["projects"])


def _get_row(session: Session, project_id: str) -> ProjectRow:
    row = session.get(ProjectRow, project_id)
    if not row:
        raise HTTPException(404, "Proje bulunamadı.")
    return row


@router.get("/projects")
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    rows = session.exec(select(ProjectRow)).all()
    return [Project.model_validate(r.data) for r in rows]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, session: Session = Depends(get_session)) -> Project:
    project = Project(id=new_id("prj"), **body.model_dump())
    session.add(ProjectRow(id=project.id, data=project.model_dump(mode="json")))
    session.commit()
    return project


@router.put("/projects/{project_id}")
def update_project(
    project_id: str, body: ProjectIn, session: Session = Depends(get_session)
) -> Project:
    row = _get_row(session, project_id)
    project = Project(id=project_id, **body.model_dump())
    row.data = project.model_dump(mode="json")
    session.add(row)
    session.commit()
    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(get_session)) -> Response:
    session.delete(_get_row(session, project_id))
    session.commit()
    return Response(status_code=204)


MAX_IMPORT_FILE_BYTES = 1024 * 1024


def _describe(error: ValidationError) -> str:
    first = error.errors()[0]
    field = ".".join(str(p) for p in first["loc"]) or "proje"
    return f"'{field}' alanı geçersiz ({first['msg']})"


@router.post("/projects/import")
def import_projects(
    files: list[UploadFile], session: Session = Depends(get_session)
) -> ProjectImportResult:
    """Import projects from JSON files (one project or a list per file), in the same shape
    as GET /projects. A project whose id or name already exists is updated, not duplicated,
    so editing the files and importing again is safe."""
    rows = session.exec(select(ProjectRow)).all()
    by_id = {r.id: r for r in rows}
    by_name = {fold(r.data.get("name", "")): r for r in rows}
    result = ProjectImportResult()

    for upload in files:
        name = upload.filename or "dosya"
        raw = upload.file.read(MAX_IMPORT_FILE_BYTES + 1)
        if len(raw) > MAX_IMPORT_FILE_BYTES:
            result.errors.append(ImportIssue(file=name, message="Dosya 1 MB'tan büyük."))
            continue
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except UnicodeDecodeError:
            result.errors.append(ImportIssue(file=name, message="Dosya UTF-8 metin değil."))
            continue
        except json.JSONDecodeError as e:
            message = f"Geçerli bir JSON değil (satır {e.lineno}, sütun {e.colno})."
            result.errors.append(ImportIssue(file=name, message=message))
            continue
        items = data if isinstance(data, list) else [data]
        for index, item in enumerate(items):
            label = name if len(items) == 1 else f"{name} #{index + 1}"
            if not isinstance(item, dict):
                result.errors.append(ImportIssue(file=label, message="Proje bir JSON nesnesi olmalı."))
                continue
            try:
                body = ProjectIn.model_validate(item)
            except ValidationError as e:
                result.errors.append(ImportIssue(file=label, message=_describe(e)))
                continue

            given_id = item.get("id") if isinstance(item.get("id"), str) else None
            existing = by_id.get(given_id) if given_id else None
            existing = existing or by_name.get(fold(body.name))
            project_id = existing.id if existing else (given_id or new_id("prj"))
            project = Project(id=project_id, **body.model_dump())
            data_json = project.model_dump(mode="json")
            if existing:
                existing.data = data_json
                session.add(existing)
                result.updated.append(project)
            else:
                row = ProjectRow(id=project_id, data=data_json)
                session.add(row)
                by_id[project_id] = row
                by_name[fold(body.name)] = row
                result.created.append(project)
    session.commit()
    return result
