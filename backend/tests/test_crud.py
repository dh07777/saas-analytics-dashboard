from app.models import Product


def test_expense_lifecycle(client, admin):
    r = client.post("/api/expenses", headers=admin, json={"category": "Travel", "amount": 250.5, "expense_date": "2026-03-01", "vendor": "Air Co"})
    assert r.status_code == 201
    eid = r.get_json()["id"]
    assert client.put(f"/api/expenses/{eid}", headers=admin, json={"amount": 300}).get_json()["amount"] == 300
    assert client.get("/api/expenses?q=Air", headers=admin).get_json()["total"] == 1
    assert client.delete(f"/api/expenses/{eid}", headers=admin).status_code == 200


def test_expense_validation(client, admin):
    r = client.post("/api/expenses", headers=admin, json={"category": "Travel", "amount": -5, "expense_date": "bad"})
    assert r.status_code == 400 and {"amount", "expense_date"} <= set(r.get_json()["fields"])


def test_pagination_search_sort(client, admin):
    p = client.get("/api/products?per_page=5&page=2&sort=price&order=asc", headers=admin).get_json()
    assert len(p["items"]) == 5 and p["page"] == 2 and p["pages"] > 1
    prices = [i["price"] for i in p["items"]]
    assert prices == sorted(prices)
    assert client.get("/api/products?q=zzzznomatch", headers=admin).get_json()["total"] == 0


def test_sql_injection_attempt_is_harmless(client, admin):
    r = client.get("/api/customers?q=' OR 1=1; DROP TABLE customers;--", headers=admin)
    assert r.status_code == 200 and r.get_json()["total"] == 0
    assert client.get("/api/customers", headers=admin).get_json()["total"] == 30


def test_order_creation_updates_stock_and_transactions(client, admin):
    prod = client.get("/api/products?active=1&sort=stock&order=desc", headers=admin).get_json()["items"][0]
    before = prod["stock"]
    r = client.post("/api/orders", headers=admin, json={"items": [{"product_id": prod["id"], "quantity": 2}], "region": "Europe"})
    assert r.status_code == 201
    order = r.get_json()
    assert order["total"] == round(prod["price"] * 2, 2)
    assert Product.query.get(prod["id"]).stock == before - 2
    assert client.patch(f"/api/orders/{order['id']}", headers=admin, json={"status": "refunded"}).status_code == 200
    assert Product.query.get(prod["id"]).stock == before


def test_order_rejects_oversell_and_bad_transition(client, admin):
    prod = client.get("/api/products?active=1", headers=admin).get_json()["items"][0]
    r = client.post("/api/orders", headers=admin, json={"items": [{"product_id": prod["id"], "quantity": 99999}]})
    assert r.status_code == 400
    order = client.get("/api/orders?status=cancelled", headers=admin).get_json()["items"]
    if order:
        assert client.patch(f"/api/orders/{order[0]['id']}", headers=admin, json={"status": "completed"}).status_code == 400


def test_user_management_and_self_protection(client, admin):
    r = client.post("/api/users", headers=admin, json={"full_name": "New Analyst", "email": "na@x.test", "password": "Passw0rd1", "role": "analyst"})
    assert r.status_code == 201
    me = client.get("/api/auth/me", headers=admin).get_json()["user"]
    assert client.delete(f"/api/users/{me['id']}", headers=admin).status_code == 400
    assert client.delete(f"/api/users/{r.get_json()['id']}", headers=admin).status_code == 200


def test_notifications_lifecycle(client, admin):
    data = client.get("/api/notifications", headers=admin).get_json()
    assert data["total"] >= 1
    nid = data["items"][0]["id"]
    assert client.patch(f"/api/notifications/{nid}/read", headers=admin).get_json()["is_read"] is True
    assert client.post("/api/notifications/read-all", headers=admin).status_code == 200
    assert client.get("/api/notifications/unread-count", headers=admin).get_json()["unread"] == 0


def test_settings_and_sample_purge(client, admin):
    assert client.put("/api/settings/business", headers=admin, json={"currency": "EUR"}).status_code == 200
    assert client.put("/api/settings/business", headers=admin, json={"currency": "XXX"}).status_code == 400
    assert client.put("/api/settings/user", headers=admin, json={"theme": "dark"}).get_json()["user"]["theme"] == "dark"
    assert client.delete("/api/settings/sample-data", headers=admin).status_code == 200
    assert client.get("/api/orders", headers=admin).get_json()["total"] == 0
    assert client.get("/api/auth/me", headers=admin).get_json()["user"]["business"]["is_sample_data"] is False


def test_audit_log_records_actions(client, admin):
    client.post("/api/expenses", headers=admin, json={"category": "Other", "amount": 5, "expense_date": "2026-02-02"})
    logs = client.get("/api/audit-logs?action=create", headers=admin).get_json()
    assert logs["total"] >= 1


def test_transactions_list_and_totals(client, admin):
    r = client.get("/api/transactions?per_page=5", headers=admin).get_json()
    assert r["total"] > 0 and len(r["items"]) == 5
    assert r["totals"]["net"] == round(r["totals"]["sales"] - r["totals"]["refunds"], 2)
    only = client.get("/api/transactions?type=refund", headers=admin).get_json()
    assert all(t["type"] == "refund" for t in only["items"])


def test_order_detail_has_items(client, admin):
    oid = client.get("/api/orders", headers=admin).get_json()["items"][0]["id"]
    d = client.get(f"/api/orders/{oid}", headers=admin).get_json()
    assert d["items"] and d["items"][0]["product"]


def test_new_business_product_analytics_without_sales(client):
    r = client.post("/api/auth/register", json={"full_name": "P Owner", "email": "p@biz.test", "password": "Strong123", "company_name": "P Co"})
    h = {"Authorization": f"Bearer {r.get_json()['token']}"}
    assert client.post("/api/products", headers=h, json={"name": "Widget", "sku": "W-1", "price": 5, "stock": 3}).status_code == 201
    a = client.get("/api/analytics/products", headers=h)
    assert a.status_code == 200 and a.get_json()["kpis"]["active_products"] == 1
