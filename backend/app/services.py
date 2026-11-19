"""Business logic shared by routes and the seeder."""
import time
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func

from .extensions import db
from .models import Notification, Order, OrderItem, Product, Transaction, utcnow
from .utils import ApiError

PAYMENT_METHODS = ["card", "bank transfer", "paypal", "cash"]


def notify(business_id, title, message, type_="system", severity="info",
           user_id=None, audience="all", dedupe_key=None):
    if dedupe_key and Notification.query.filter_by(
            business_id=business_id, dedupe_key=dedupe_key, is_read=False).first():
        return None
    n = Notification(business_id=business_id, user_id=user_id, type=type_, severity=severity,
                     audience=audience, title=title, message=message, dedupe_key=dedupe_key)
    db.session.add(n)
    return n


def create_order(business_id, items, customer_id=None, status="completed", region=None,
                 order_date=None, created_by=None, is_sample=False, adjust_stock=True, method=None):
    """items: [{'product_id': int, 'quantity': int}]. Validates stock and snapshots price/cost."""
    if not items:
        raise ApiError("An order needs at least one item", 400)
    order = Order(business_id=business_id, customer_id=customer_id, status=status, region=region,
                  order_date=order_date or utcnow(), created_by=created_by, is_sample=is_sample,
                  order_number=uuid.uuid4().hex[:20])
    total = 0.0
    for it in items:
        product = db.session.get(Product, it["product_id"])
        if not product or product.business_id != business_id or not product.is_active:
            raise ApiError(f"Product {it['product_id']} is not available", 400)
        qty = int(it["quantity"])
        if qty < 1:
            raise ApiError("Quantity must be at least 1", 400)
        if adjust_stock and status in ("completed", "pending"):
            if product.stock < qty:
                raise ApiError(f"Only {product.stock} units of {product.name} in stock", 400)
            product.stock -= qty
        order.items.append(OrderItem(product_id=product.id, quantity=qty,
                                     unit_price=product.price, unit_cost=product.cost))
        total += product.price * qty
    order.total = round(total, 2)
    db.session.add(order)
    db.session.flush()
    order.order_number = f"ORD-{1000 + order.id}"
    if status == "completed":
        add_transaction(order, "sale", method)
    elif status == "refunded":
        add_transaction(order, "sale", method)
        add_transaction(order, "refund", method)
    return order


def add_transaction(order, kind, method=None, when=None):
    db.session.add(Transaction(
        business_id=order.business_id, order_id=order.id, type=kind, amount=order.total,
        method=method or "card", status="success", reference=order.order_number,
        created_at=when or order.order_date, is_sample=order.is_sample))


ALLOWED_TRANSITIONS = {"pending": ["completed", "cancelled"], "completed": ["refunded"]}


def change_order_status(order, new_status):
    if new_status not in ALLOWED_TRANSITIONS.get(order.status, []):
        raise ApiError(f"Cannot change an order from {order.status} to {new_status}", 400)
    if new_status in ("cancelled", "refunded"):
        for it in order.items:
            if it.product:
                it.product.stock += it.quantity
    if new_status == "completed":
        add_transaction(order, "sale", when=utcnow())
    if new_status == "refunded":
        add_transaction(order, "refund", when=utcnow())
    order.status = new_status


def delete_order(order):
    if order.status in ("completed", "pending"):
        for it in order.items:
            if it.product:
                it.product.stock += it.quantity
    Transaction.query.filter_by(order_id=order.id).delete()
    db.session.delete(order)


_last_refresh = {}


def refresh_alerts(business_id, force=False):
    """Create low-stock and revenue alerts from live data (throttled to once per 5 minutes)."""
    now = time.time()
    if not force and now - _last_refresh.get(business_id, 0) < 300:
        return
    _last_refresh[business_id] = now
    low = (Product.query.filter(Product.business_id == business_id, Product.is_active.is_(True),
                                Product.stock <= Product.reorder_level)
           .order_by(Product.stock.asc()).limit(12).all())
    for p in low:
        out = p.stock <= 0
        notify(business_id, f"{'Out of stock' if out else 'Low stock'}: {p.name}",
               f"{p.stock} units left (reorder level {p.reorder_level}).", "inventory",
               "danger" if out else "warning", dedupe_key=f"low_stock:{p.id}")

    def revenue(a, b):
        return float(db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
            Order.business_id == business_id, Order.status == "completed",
            Order.order_date >= a, Order.order_date < b).scalar() or 0)

    today = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
    cur, prev = revenue(today - timedelta(days=7), today), revenue(today - timedelta(days=14), today - timedelta(days=7))
    week = date.today().isocalendar()
    if prev > 0:
        change = (cur - prev) / prev * 100
        if change <= -15:
            notify(business_id, "Revenue dropped this week",
                   f"Last 7 days are {abs(change):.0f}% below the previous 7 days.", "revenue", "warning",
                   dedupe_key=f"rev_drop:{week[0]}-{week[1]}")
        elif change >= 20:
            notify(business_id, "Revenue is up this week",
                   f"Last 7 days are {change:.0f}% above the previous 7 days.", "revenue", "success",
                   dedupe_key=f"rev_up:{week[0]}-{week[1]}")
    db.session.commit()
