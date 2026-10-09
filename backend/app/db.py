from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import JSON, Column, event, inspect, text
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
    employment_type: str | None = None
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
    # When the user first opened the job; until then a job from the latest run reads "Yeni".
    seen_at: datetime | None = None
    posting_status: str = "unknown"
    last_verified_at: datetime | None = None
    application_deadline: date | None = None
    verification_reason: str | None = None


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
    jobs_scored: int = 0
    jobs_new: int = 0
    jobs_above_threshold: int = 0
    jobs_closed: int = 0
    error: str | None = None
    # Job ids for the daily report: {"new": [...], "closed": [...], "reopened": [...]}.
    summary: dict | None = Field(default=None, sa_column=Column(JSON))


class SeenPostingRow(SQLModel, table=True):
    """Postings that were scored but not kept, so later runs don't pay the LLM for them
    again. Older versions also marked alert emails here ("email:<Message-ID>"); those rows
    are no longer read, see AlertEmailRow."""

    __tablename__ = "seen_posting"
    url: str = Field(primary_key=True)
    seen_at: datetime


class AlertEmailRow(SQLModel, table=True):
    """Job alert emails whose postings were extracted, so each email costs one LLM call."""

    __tablename__ = "alert_email"
    message_id: str = Field(primary_key=True)
    read_at: datetime = Field(index=True)


class AlertPostingRow(SQLModel, table=True):
    """Every posting found in a job alert email, whatever the filters said then. Each run
    filters them again, so a role added later still finds postings in emails already read."""

    __tablename__ = "alert_posting"
    url: str = Field(primary_key=True)
    # The latest email that listed it; the posting is dropped together with that email.
    message_id: str = Field(index=True)
    company: str
    title: str
    location: str | None = None
    remote: bool | None = None
    received_at: datetime | None = None
    description: str = ""


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        # A search run and package building write from different threads: wait for the
        # other writer instead of failing after SQLite's default 5 seconds.
        _engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _sqlite_pragmas)
    return _engine


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    # WAL: readers never wait for the writer, and the writer doesn't wait for readers.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def _sql_default(column) -> str:
    """Existing rows get the column's Python default, so non-null fields stay valid."""
    default = column.default.arg if column.default is not None and column.default.is_scalar else None
    if isinstance(default, bool):
        return f" DEFAULT {int(default)}"
    if isinstance(default, int | float):
        return f" DEFAULT {default}"
    if isinstance(default, str):
        return " DEFAULT '" + default.replace("'", "''") + "'"
    return ""


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
                    conn.execute(
                        text(
                            f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
                            + _sql_default(column)
                        )
                    )


def init_db() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _add_missing_columns(engine)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
