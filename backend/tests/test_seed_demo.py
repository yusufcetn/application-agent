import sys


def test_seed_demo_fills_every_ui_state(client, monkeypatch):
    from scripts import seed_demo

    monkeypatch.setattr(sys, "argv", ["seed_demo", "--force"])
    seed_demo.main()

    jobs = {j["id"]: j for j in client.get("/api/jobs").json()}
    assert {j["package_status"] for j in jobs.values()} == {"ready", "failed", "none"}
    assert {"new", "applied", "interview"} <= {j["status"] for j in jobs.values()}
    assert jobs["job_failed"]["package_error"]
    assert client.get("/api/jobs/job_ready/package").status_code == 200
    assert client.get("/api/jobs/job_ready/cv.pdf").content.startswith(b"%PDF")
    assert client.get("/api/profile").json()["full_name"] == "Ad Soyad"
    assert len(client.get("/api/projects").json()) == 2
    assert client.get("/api/search/runs", params={"limit": 1}).json()[0]["id"] == "run_demo"
