import json
import os
from pathlib import Path

# Before any app import: the developer's personal .env (API_TOKEN, IMAP, LLM settings)
# must not leak into tests.
os.environ["APPLY_AGENT_ENV_FILE"] = ""

import pytest
from fastapi.testclient import TestClient

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"


def load_example(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    from app import config, db

    config.get_settings.cache_clear()
    db._engine = None
    from app.main import app

    with TestClient(app) as c:
        yield c
    db._engine = None
    config.get_settings.cache_clear()
