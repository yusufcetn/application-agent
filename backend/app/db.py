from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, Column, inspect, text
from sqlmodel import Field, Session, SQLModel, create_engine

from app.config import get_settings


class ProfileRow(SQLModel, table=True):
    __tablename__ = "profile"
    id: int = Field(default=1, primary_key=True)
    data: dict = Field(sa_column=Column(JSON, nullable=False))


class SettingsRow(SQLModel, table=True):
    __tablename__ = "settings"
    id: int = Field(default=1, primary_key=True)
    data: dict = Field(sa_column=Column(JSON, nullable=False))


class ProjectRow(SQLModel, table=True):
    __tablename__ = "project"
    id: str = Field(primary_key=True)
    data: dict = Field(sa_column=Column(JSON, nullable=False))


class JobRow(SQLModel, table=True):
    __tablename__ = "job"
    id: str = Field(primary_key=True)
    source: str
    url: str = Field(index=True, unique=True)
    company: str
    title: str
    location: str | None = None
    remote: bool | None = None
    seniority: str | None = None
    posted_at: datetime | None = None
    found_at: datetime
    description: str = ""
    # Internal: the user pasted the posting text, so never replace it by fetching the page.
    description_pasted: bool = False
    score: int | None = Field(default=None, index=True)
    score_reason: str | None = None
    status: str = Field(default="new", index=True)
    package_status: str = "none"
    package_error: str | None = None
    notes: str = ""


class PackageRow(SQLModel, table=True):
    __tablename__ = "package"
    job_id: str = Field(primary_key=True, foreign_key="job.id")
    # Public package fields (see schemas.Package) plus the tailored CV used for the PDF.
    data: dict = Field(sa_column=Column(JSON, nullable=False))


class SearchRunRow(SQLModel, table=True):
    __tablename__ = "search_run"
    id: str = Field(primary_key=True)
    status: str = Field(index=True)
    started_at: datetime = Field(index=True)
    finished_at: datetime | None = None
    jobs_found: int = 0
    jobs_new: int = 0
    jobs_above_threshold: int = 0
    error: str | None = None


class SeenPostingRow(SQLModel, table=True):
    """Postings that were scored but not kept, and alert emails already read (url
    "email:<Message-ID>"), so later runs don't pay the LLM for them again."""

    __tablename__ = "seen_posting"
    url: str = Field(primary_key=True)
    seen_at: datetime


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})
    return _engine


def _add_missing_columns(engine) -> None:
    """create_all() doesn't touch existing tables, so databases from older versions
    would miss new columns. Add them (new columns are always nullable or defaulted)."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing:
                    col_type = column.type.compile(engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))


def init_db() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _add_missing_columns(engine)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
