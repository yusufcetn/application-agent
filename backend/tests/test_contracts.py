"""The example JSON files are the API contract; our models must accept them unchanged."""

from app.schemas import Job, Profile, Project, SearchSettings
from tests.conftest import load_example


def test_profile_example_roundtrip():
    data = load_example("profile")
    assert Profile.model_validate(data).model_dump(mode="json") == data


def test_project_example_roundtrip():
    data = load_example("project")
    assert Project.model_validate(data).model_dump(mode="json") == data


def test_settings_example_roundtrip():
    data = load_example("settings")
    assert SearchSettings.model_validate(data).model_dump(mode="json") == data


def test_job_example_roundtrip():
    data = load_example("job")
    assert Job.model_validate(data).model_dump(mode="json") == data
