"""Shared helpers: errors, validation, auth decorators, pagination, audit, rate limiting."""
import logging
import math
import re
import threading
import time
from datetime import date, datetime, timedelta
from functools import wraps

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import or_

from .extensions import db
from .models import AppConfig, AuditLog, User

log = logging.getLogger("insightflow")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApiError(Exception):
    def __init__(self, message, status=400, details=None, code=None):
        super().__init__(message)
        self.message, self.status, self.details, self.code = message, status, details, code


# ---------- validation ----------
def parse_date(value, field="date"):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(f"{field} must be in YYYY-MM-DD format", 400)


def validate(data, schema, partial=False):
    """schema: {field: {type, required, min, max, min_len, max_len, choices}} -> cleaned dict."""
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object", 400)
    errors, clean = {}, {}
    for field, rule in schema.items():
        raw = data.get(field)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            if rule.get("required") and not partial:
                errors[field] = "This field is required"
            elif field in data:
                clean[field] = None
            continue
        kind = rule.get("type", "str")
        try:
            if kind == "str":
                val = str(raw).strip()
                if len(val) > rule.get("max_len", 250):
                    raise ValueError(f"Must be at most {rule.get('max_len', 250)} characters")
                if len(val) < rule.get("min_len", 0):
                    raise ValueError(f"Must be at least {rule['min_len']} characters")
            elif kind == "email":
                val = str(raw).strip().lower()
                if not EMAIL_RE.match(val) or len(val) > 150:
                    raise ValueError("Enter a valid email address")
            elif kind == "int":
                if isinstance(raw, bool):
                    raise ValueError("Must be a whole number")
                val = int(raw)
            elif kind == "float":
                if isinstance(raw, bool):
                    raise ValueError("Must be a number")
                val = float(raw)
                if math.isnan(val) or math.isinf(val):
                    raise ValueError("Must be a number")
            elif kind == "date":
                val = parse_date(raw, field)
            elif kind == "bool":
                val = raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes")
            else:
                val = raw
            if "min" in rule and val < rule["min"]:
                raise ValueError(f"Must be at least {rule['min']}")
            if "max" in rule and val > rule["max"]:
                raise ValueError(f"Must be at most {rule['max']}")
            if "choices" in rule and val not in rule["choices"]:
                raise ValueError("Must be one of: " + ", ".join(map(str, rule["choices"])))
        except ApiError as e:
            errors[field] = e.message
            continue
        except (ValueError, TypeError) as e:
            errors[field] = str(e) if str(e) and "invalid literal" not in str(e) and "could not convert" not in str(e) else "Invalid value"
            continue
        clean[field] = val
    if errors:
        raise ApiError("Please fix the highlighted fields", 400, errors)
    return clean


def json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be valid JSON", 400)
    return data


# ---------- auth helpers ----------
def current_user():
    cached = getattr(request, "_if_user", None)
    if cached is not None:
        return cached
    uid = get_jwt_identity()
    user = db.session.get(User, int(uid)) if uid else None
    if not user or not user.is_active or (user.business and not user.business.is_active and user.role.name != "super_admin"):
        raise ApiError("Your account is not active", 401, code="inactive")
    request._if_user = user
    return user


def auth_required(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        verify_jwt_in_request()
        current_user()
        return fn(*a, **k)
    return wrapper


def permission_required(*codes):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            verify_jwt_in_request()
            user = current_user()
            have = user.permission_codes()
            if not any(c in have for c in codes):
                raise ApiError("You do not have permission to do this", 403, code="forbidden")
            return fn(*a, **k)
        return wrapper
    return deco


def biz_id():
    """Business the request operates on. Super admins may pass ?business_id=."""
    u = current_user()
    if u.role.name == "super_admin":
        bid = request.args.get("business_id", type=int)
        if bid:
            return bid
    if not u.business_id:
        raise ApiError("No business is assigned to this account", 400)
    return u.business_id


# ---------- config ----------
def get_config(key, default=None):
    row = db.session.get(AppConfig, key)
    return row.value if row and row.value is not None else default


def set_config(key, value):
    row = db.session.get(AppConfig, key)
    if row:
        row.value = value
    else:
        db.session.add(AppConfig(key=key, value=value))


# ---------- audit ----------
def audit(action, entity=None, entity_id=None, details=None, user=None, business_id=None):
    try:
        u = user or getattr(request, "_if_user", None)
        db.session.add(AuditLog(
            user_id=u.id if u else None,
            business_id=business_id if business_id is not None else (u.business_id if u else None),
            action=action, entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=(details or "")[:400] or None, ip=request.remote_addr))
    except Exception:  # auditing must never break the request
        log.exception("audit failed")


def audit_dict(a):
    return {"id": a.id, "action": a.action, "entity": a.entity, "entity_id": a.entity_id,
            "details": a.details, "ip": a.ip, "user_id": a.user_id,
            "user": a.user.full_name if a.user else "System",
            "business_id": a.business_id, "created_at": a.created_at.isoformat()}


# ---------- pagination ----------
def paginate(query, serialize, search_cols=(), sort_map=None, default_sort=None, default_order="desc"):
    q = request.args.get("q", "").strip()
    if q and search_cols:
        like = f"%{q[:80]}%"
        query = query.filter(or_(*[c.ilike(like) for c in search_cols]))
    sort_map = sort_map or {}
    key = request.args.get("sort")
    key = key if key in sort_map else default_sort
    order = request.args.get("order", default_order)
    if key in sort_map:
        col = sort_map[key]
        query = query.order_by(col.asc() if order == "asc" else col.desc())
    page = max(request.args.get("page", 1, type=int), 1)
    per = min(max(request.args.get("per_page", 10, type=int), 1), 100)
    total = query.order_by(None).count()
    items = query.limit(per).offset((page - 1) * per).all()
    return {"items": [serialize(i) for i in items], "page": page, "per_page": per,
            "total": total, "pages": max(math.ceil(total / per), 1)}


def date_range(default_days=30):
    end = parse_date(request.args.get("end"), "end") or date.today()
    start = parse_date(request.args.get("start"), "start") or end - timedelta(days=default_days - 1)
    if start > end:
        raise ApiError("start must not be after end", 400)
    return start, end


def previous_range(start, end):
    length = (end - start).days + 1
    pe = start - timedelta(days=1)
    return pe - timedelta(days=length - 1), pe


# ---------- rate limiting (in-memory, per process) ----------
_hits, _lock = {}, threading.Lock()


def _allow(key, limit, window=60):
    now = time.time()
    with _lock:
        arr = [t for t in _hits.get(key, []) if now - t < window]
        if len(arr) >= limit:
            _hits[key] = arr
            return False
        arr.append(now)
        _hits[key] = arr
        return True


def reset_rate_limits():
    with _lock:
        _hits.clear()


def check_global_rate_limit():
    if request.path.startswith("/api/") and not _allow(f"g:{request.remote_addr}", current_app.config["RATE_LIMIT_PER_MINUTE"]):
        raise ApiError("Too many requests. Please slow down.", 429, code="rate_limited")


def rate_limit(config_key):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if not _allow(f"{request.endpoint}:{request.remote_addr}", current_app.config[config_key]):
                raise ApiError("Too many attempts. Try again in a minute.", 429, code="rate_limited")
            return fn(*a, **k)
        return wrapper
    return deco


def error_response(e):
    body = {"error": e.message}
    if e.details:
        body["fields"] = e.details
    if e.code:
        body["code"] = e.code
    return jsonify(body), e.status
