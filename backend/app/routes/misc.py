"""Notifications, settings, public config and audit logs."""
from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import (AuditLog, Category, Customer, Expense, Notification, Order, OrderItem, Product,
                      Transaction, UserSetting)
from ..services import refresh_alerts
from ..utils import (ApiError, audit, audit_dict, auth_required, biz_id, current_user, get_config,
                     json_body, paginate, permission_required, validate)

bp = Blueprint("misc", __name__)
TYPE_PREF = {"revenue": "notify_revenue", "inventory": "notify_inventory", "activity": "notify_activity"}


# ---------- notifications ----------
def _visible(user):
    q = Notification.query.filter(Notification.business_id == user.business_id,
                                  or_(Notification.user_id.is_(None), Notification.user_id == user.id))
    if "users.manage" not in user.permission_codes():
        q = q.filter(Notification.audience == "all")
    s = user.settings
    for ntype, attr in TYPE_PREF.items():
        if s is not None and getattr(s, attr) is False:
            q = q.filter(Notification.type != ntype)
    return q


def _note(n):
    return {"id": n.id, "type": n.type, "severity": n.severity, "title": n.title, "message": n.message,
            "is_read": n.is_read, "created_at": n.created_at.isoformat()}


def _own_note(nid):
    n = _visible(current_user()).filter(Notification.id == nid).first()
    if not n:
        raise ApiError("Notification not found", 404)
    return n


@bp.get("/notifications")
@auth_required
def list_notifications():
    u = current_user()
    refresh_alerts(u.business_id)
    q = _visible(u)
    if request.args.get("unread"):
        q = q.filter(Notification.is_read.is_(False))
    if request.args.get("type"):
        q = q.filter(Notification.type == request.args["type"])
    page = paginate(q, _note, (Notification.title, Notification.message), {"created_at": Notification.created_at}, "created_at")
    page["unread"] = _visible(u).filter(Notification.is_read.is_(False)).count()
    return jsonify(page)


@bp.get("/notifications/unread-count")
@auth_required
def unread_count():
    u = current_user()
    refresh_alerts(u.business_id)
    return jsonify({"unread": _visible(u).filter(Notification.is_read.is_(False)).count()})


@bp.patch("/notifications/<int:nid>/read")
@auth_required
def mark_read(nid):
    n = _own_note(nid)
    n.is_read = True
    db.session.commit()
    return jsonify(_note(n))


@bp.post("/notifications/read-all")
@auth_required
def read_all():
    for n in _visible(current_user()).filter(Notification.is_read.is_(False)).all():
        n.is_read = True
    db.session.commit()
    return jsonify({"message": "All notifications marked as read"})


@bp.delete("/notifications/<int:nid>")
@auth_required
def delete_note(nid):
    db.session.delete(_own_note(nid))
    db.session.commit()
    return jsonify({"message": "Notification deleted"})


# ---------- settings ----------
@bp.get("/settings")
@auth_required
def get_settings():
    u = current_user()
    return jsonify({"business": u.business.to_dict() if u.business else None,
                    "user": (u.settings or UserSetting()).to_dict()})


@bp.put("/settings/user")
@auth_required
def update_user_settings():
    u = current_user()
    d = validate(json_body(), {"theme": {"choices": ["light", "dark"]},
                               "date_format": {"choices": ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"]},
                               "notify_revenue": {"type": "bool"}, "notify_inventory": {"type": "bool"},
                               "notify_activity": {"type": "bool"}}, partial=True)
    s = u.settings or UserSetting(user_id=u.id)
    for k, v in d.items():
        if v is not None:
            setattr(s, k, v)
    widgets = (request.get_json(silent=True) or {}).get("dashboard_widgets")
    if isinstance(widgets, list):
        allowed = {"trend", "categories", "topProducts", "transactions", "activity"}
        s.dashboard_widgets = ",".join(w for w in widgets if w in allowed)
    db.session.add(s)
    db.session.commit()
    return jsonify({"user": s.to_dict()})


@bp.put("/settings/business")
@permission_required("settings.edit")
def update_business_settings():
    u = current_user()
    if not u.business:
        raise ApiError("No business assigned", 400)
    d = validate(json_body(), {"name": {"min_len": 2, "max_len": 150}, "industry": {"max_len": 100},
                               "email": {"type": "email"}, "phone": {"max_len": 40}, "address": {"max_len": 250},
                               "currency": {"choices": ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "AED", "SGD", "BRL"]}},
                 partial=True)
    for k, v in d.items():
        if k == "name" and not v:
            continue
        setattr(u.business, k, v)
    audit("update", "business", u.business_id, "Company settings")
    db.session.commit()
    return jsonify({"business": u.business.to_dict()})


@bp.delete("/settings/sample-data")
@permission_required("settings.edit")
def purge_sample_data():
    """Delete every row flagged is_sample for this business. Live rows are never touched."""
    biz = biz_id()
    sample_orders = [o.id for o in Order.query.filter_by(business_id=biz, is_sample=True).all()]
    if sample_orders:
        OrderItem.query.filter(OrderItem.order_id.in_(sample_orders)).delete(synchronize_session=False)
        Transaction.query.filter(Transaction.order_id.in_(sample_orders)).delete(synchronize_session=False)
        Order.query.filter(Order.id.in_(sample_orders)).delete(synchronize_session=False)
    Transaction.query.filter_by(business_id=biz, is_sample=True).delete()
    Expense.query.filter_by(business_id=biz, is_sample=True).delete()
    for model in (Product, Customer):
        for row in model.query.filter_by(business_id=biz, is_sample=True).all():
            used = (OrderItem.query.filter_by(product_id=row.id).count() if model is Product
                    else Order.query.filter_by(customer_id=row.id).count())
            if not used:
                db.session.delete(row)
    db.session.flush()
    for c in Category.query.filter_by(business_id=biz).all():
        if not Product.query.filter_by(category_id=c.id).count():
            db.session.delete(c)
    Notification.query.filter_by(business_id=biz).delete()
    user = current_user()
    if user.business:
        user.business.is_sample_data = False
    audit("purge_sample_data", "business", biz, "Removed sample data")
    db.session.commit()
    return jsonify({"message": "Sample data removed"})


# ---------- public config ----------
@bp.get("/config/public")
def public_config():
    return jsonify({"allow_registration": get_config("allow_registration", "true") == "true",
                    "announcement": get_config("announcement", "")})


# ---------- audit logs ----------
@bp.get("/audit-logs")
@permission_required("audit.view")
def audit_logs():
    u = current_user()
    q = AuditLog.query
    if u.role.name != "super_admin":
        q = q.filter(AuditLog.business_id == u.business_id)
    elif request.args.get("business_id", type=int):
        q = q.filter(AuditLog.business_id == request.args.get("business_id", type=int))
    if request.args.get("action"):
        q = q.filter(AuditLog.action == request.args["action"])
    return jsonify(paginate(q, audit_dict, (AuditLog.action, AuditLog.details, AuditLog.entity),
                            {"created_at": AuditLog.created_at, "action": AuditLog.action}, "created_at"))
