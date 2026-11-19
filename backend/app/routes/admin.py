"""System administration (super admin only)."""
import os
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, text

from ..extensions import db
from ..models import AuditLog, Business, Permission, Role, User, utcnow
from ..utils import (ApiError, audit, audit_dict, get_config, json_body, paginate,
                     permission_required, set_config, validate)

bp = Blueprint("admin", __name__)
ADMIN = "admin.access"


def _biz(b):
    d = b.to_dict()
    d["users"] = User.query.filter_by(business_id=b.id).count()
    return d


@bp.get("/overview")
@permission_required(ADMIN)
def overview():
    day = utcnow() - timedelta(days=1)
    return jsonify({
        "businesses": Business.query.count(), "users": User.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "logins_24h": AuditLog.query.filter(AuditLog.action == "login", AuditLog.created_at >= day).count(),
        "failed_logins_24h": AuditLog.query.filter(AuditLog.action == "login_failed", AuditLog.created_at >= day).count(),
        "audit_events": AuditLog.query.count(), "environment": current_app.config["APP_ENV"]})


@bp.get("/businesses")
@permission_required(ADMIN)
def businesses():
    return jsonify(paginate(Business.query, _biz, (Business.name, Business.email),
                            {"name": Business.name, "created_at": Business.created_at}, "created_at"))


@bp.post("/businesses")
@permission_required(ADMIN)
def create_business():
    d = validate(json_body(), {"name": {"required": True, "min_len": 2, "max_len": 150}, "industry": {"max_len": 100},
                               "email": {"type": "email"}, "currency": {"max_len": 3}})
    b = Business(**d)
    db.session.add(b)
    db.session.flush()
    audit("create", "business", b.id, b.name)
    db.session.commit()
    return jsonify(_biz(b)), 201


@bp.put("/businesses/<int:bid>")
@permission_required(ADMIN)
def update_business(bid):
    b = db.session.get(Business, bid)
    if not b:
        raise ApiError("Business not found", 404)
    d = validate(json_body(), {"name": {"min_len": 2, "max_len": 150}, "industry": {"max_len": 100},
                               "email": {"type": "email"}, "is_active": {"type": "bool"}}, partial=True)
    for k, v in d.items():
        if v is not None:
            setattr(b, k, v)
    audit("update", "business", b.id, b.name)
    db.session.commit()
    return jsonify(_biz(b))


@bp.get("/db-stats")
@permission_required(ADMIN)
def db_stats():
    tables = []
    for name in sorted(db.metadata.tables):
        count = db.session.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
        tables.append({"table": name, "rows": int(count)})
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    size = None
    if uri.startswith("sqlite:///") and ":memory:" not in uri:
        path = uri.replace("sqlite:///", "", 1)
        size = os.path.getsize(path) if os.path.exists(path) else None
    return jsonify({"engine": db.engine.dialect.name, "size_bytes": size, "tables": tables,
                    "total_rows": sum(t["rows"] for t in tables)})


@bp.get("/activity")
@permission_required(ADMIN)
def activity():
    since = utcnow() - timedelta(days=14)
    rows = db.session.query(func.date(AuditLog.created_at), AuditLog.action, func.count(AuditLog.id)).filter(
        AuditLog.created_at >= since, AuditLog.action.in_(["login", "login_failed"])
    ).group_by(func.date(AuditLog.created_at), AuditLog.action).all()
    days = {}
    for d, action, n in rows:
        days.setdefault(str(d), {"date": str(d), "login": 0, "login_failed": 0})[action] = n
    recent = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(15).all()
    return jsonify({"logins": sorted(days.values(), key=lambda x: x["date"]), "recent": [audit_dict(a) for a in recent]})


@bp.get("/config")
@permission_required(ADMIN)
def config():
    c = current_app.config
    return jsonify({
        "editable": {"allow_registration": get_config("allow_registration", "true") == "true",
                     "announcement": get_config("announcement", "")},
        "readonly": {"environment": c["APP_ENV"], "token_lifetime_minutes": int(c["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds() // 60),
                     "rate_limit_per_minute": c["RATE_LIMIT_PER_MINUTE"], "login_rate_limit_per_minute": c["LOGIN_RATE_LIMIT"],
                     "cors_origins": c["CORS_ORIGINS"], "database_engine": db.engine.dialect.name}})


@bp.put("/config")
@permission_required(ADMIN)
def update_config():
    d = validate(json_body(), {"allow_registration": {"type": "bool"}, "announcement": {"max_len": 300}}, partial=True)
    if "allow_registration" in d and d["allow_registration"] is not None:
        set_config("allow_registration", "true" if d["allow_registration"] else "false")
    if "announcement" in d:
        set_config("announcement", d["announcement"] or "")
    audit("update", "config", None, "Application configuration")
    db.session.commit()
    return config()


@bp.get("/roles")
@permission_required(ADMIN)
def roles():
    perms = Permission.query.order_by(Permission.code).all()
    return jsonify({
        "permissions": [{"code": p.code, "description": p.description} for p in perms],
        "roles": [{"id": r.id, "name": r.name, "label": r.label, "description": r.description,
                   "locked": r.name == "super_admin", "permissions": sorted(p.code for p in r.permissions),
                   "users": User.query.filter_by(role_id=r.id).count()}
                  for r in Role.query.order_by(Role.id).all()]})


@bp.put("/roles/<int:rid>/permissions")
@permission_required(ADMIN)
def set_role_permissions(rid):
    role = db.session.get(Role, rid)
    if not role:
        raise ApiError("Role not found", 404)
    if role.name == "super_admin":
        raise ApiError("The Super Admin role cannot be changed", 400)
    body = json_body()
    codes = body.get("permissions")
    if not isinstance(codes, list):
        raise ApiError("permissions must be a list", 400)
    found = Permission.query.filter(Permission.code.in_(codes)).all()
    if len(found) != len(set(codes)):
        raise ApiError("Unknown permission in list", 400)
    if "admin.access" in codes:
        raise ApiError("admin.access is reserved for Super Admin", 400)
    if "dashboard.view" not in codes:
        raise ApiError("Every role must keep dashboard.view", 400)
    role.permissions = found
    audit("update", "role", role.id, f"{role.name}: {', '.join(sorted(codes))}")
    db.session.commit()
    return roles()
