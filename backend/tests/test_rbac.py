def test_standard_user_limited_to_dashboard(client, standard):
    assert client.get("/api/analytics/dashboard", headers=standard).status_code == 200
    assert client.get("/api/analytics/revenue", headers=standard).status_code == 403
    assert client.get("/api/customers", headers=standard).status_code == 403
    assert client.get("/api/users", headers=standard).status_code == 403


def test_analyst_reads_but_cannot_write(client, analyst):
    assert client.get("/api/customers", headers=analyst).status_code == 200
    r = client.post("/api/expenses", headers=analyst, json={"category": "Rent", "amount": 10, "expense_date": "2026-01-01"})
    assert r.status_code == 403


def test_business_admin_cannot_use_system_admin(client, admin):
    assert client.get("/api/admin/overview", headers=admin).status_code == 403


def test_super_admin_can_use_system_admin(client):
    from .conftest import login
    h = login(client, "super")
    assert client.get("/api/admin/overview", headers=h).status_code == 200
    stats = client.get("/api/admin/db-stats", headers=h).get_json()
    assert any(t["table"] == "orders" and t["rows"] > 0 for t in stats["tables"])


def test_business_admin_cannot_create_super_admin(client, admin):
    r = client.post("/api/users", headers=admin, json={"full_name": "Evil Root", "email": "evil@x.test",
                                                       "password": "Passw0rd1", "role": "super_admin"})
    assert r.status_code == 403


def test_role_permissions_are_editable_and_enforced(client):
    from .conftest import login
    sup = login(client, "super")
    roles = client.get("/api/admin/roles", headers=sup).get_json()["roles"]
    analyst = next(r for r in roles if r["name"] == "analyst")
    new = [p for p in analyst["permissions"] if p != "reports.generate"]
    assert client.put(f"/api/admin/roles/{analyst['id']}/permissions", headers=sup, json={"permissions": new}).status_code == 200
    h = login(client, "analyst")
    assert client.get("/api/reports", headers=h).status_code == 403
    sa = next(r for r in roles if r["name"] == "super_admin")
    assert client.put(f"/api/admin/roles/{sa['id']}/permissions", headers=sup, json={"permissions": []}).status_code == 400


def test_rate_limit_blocks_login_spam(app):
    app.config["LOGIN_RATE_LIMIT"] = 3
    c = app.test_client()
    codes = [c.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}).status_code for _ in range(5)]
    assert 429 in codes
