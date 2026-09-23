import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.store import DataStore
from tests.helpers import sign_in

DEMO = Path(__file__).resolve().parents[2] / "docs" / "demo"


def test_judge_demo_upload_recommendation_completion_and_unknown_role(monkeypatch):
    monkeypatch.setattr(main, "store", DataStore())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    files = {
        "employees_file": ("employees.json", (DEMO / "employees.json").read_bytes(), "application/json"),
        "history_file": ("history.csv", (DEMO / "activity_history.csv").read_bytes(), "text/csv"),
    }
    with TestClient(main.app) as client:
        sign_in(client)
        response = client.post("/api/data/upload", files=files)
        assert response.status_code == 200
        assert response.json() == {"added_employees": 3, "added_history_records": 4}
        assert client.post("/api/data/upload", files=files).json()["added_history_records"] == 0
        trap = client.get("/api/employees/DEMO_TRAP").json()
        assert trap["gaps"][0]["skill_id"] == "SK_SYSTEM_DESIGN"
        assert trap["steps"][0]["skills"][0]["skill_id"] == "SK_SYSTEM_DESIGN"
        assert trap["readiness_percent"] == 88
        completed = client.post(f"/api/employees/DEMO_TRAP/complete/{trap['steps'][0]['event']['event_id']}")
        assert completed.status_code == 200
        assert completed.json()["profile"]["readiness_percent"] == 94
        history = client.get("/api/employees/DEMO_HISTORY").json()
        assert history["readiness_percent"] == 100
        assert history["steps"] == []
        unknown = client.get("/api/employees/DEMO_UNKNOWN").json()
        assert unknown["readiness_percent"] is None
        overview = client.get("/api/hr/overview").json()
        assert "DEMO_UNKNOWN" in overview["employees_unknown_data"]
        assert "DEMO_HISTORY" not in overview["employees_without_step"]
        invalid_profile = json.loads((DEMO / "employees.json").read_text())["employees"][0]
        invalid_profile["employee_id"] = "NOT_IMPORTED"
        invalid = client.post("/api/data/upload", files={
            "employees_file": ("employees.json", json.dumps([invalid_profile]), "application/json"),
            "history_file": (
                "history.csv",
                "employee_id,event_id,date,status\nNOT_IMPORTED,NO_EVENT,2026-09-01,completed",
                "text/csv",
            ),
        })
        assert invalid.status_code == 400
        assert client.get("/api/employees/NOT_IMPORTED").status_code == 404
