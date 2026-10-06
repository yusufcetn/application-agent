"""Serve the built frontend (frontend/dist) so a phone needs just one address."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "Bulunamadı.")
        if not index.exists():
            raise HTTPException(404, "Frontend derlenmemiş: frontend klasöründe `npm run build` çalıştır.")
        file = (dist / path).resolve()
        if path and file.is_file() and file.is_relative_to(dist.resolve()):
            return FileResponse(file)
        return FileResponse(index)  # client-side routes like /jobs/123
