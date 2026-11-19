from datetime import date, timedelta

Q = f"start={(date.today() - timedelta(days=400)).isoformat()}&end={date.today().isoformat()}"


def test_generate_report_and_history(client, analyst):
    r = client.post("/api/reports", headers=analyst, json={"type": "sales", "start": (date.today() - timedelta(days=400)).isoformat(), "end": date.today().isoformat()})
    assert r.status_code == 201 and r.get_json()["row_count"] > 0
    assert client.get("/api/reports", headers=analyst).get_json()["total"] == 1


def test_report_date_validation(client, analyst):
    r = client.post("/api/reports", headers=analyst, json={"type": "sales", "start": "2026-05-01", "end": "2026-01-01"})
    assert r.status_code == 400


def test_csv_export_every_type(client, analyst):
    for t in ("revenue", "sales", "customers", "products", "expenses"):
        r = client.get(f"/api/reports/export?type={t}&format=csv&{Q}", headers=analyst)
        assert r.status_code == 200 and r.mimetype == "text/csv", t
        assert len(r.data.splitlines()) >= 2, t


def test_pdf_export(client, analyst):
    r = client.get(f"/api/reports/export?type=revenue&format=pdf&{Q}", headers=analyst)
    assert r.status_code == 200 and r.data[:4] == b"%PDF"


def test_standard_user_cannot_export(client, standard):
    assert client.get(f"/api/reports/export?type=sales&format=csv&{Q}", headers=standard).status_code == 403
