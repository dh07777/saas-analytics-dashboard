import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Business, Customer, Order, OrderItem, Product, Role, User


def test_seed_volume_and_flags(app):
    assert Customer.query.count() == 30
    assert Product.query.count() >= 50
    assert Order.query.count() >= 50
    assert Business.query.first().is_sample_data is True
    assert Order.query.filter_by(is_sample=False).count() == 0


def test_order_relationships_are_consistent(app):
    o = Order.query.filter_by(status="completed").first()
    assert o.items and abs(sum(i.quantity * i.unit_price for i in o.items) - o.total) < 0.01
    assert o.items[0].product.business_id == o.business_id


def test_roles_have_permissions(app):
    assert {p.code for p in Role.query.filter_by(name="user").first().permissions} == {"dashboard.view"}
    assert len(Role.query.filter_by(name="super_admin").first().permissions) >= 9


def test_unique_email_and_sku(app):
    biz = Business.query.first()
    u = User(email="admin@insightflow.demo", full_name="Dup", password_hash="x", role_id=1, business_id=biz.id)
    db.session.add(u)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    p = Product.query.first()
    db.session.add(Product(business_id=p.business_id, sku=p.sku, name="Dup", price=1))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_password_is_hashed(app):
    u = User.query.filter_by(email="admin@insightflow.demo").first()
    assert u.password_hash != "Demo@1234" and u.check_password("Demo@1234")
