from fastapi.testclient import TestClient

from app import engine, main
from app.store import DataStore
from tests.helpers import sign_in


def test_pages_work_offline_and_ignore_malformed_change_query(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(main.app) as client:
        sign_in(client)
        for path in ["/", "/employee/E0028?changed=broken", "/employee/E0028?lang=en", "/hr"]:
            response = client.get(path)
            assert response.status_code == 200
            assert "cdn.tailwindcss.com" not in response.text
        assert client.get("/static/app.js").status_code == 200


def test_unknown_employee_and_invalid_completion_have_friendly_error(monkeypatch):
    monkeypatch.setattr(main, "store", DataStore())
    with TestClient(main.app) as client:
        sign_in(client)
        response = client.post("/employee/E0028/complete/EV_001")
        assert response.status_code == 400
        assert "Не удалось выполнить действие" in response.text
        assert client.get("/api/employees/UNKNOWN").status_code == 404


def test_ai_endpoint_without_key_returns_facts_and_respects_selected_language(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(main, "store", DataStore())
    event_id = engine.recommend(main.store, "E0028")["steps"][0]["event"]["event_id"]
    with TestClient(main.app) as client:
        sign_in(client)
        result = client.post(f"/api/employees/E0028/explain/{event_id}?lang=en").json()
        assert result["source"] == "template"
        assert "required" in result["text"]
        assert result["tool_calls"] == []
        assert client.post("/api/employees/E0028/explain/EV_001").status_code == 409


def test_completion_keeps_explicit_language(monkeypatch):
    monkeypatch.setattr(main, "store", DataStore())
    event_id = engine.recommend(main.store, "E0028")["steps"][0]["event"]["event_id"]
    with TestClient(main.app) as client:
        sign_in(client)
        response = client.post(f"/employee/E0028/complete/{event_id}?lang=en", follow_redirects=False)
        assert response.status_code == 303
        assert "lang=en" in response.headers["location"]
        assert "changed=" in response.headers["location"]
