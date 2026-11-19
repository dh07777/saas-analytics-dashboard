"""Backend self-check. Run from the backend folder:  python smoke_test.py
Uses a temporary in-memory database, so it never touches your real data."""
import sys

from app import create_app
from app.extensions import db
from app.seed import seed_demo
from config import TestConfig

app = create_app(TestConfig)
failures = 0


def check(name, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra and not ok else ""))
    failures += 0 if ok else 1


with app.app_context():
    db.create_all()
    seed_demo(n_customers=30, n_orders=80, months=6)
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": "admin@insightflow.demo", "password": "Demo@1234"})
    check("login as business admin", r.status_code == 200, r.get_data(as_text=True)[:300])
    if r.status_code != 200:
        sys.exit(1)
    h = {"Authorization": f"Bearer {r.get_json()['token']}"}
    for path in ["/api/auth/me", "/api/analytics/dashboard", "/api/analytics/revenue", "/api/analytics/customers",
                 "/api/analytics/sales", "/api/analytics/products", "/api/analytics/expenses", "/api/customers",
                 "/api/products", "/api/orders", "/api/expenses", "/api/transactions", "/api/categories",
                 "/api/users", "/api/notifications", "/api/settings", "/api/audit-logs", "/api/reports"]:
        r = c.get(path, headers=h)
        check(f"GET {path}", r.status_code == 200, f"{r.status_code} {r.get_data(as_text=True)[:200]}")
    r = c.get("/api/reports/export?type=sales&format=pdf&start=2020-01-01&end=2030-01-01", headers=h)
    check("PDF export", r.status_code == 200 and r.data[:4] == b"%PDF", str(r.status_code))
    r = c.get("/api/reports/export?type=revenue&format=csv&start=2020-01-01&end=2030-01-01", headers=h)
    check("CSV export", r.status_code == 200 and len(r.data.splitlines()) > 1, str(r.status_code))
    sup = c.post("/api/auth/login", json={"email": "super@insightflow.demo", "password": "Demo@1234"}).get_json()
    hs = {"Authorization": f"Bearer {sup['token']}"}
    for path in ["/api/admin/overview", "/api/admin/businesses", "/api/admin/db-stats", "/api/admin/activity",
                 "/api/admin/config", "/api/admin/roles"]:
        r = c.get(path, headers=hs)
        check(f"GET {path} (super admin)", r.status_code == 200, f"{r.status_code} {r.get_data(as_text=True)[:200]}")
print("\nAll checks passed." if not failures else f"\n{failures} check(s) failed. Copy the FAIL lines and send them to get a fix.")
sys.exit(1 if failures else 0)
