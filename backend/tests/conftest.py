import pytest

from app import create_app
from app.extensions import db
from app.seed import seed_demo
from config import TestConfig


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_demo(n_customers=30, n_orders=80, months=6)
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, who="admin", password="Demo@1234"):
    r = client.post("/api/auth/login", json={"email": f"{who}@insightflow.demo", "password": password})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "admin")


@pytest.fixture()
def analyst(client):
    return login(client, "analyst")


@pytest.fixture()
def standard(client):
    return login(client, "user")
