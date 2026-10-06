import json

from tests.conftest import load_example


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_profile_empty_then_saved(client):
    assert client.get("/api/profile").json()["full_name"] == ""

    body = load_example("profile")
    saved = client.put("/api/profile", json=body).json()
    assert saved["full_name"] == body["full_name"]
    assert saved["updated_at"] is not None

    fetched = client.get("/api/profile").json()
    assert fetched == saved


def test_profile_generates_missing_ids(client):
    body = load_example("profile")
    del body["experience"][0]["id"]
    saved = client.put("/api/profile", json=body).json()
    assert saved["experience"][0]["id"].startswith("exp_")


def test_projects_crud(client):
    body = load_example("project")
    del body["id"]

    created = client.post("/api/projects", json=body)
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert project_id.startswith("prj_")

    assert [p["id"] for p in client.get("/api/projects").json()] == [project_id]

    body["name"] = "Yeni ad"
    updated = client.put(f"/api/projects/{project_id}", json=body).json()
    assert updated["name"] == "Yeni ad"

    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get("/api/projects").json() == []
    assert client.delete(f"/api/projects/{project_id}").status_code == 404


def test_settings_default_then_saved(client):
    assert client.get("/api/settings").json()["min_score"] == 70

    body = load_example("settings")
    body["min_score"] = 85
    assert client.put("/api/settings", json=body).json()["min_score"] == 85
    assert client.get("/api/settings").json()["min_score"] == 85


def test_settings_rejects_invalid_score(client):
    body = load_example("settings")
    body["min_score"] = 150
    assert client.put("/api/settings", json=body).status_code == 422


def test_import_rejects_unsupported_file(client):
    res = client.post("/api/profile/import", files={"file": ("cv.png", b"x", "image/png")})
    assert res.status_code == 415



def _json_file(name: str, data) -> tuple:
    return ("files", (name, json.dumps(data, ensure_ascii=False).encode(), "application/json"))


def test_project_import_creates_updates_and_reports_errors(client):
    project = load_example("project")
    other = {**project, "id": "prj_2", "name": "Hava Durumu Botu"}
    res = client.post(
        "/api/projects/import",
        files=[
            _json_file("apply-agent.json", project),
            _json_file("liste.json", [other, {"name": 42}]),
            ("files", ("bozuk.json", b"{not json", "application/json")),
        ],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [p["id"] for p in body["created"]] == ["prj_1", "prj_2"]  # ids from the files are kept
    assert body["updated"] == []
    assert [e["file"] for e in body["errors"]] == ["liste.json #2", "bozuk.json"]
    assert "name" in body["errors"][0]["message"]
    assert body["errors"][1]["message"] == "Geçerli bir JSON değil (satır 1, sütun 2)."

    # Importing again updates instead of duplicating: by id, or by name when there is no id.
    edited = {**project, "summary": "Güncellendi"}
    no_id = {k: v for k, v in other.items() if k != "id"} | {"name": "HAVA DURUMU BOTU"}
    body = client.post(
        "/api/projects/import", files=[_json_file("a.json", edited), _json_file("b.json", no_id)]
    ).json()
    assert body["created"] == [] and [p["id"] for p in body["updated"]] == ["prj_1", "prj_2"]
    projects = {p["id"]: p for p in client.get("/api/projects").json()}
    assert len(projects) == 2 and projects["prj_1"]["summary"] == "Güncellendi"


def test_project_import_without_ids_creates_new_ids(client):
    project = {k: v for k, v in load_example("project").items() if k != "id"}
    body = client.post("/api/projects/import", files=[_json_file("p.json", project)]).json()
    assert body["created"][0]["id"].startswith("prj_")
