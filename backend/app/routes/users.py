from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import ROLES, AuditLog, Business, Notification, Report, Role, User, UserSetting
from ..services import notify
from ..utils import (ApiError, audit, audit_dict, current_user, json_body, paginate,
                     permission_required, validate)
from .auth import check_password_strength

bp = Blueprint("users", __name__)


def _assignable(actor):
    return ROLES if actor.role.name == "super_admin" else ["business_admin", "manager", "analyst", "user"]


def _scoped_user(uid, actor):
    u = db.session.get(User, uid)
    if not u or (actor.role.name != "super_admin" and u.business_id != actor.business_id):
        raise ApiError("User not found", 404)
    return u


def _check_role(actor, role_name, target=None):
    if role_name not in _assignable(actor):
        raise ApiError("You cannot assign that role", 403, {"role": "Not allowed"})
    if target and target.role.name == "super_admin" and actor.role.name != "super_admin":
        raise ApiError("You cannot modify a super admin", 403)


@bp.get("/users")
@permission_required("users.manage")
def list_users():
    actor = current_user()
    q = User.query.join(Role, Role.id == User.role_id)
    if actor.role.name != "super_admin":
        q = q.filter(User.business_id == actor.business_id)
    elif request.args.get("business_id", type=int):
        q = q.filter(User.business_id == request.args.get("business_id", type=int))
    if request.args.get("role") in ROLES:
        q = q.filter(Role.name == request.args["role"])
    if request.args.get("status") in ("active", "inactive"):
        q = q.filter(User.is_active.is_(request.args["status"] == "active"))
    page = paginate(q, lambda u: u.to_dict(), (User.full_name, User.email),
                    {"full_name": User.full_name, "email": User.email, "created_at": User.created_at,
                     "last_login": User.last_login, "role": Role.name}, "created_at")
    page["roles"] = _assignable(actor)
    return jsonify(page)


USER_SCHEMA = {"full_name": {"required": True, "min_len": 2, "max_len": 120}, "email": {"type": "email", "required": True},
               "role": {"required": True, "choices": ROLES}, "is_active": {"type": "bool"},
               "business_id": {"type": "int"}, "password": {"max_len": 128}}


@bp.post("/users")
@permission_required("users.manage")
def create_user():
    actor = current_user()
    d = validate(json_body(), {**USER_SCHEMA, "password": {"required": True, "max_len": 128}})
    _check_role(actor, d["role"])
    check_password_strength(d["password"])
    if User.query.filter_by(email=d["email"]).first():
        raise ApiError("An account with this email already exists", 409, {"email": "Already registered"})
    bid = actor.business_id
    if actor.role.name == "super_admin" and d.get("business_id"):
        if not db.session.get(Business, d["business_id"]):
            raise ApiError("Business not found", 404)
        bid = d["business_id"]
    u = User(email=d["email"], full_name=d["full_name"], business_id=bid, is_active=d.get("is_active", True) is not False,
             role=Role.query.filter_by(name=d["role"]).first())
    u.set_password(d["password"])
    u.settings = UserSetting()
    db.session.add(u)
    db.session.flush()
    audit("create", "user", u.id, f"{u.email} as {d['role']}")
    notify(bid, "New team member", f"{u.full_name} was added as {u.role.label}.", "activity", "info", audience="admin")
    db.session.commit()
    return jsonify(u.to_dict()), 201


@bp.put("/users/<int:uid>")
@permission_required("users.manage")
def update_user(uid):
    actor = current_user()
    u = _scoped_user(uid, actor)
    d = validate(json_body(), USER_SCHEMA, partial=True)
    if d.get("role"):
        _check_role(actor, d["role"], u)
        if u.id == actor.id and d["role"] != u.role.name:
            raise ApiError("You cannot change your own role", 400)
        u.role = Role.query.filter_by(name=d["role"]).first()
    elif u.role.name == "super_admin" and actor.role.name != "super_admin":
        raise ApiError("You cannot modify a super admin", 403)
    if d.get("email") and d["email"] != u.email:
        if User.query.filter(User.email == d["email"], User.id != u.id).first():
            raise ApiError("An account with this email already exists", 409, {"email": "Already registered"})
        u.email = d["email"]
    if d.get("full_name"):
        u.full_name = d["full_name"]
    if "is_active" in d and d["is_active"] is not None:
        if u.id == actor.id and not d["is_active"]:
            raise ApiError("You cannot deactivate your own account", 400)
        u.is_active = d["is_active"]
    if d.get("password"):
        check_password_strength(d["password"])
        u.set_password(d["password"])
    audit("update", "user", u.id, u.email)
    db.session.commit()
    return jsonify(u.to_dict())


@bp.patch("/users/<int:uid>/status")
@permission_required("users.manage")
def toggle_user(uid):
    actor = current_user()
    u = _scoped_user(uid, actor)
    if u.id == actor.id:
        raise ApiError("You cannot deactivate your own account", 400)
    _check_role(actor, u.role.name, u)
    u.is_active = not u.is_active
    audit("activate" if u.is_active else "deactivate", "user", u.id, u.email)
    db.session.commit()
    return jsonify(u.to_dict())


@bp.delete("/users/<int:uid>")
@permission_required("users.manage")
def delete_user(uid):
    actor = current_user()
    u = _scoped_user(uid, actor)
    if u.id == actor.id:
        raise ApiError("You cannot delete your own account", 400)
    _check_role(actor, u.role.name, u)
    audit("delete", "user", u.id, u.email)
    AuditLog.query.filter_by(user_id=u.id).update({"user_id": None})
    Report.query.filter_by(user_id=u.id).update({"user_id": None})
    Notification.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()
    return jsonify({"message": "User deleted"})


@bp.get("/users/<int:uid>/activity")
@permission_required("users.manage")
def user_activity(uid):
    u = _scoped_user(uid, current_user())
    q = AuditLog.query.filter_by(user_id=u.id)
    return jsonify(paginate(q, audit_dict, (AuditLog.action, AuditLog.details),
                            {"created_at": AuditLog.created_at}, "created_at"))
