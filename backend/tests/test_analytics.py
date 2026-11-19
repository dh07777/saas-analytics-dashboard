from datetime import date, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import Customer, Expense, Order


def _range(days=3650):
    return f"start={(date.today() - timedelta(days=days)).isoformat()}&end={date.today().isoformat()}"


def test_dashboard_numbers_match_database(client, admin):
    body = client.get(f"/api/analytics/dashboard?{_range()}", headers=admin).get_json()
    revenue = db.session.query(func.sum(Order.total)).filter(Order.status == "completed").scalar()
    orders = Order.query.filter_by(status="completed").count()
    expenses = db.session.query(func.sum(Expense.amount)).scalar()
    k = body["kpis"]
    assert abs(k["revenue"] - round(revenue, 2)) < 0.05
    assert k["orders"] == orders
    assert abs(k["expenses"] - round(expenses, 2)) < 0.05
    assert k["total_customers"] == Customer.query.count()
    assert abs(k["profit"] - (k["revenue"] - k["cogs"] - k["expenses"])) < 0.05


def test_revenue_series_sums_to_total(client, admin):
    body = client.get(f"/api/analytics/revenue?granularity=monthly&{_range()}", headers=admin).get_json()
    assert abs(sum(r["revenue"] for r in body["series"]) - body["summary"]["revenue"]) < 0.5
    assert body["forecast"]["meta"]["months_used"] >= 3
    assert len(body["forecast"]["forecast"]) == 3


def test_invalid_granularity_and_dates(client, admin):
    assert client.get("/api/analytics/revenue?granularity=hourly", headers=admin).status_code == 400
    assert client.get("/api/analytics/revenue?start=2026-05-01&end=2026-01-01", headers=admin).status_code == 400
    assert client.get("/api/analytics/revenue?start=banana", headers=admin).status_code == 400


def test_customer_sales_product_endpoints(client, admin):
    for path in ("customers", "sales", "products", "expenses"):
        r = client.get(f"/api/analytics/{path}?{_range()}", headers=admin)
        assert r.status_code == 200, path
        assert "NaN" not in r.get_data(as_text=True)
    sales = client.get(f"/api/analytics/sales?{_range()}", headers=admin).get_json()
    assert abs(sum(c["revenue"] for c in sales["by_category"]) - sales["totals"]["sales"]) < 0.5


def test_new_business_has_empty_but_valid_analytics(client):
    r = client.post("/api/auth/register", json={"full_name": "New Owner", "email": "new@biz.test",
                                                "password": "Strong123", "company_name": "Fresh Co"})
    h = {"Authorization": f"Bearer {r.get_json()['token']}"}
    d = client.get("/api/analytics/dashboard", headers=h).get_json()
    assert d["kpis"]["revenue"] == 0 and d["trend"] == []
    assert client.get("/api/analytics/revenue", headers=h).status_code == 200
    assert client.get("/api/analytics/customers", headers=h).status_code == 200
    assert client.get("/api/analytics/products", headers=h).status_code == 200


def test_tenant_isolation(client, admin):
    r = client.post("/api/auth/register", json={"full_name": "Other Owner", "email": "other@biz.test",
                                                "password": "Strong123", "company_name": "Other Co"})
    other = {"Authorization": f"Bearer {r.get_json()['token']}"}
    assert client.get("/api/customers", headers=other).get_json()["total"] == 0
    cid = client.get("/api/customers", headers=admin).get_json()["items"][0]["id"]
    assert client.put(f"/api/customers/{cid}", headers=other, json={"name": "Hacked"}).status_code == 404
