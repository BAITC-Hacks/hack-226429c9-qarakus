from fastapi.testclient import TestClient

from app import main
from tests.helpers import sign_in


def test_employee_cannot_read_or_change_other_profiles_or_hr():
    with TestClient(main.app) as client:
        assert client.get("/api/employees/E0028").status_code == 401
        sign_in(client, "E0028", "employee-demo")
        assert client.get("/api/employees/E0028").status_code == 200
        for path in ["/api/employees/E0001", "/employee/E0001", "/hr", "/api/hr/overview"]:
            assert client.get(path).status_code == 403
        for path in ["/api/employees/E0001/complete/EV_005", "/api/employees/E0001/explain/EV_005", "/api/data/upload"]:
            assert client.post(path).status_code == 403


def test_post_requires_csrf_and_tampered_session_is_rejected():
    with TestClient(main.app) as client:
        sign_in(client)
        del client.headers["X-CSRF-Token"]
        assert client.post("/api/data/upload").status_code == 403
        assert client.post("/logout").status_code == 403
        client.cookies.clear()
        client.cookies.set("session", "forged-role-hr")
        assert client.get("/api/hr/overview").status_code == 401


def test_demo_credentials_disabled_outside_demo(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("HR_PASSWORD", "test-configured-password")
    with TestClient(main.app) as client:
        csrf = client.get("/api/session").json()["csrf_token"]
        response = client.post("/login", data={"employee_id": "hr", "password": "hr-demo", "csrf_token": csrf})
        assert response.status_code == 401
        sign_in(client, "hr", "test-configured-password")
        assert client.get("/api/hr/overview").status_code == 200
