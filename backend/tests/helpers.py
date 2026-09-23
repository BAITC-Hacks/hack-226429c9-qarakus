def sign_in(client, username="hr", password="hr-demo"):
    csrf = client.get("/api/session").json()["csrf_token"]
    response = client.post("/login", data={"employee_id": username, "password": password, "csrf_token": csrf},
                           follow_redirects=False)
    assert response.status_code == 303
    client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
