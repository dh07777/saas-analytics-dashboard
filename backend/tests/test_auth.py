from .conftest import login


def test_login_success_returns_token_and_permissions(client):
    r = client.post("/api/auth/login", json={"email": "admin@insightflow.demo", "password": "Demo@1234"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["token"] and body["user"]["role"] == "business_admin"
    assert "users.manage" in body["user"]["permissions"]


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "admin@insightflow.demo", "password": "nope1234"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/analytics/dashboard").status_code == 401


def test_register_creates_business_admin(client):
    r = client.post("/api/auth/register", json={"full_name": "Rita Owner", "email": "rita@shop.test",
                                                "password": "Strong123", "company_name": "Rita Shop"})
    assert r.status_code == 201
    assert r.get_json()["user"]["role"] == "business_admin"


def test_register_rejects_weak_password_and_duplicates(client):
    payload = {"full_name": "Rita", "email": "rita@shop.test", "password": "short", "company_name": "Shop"}
    assert client.post("/api/auth/register", json=payload).status_code == 400
    payload["password"] = "Strong123"
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_logout_revokes_token(client, admin):
    assert client.get("/api/auth/me", headers=admin).status_code == 200
    assert client.post("/api/auth/logout", headers=admin).status_code == 200
    assert client.get("/api/auth/me", headers=admin).status_code == 401


def test_change_password(client, admin):
    r = client.post("/api/auth/change-password", headers=admin,
                    json={"current_password": "Demo@1234", "new_password": "NewPass123"})
    assert r.status_code == 200
    login(client, "admin", "NewPass123")


def test_reset_password_flow(client):
    r = client.post("/api/auth/forgot-password", json={"email": "user@insightflow.demo"})
    token = r.get_json()["dev_reset_token"]
    assert client.post("/api/auth/reset-password", json={"token": "bad", "password": "Reset1234"}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "Reset1234"}).status_code == 200
    login(client, "user", "Reset1234")


def test_forgot_password_does_not_reveal_unknown_email(client):
    r = client.post("/api/auth/forgot-password", json={"email": "ghost@nowhere.test"})
    assert r.status_code == 200 and "dev_reset_token" not in r.get_json()


def test_deactivated_user_cannot_login(client, admin):
    users = client.get("/api/users?q=Uma", headers=admin).get_json()["items"]
    uid = users[0]["id"]
    assert client.patch(f"/api/users/{uid}/status", headers=admin).status_code == 200
    r = client.post("/api/auth/login", json={"email": "user@insightflow.demo", "password": "Demo@1234"})
    assert r.status_code == 403
