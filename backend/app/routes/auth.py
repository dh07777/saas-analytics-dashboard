import hashlib
import logging
import re
import secrets
from datetime import timedelta

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import create_access_token, get_jwt, verify_jwt_in_request

from ..extensions import db
from ..models import Business, Role, TokenBlocklist, User, UserSetting, utcnow
from ..utils import (ApiError, audit, auth_required, current_user, get_config, json_body,
                     rate_limit, validate)

bp = Blueprint("auth", __name__)
log = logging.getLogger("insightflow")


def check_password_strength(pw):
    if len(pw) < 8 or len(pw) > 128 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise ApiError("Password must be 8+ characters and include a letter and a number", 400,
                       {"password": "Use 8+ characters with at least one letter and one number"})


def _session(user, status=200):
    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict(True)}), status


@bp.post("/register")
@rate_limit("LOGIN_RATE_LIMIT")
def register():
    if get_config("allow_registration", "true") != "true":
        raise ApiError("New registrations are currently disabled", 403)
    d = validate(json_body(), {
        "full_name": {"required": True, "min_len": 2, "max_len": 120},
        "email": {"type": "email", "required": True},
        "password": {"required": True, "max_len": 128},
        "company_name": {"required": True, "min_len": 2, "max_len": 150}})
    check_password_strength(d["password"])
    if User.query.filter_by(email=d["email"]).first():
        raise ApiError("An account with this email already exists", 409, {"email": "Already registered"})
    biz = Business(name=d["company_name"], email=d["email"])
    db.session.add(biz)
    db.session.flush()
    user = User(email=d["email"], full_name=d["full_name"], business_id=biz.id,
                role=Role.query.filter_by(name="business_admin").first())
    user.set_password(d["password"])
    user.settings = UserSetting()
    db.session.add(user)
    db.session.flush()
    audit("register", "user", user.id, f"New business: {biz.name}", user=user, business_id=biz.id)
    db.session.commit()
    return _session(user, 201)


@bp.post("/login")
@rate_limit("LOGIN_RATE_LIMIT")
def login():
    d = validate(json_body(), {"email": {"type": "email", "required": True},
                               "password": {"required": True, "max_len": 128}})
    user = User.query.filter_by(email=d["email"]).first()
    if not user or not user.check_password(d["password"]):
        audit("login_failed", "user", user.id if user else None, d["email"], user=user)
        db.session.commit()
        raise ApiError("Incorrect email or password", 401, code="bad_credentials")
    if not user.is_active:
        raise ApiError("This account has been deactivated. Contact your administrator.", 403, code="inactive")
    if user.business and not user.business.is_active and user.role.name != "super_admin":
        raise ApiError("This business account is suspended.", 403, code="suspended")
    user.last_login = utcnow()
    audit("login", "user", user.id, user=user)
    db.session.commit()
    return _session(user)


@bp.post("/logout")
def logout():
    verify_jwt_in_request()
    jwt_data = get_jwt()
    db.session.add(TokenBlocklist(jti=jwt_data["jti"]))
    uid = int(jwt_data["sub"])
    user = db.session.get(User, uid)
    if user:
        audit("logout", "user", user.id, user=user)
    db.session.commit()
    return jsonify({"message": "Signed out"})


@bp.get("/me")
@auth_required
def me():
    return jsonify({"user": current_user().to_dict(True)})


@bp.put("/profile")
@auth_required
def update_profile():
    user = current_user()
    d = validate(json_body(), {"full_name": {"min_len": 2, "max_len": 120}, "email": {"type": "email"}}, partial=True)
    if d.get("email") and d["email"] != user.email:
        if User.query.filter(User.email == d["email"], User.id != user.id).first():
            raise ApiError("That email is already in use", 409, {"email": "Already in use"})
        user.email = d["email"]
    if d.get("full_name"):
        user.full_name = d["full_name"]
    audit("profile_update", "user", user.id)
    db.session.commit()
    return jsonify({"user": user.to_dict(True)})


@bp.post("/change-password")
@auth_required
def change_password():
    user = current_user()
    d = validate(json_body(), {"current_password": {"required": True, "max_len": 128},
                               "new_password": {"required": True, "max_len": 128}})
    if not user.check_password(d["current_password"]):
        raise ApiError("Current password is incorrect", 400, {"current_password": "Incorrect password"})
    check_password_strength(d["new_password"])
    user.set_password(d["new_password"])
    audit("password_change", "user", user.id)
    db.session.commit()
    return jsonify({"message": "Password updated"})


@bp.post("/forgot-password")
@rate_limit("LOGIN_RATE_LIMIT")
def forgot_password():
    d = validate(json_body(), {"email": {"type": "email", "required": True}})
    user = User.query.filter_by(email=d["email"]).first()
    body = {"message": "If that email is registered, a reset link has been sent."}
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        user.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
        user.reset_expires = utcnow() + timedelta(minutes=current_app.config["RESET_TOKEN_MINUTES"])
        audit("password_reset_requested", "user", user.id, user=user)
        db.session.commit()
        # No email server is configured. The link goes to the server log; in development it is also returned
        # so the flow can be tested. Replace this block with an email provider before real production use.
        log.info("Password reset link for %s: /reset-password?token=%s", user.email, token)
        if current_app.config["APP_ENV"] != "production":
            body["dev_reset_token"] = token
    return jsonify(body)


@bp.post("/reset-password")
@rate_limit("LOGIN_RATE_LIMIT")
def reset_password():
    d = validate(json_body(), {"token": {"required": True, "max_len": 200},
                               "password": {"required": True, "max_len": 128}})
    check_password_strength(d["password"])
    h = hashlib.sha256(d["token"].encode()).hexdigest()
    user = User.query.filter_by(reset_token_hash=h).first()
    if not user or not user.reset_expires or user.reset_expires < utcnow():
        raise ApiError("This reset link is invalid or has expired. Request a new one.", 400, code="bad_token")
    user.set_password(d["password"])
    user.reset_token_hash = None
    user.reset_expires = None
    audit("password_reset", "user", user.id, user=user)
    db.session.commit()
    return jsonify({"message": "Password reset. You can sign in now."})
