"""CRUD for customers, categories, products, orders and expenses."""
from datetime import datetime, time

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import (ORDER_STATUSES, REGIONS, Category, Customer, Expense, Order, OrderItem, Product, Transaction)
from ..services import change_order_status, create_order, delete_order
from ..utils import (ApiError, audit, biz_id, current_user, json_body, paginate, parse_date,
                     permission_required, validate)

bp = Blueprint("data", __name__)
READ, WRITE = "data.read", "data.write"
EXPENSE_CATEGORIES = ["Rent", "Salaries", "Marketing", "Utilities", "Software", "Shipping", "Insurance",
                      "Supplies", "Travel", "Taxes", "Other"]


def _own(model, id_, biz):
    obj = db.session.get(model, id_)
    if not obj or getattr(obj, "business_id", biz) != biz:
        raise ApiError(f"{model.__name__} not found", 404)
    return obj


# ---------- customers ----------
def _cust(c, stats=None):
    s = (stats or {}).get(c.id, (0, 0.0))
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "region": c.region,
            "is_sample": c.is_sample, "orders": s[0], "total_spent": round(s[1], 2),
            "created_at": c.created_at.isoformat()}


CUSTOMER_SCHEMA = {"name": {"required": True, "min_len": 2, "max_len": 120}, "email": {"type": "email"},
                   "phone": {"max_len": 40}, "region": {"choices": REGIONS}}


@bp.get("/customers")
@permission_required(READ)
def list_customers():
    biz = biz_id()
    q = Customer.query.filter_by(business_id=biz)
    if request.args.get("region"):
        q = q.filter(Customer.region == request.args["region"])
    page = paginate(q, lambda c: c, (Customer.name, Customer.email, Customer.phone),
                    {"name": Customer.name, "created_at": Customer.created_at, "region": Customer.region}, "created_at")
    ids = [c.id for c in page["items"]]
    stats = {r[0]: (r[1], float(r[2])) for r in db.session.query(
        Order.customer_id, func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).filter(
        Order.customer_id.in_(ids), Order.status == "completed").group_by(Order.customer_id).all()} if ids else {}
    page["items"] = [_cust(c, stats) for c in page["items"]]
    page["regions"] = REGIONS
    return jsonify(page)


@bp.post("/customers")
@permission_required(WRITE)
def create_customer():
    d = validate(json_body(), CUSTOMER_SCHEMA)
    c = Customer(business_id=biz_id(), **d)
    db.session.add(c)
    db.session.flush()
    audit("create", "customer", c.id, c.name)
    db.session.commit()
    return jsonify(_cust(c)), 201


@bp.put("/customers/<int:cid>")
@permission_required(WRITE)
def update_customer(cid):
    c = _own(Customer, cid, biz_id())
    for k, v in validate(json_body(), CUSTOMER_SCHEMA, partial=True).items():
        setattr(c, k, v)
    audit("update", "customer", c.id, c.name)
    db.session.commit()
    return jsonify(_cust(c))


@bp.delete("/customers/<int:cid>")
@permission_required(WRITE)
def delete_customer(cid):
    c = _own(Customer, cid, biz_id())
    if Order.query.filter_by(customer_id=c.id).count():
        raise ApiError("This customer has orders and cannot be deleted.", 409)
    audit("delete", "customer", c.id, c.name)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Customer deleted"})


# ---------- categories ----------
@bp.get("/categories")
@permission_required(READ)
def list_categories():
    biz = biz_id()
    counts = dict(db.session.query(Product.category_id, func.count(Product.id)).filter(
        Product.business_id == biz).group_by(Product.category_id).all())
    q = Category.query.filter_by(business_id=biz)
    if request.args.get("all"):
        return jsonify({"items": [{"id": c.id, "name": c.name} for c in q.order_by(Category.name).all()]})
    return jsonify(paginate(q, lambda c: {"id": c.id, "name": c.name, "products": counts.get(c.id, 0)},
                            (Category.name,), {"name": Category.name}, "name", "asc"))


@bp.post("/categories")
@permission_required(WRITE)
def create_category():
    biz = biz_id()
    d = validate(json_body(), {"name": {"required": True, "min_len": 2, "max_len": 100}})
    if Category.query.filter_by(business_id=biz, name=d["name"]).first():
        raise ApiError("That category already exists", 409, {"name": "Already exists"})
    c = Category(business_id=biz, name=d["name"])
    db.session.add(c)
    db.session.flush()
    audit("create", "category", c.id, c.name)
    db.session.commit()
    return jsonify({"id": c.id, "name": c.name, "products": 0}), 201


@bp.put("/categories/<int:cid>")
@permission_required(WRITE)
def update_category(cid):
    biz = biz_id()
    c = _own(Category, cid, biz)
    d = validate(json_body(), {"name": {"required": True, "min_len": 2, "max_len": 100}})
    if Category.query.filter(Category.business_id == biz, Category.name == d["name"], Category.id != cid).first():
        raise ApiError("That category already exists", 409, {"name": "Already exists"})
    c.name = d["name"]
    audit("update", "category", c.id, c.name)
    db.session.commit()
    return jsonify({"id": c.id, "name": c.name})


@bp.delete("/categories/<int:cid>")
@permission_required(WRITE)
def delete_category(cid):
    c = _own(Category, cid, biz_id())
    if Product.query.filter_by(category_id=c.id).count():
        raise ApiError("Move or delete the products in this category first.", 409)
    audit("delete", "category", c.id, c.name)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Category deleted"})


# ---------- products ----------
def _prod(p):
    return {"id": p.id, "sku": p.sku, "name": p.name, "category_id": p.category_id,
            "category": p.category.name if p.category else None, "price": p.price, "cost": p.cost,
            "stock": p.stock, "reorder_level": p.reorder_level, "is_active": p.is_active,
            "is_sample": p.is_sample, "low_stock": p.stock <= p.reorder_level}


PRODUCT_SCHEMA = {"name": {"required": True, "min_len": 2, "max_len": 150}, "sku": {"required": True, "max_len": 40},
                  "category_id": {"type": "int"}, "price": {"type": "float", "required": True, "min": 0, "max": 10_000_000},
                  "cost": {"type": "float", "min": 0, "max": 10_000_000}, "stock": {"type": "int", "min": 0, "max": 10_000_000},
                  "reorder_level": {"type": "int", "min": 0, "max": 1_000_000}, "is_active": {"type": "bool"}}


def _check_category(biz, d):
    if d.get("category_id"):
        _own(Category, d["category_id"], biz)


@bp.get("/products")
@permission_required(READ)
def list_products():
    biz = biz_id()
    q = Product.query.filter_by(business_id=biz)
    if request.args.get("category_id", type=int):
        q = q.filter(Product.category_id == request.args.get("category_id", type=int))
    if request.args.get("low_stock"):
        q = q.filter(Product.stock <= Product.reorder_level)
    if request.args.get("active"):
        q = q.filter(Product.is_active.is_(True))
    return jsonify(paginate(q, _prod, (Product.name, Product.sku),
                            {"name": Product.name, "price": Product.price, "stock": Product.stock,
                             "sku": Product.sku, "created_at": Product.created_at}, "name", "asc"))


@bp.post("/products")
@permission_required(WRITE)
def create_product():
    biz = biz_id()
    d = validate(json_body(), PRODUCT_SCHEMA)
    _check_category(biz, d)
    if Product.query.filter_by(business_id=biz, sku=d["sku"]).first():
        raise ApiError("That SKU is already used", 409, {"sku": "Already used"})
    p = Product(business_id=biz, **{"cost": 0, "stock": 0, "reorder_level": 10, "is_active": True, **{k: v for k, v in d.items() if v is not None}})
    db.session.add(p)
    db.session.flush()
    audit("create", "product", p.id, p.name)
    db.session.commit()
    return jsonify(_prod(p)), 201


@bp.put("/products/<int:pid>")
@permission_required(WRITE)
def update_product(pid):
    biz = biz_id()
    p = _own(Product, pid, biz)
    d = validate(json_body(), PRODUCT_SCHEMA, partial=True)
    _check_category(biz, d)
    if d.get("sku") and Product.query.filter(Product.business_id == biz, Product.sku == d["sku"], Product.id != pid).first():
        raise ApiError("That SKU is already used", 409, {"sku": "Already used"})
    for k, v in d.items():
        if v is not None or k == "category_id":
            setattr(p, k, v)
    audit("update", "product", p.id, p.name)
    db.session.commit()
    return jsonify(_prod(p))


@bp.delete("/products/<int:pid>")
@permission_required(WRITE)
def delete_product(pid):
    p = _own(Product, pid, biz_id())
    if OrderItem.query.filter_by(product_id=p.id).count():
        p.is_active = False  # keep history intact; retire instead of deleting
        audit("deactivate", "product", p.id, p.name)
        db.session.commit()
        return jsonify({"message": "Product has sales history, so it was deactivated instead of deleted."})
    audit("delete", "product", p.id, p.name)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": "Product deleted"})


# ---------- orders ----------
def _order(o, detail=False):
    d = {"id": o.id, "order_number": o.order_number, "status": o.status, "region": o.region, "total": o.total,
         "customer_id": o.customer_id, "customer": o.customer.name if o.customer else "Walk-in",
         "order_date": o.order_date.isoformat(), "is_sample": o.is_sample, "item_count": sum(i.quantity for i in o.items)}
    if detail:
        d["items"] = [{"product_id": i.product_id, "product": i.product.name if i.product else None,
                       "quantity": i.quantity, "unit_price": i.unit_price} for i in o.items]
    return d


@bp.get("/orders")
@permission_required(READ)
def list_orders():
    biz = biz_id()
    q = Order.query.filter_by(business_id=biz).outerjoin(Customer, Customer.id == Order.customer_id)
    if request.args.get("status") in ORDER_STATUSES:
        q = q.filter(Order.status == request.args["status"])
    s, e = parse_date(request.args.get("start"), "start"), parse_date(request.args.get("end"), "end")
    if s:
        q = q.filter(Order.order_date >= datetime.combine(s, time.min))
    if e:
        q = q.filter(Order.order_date <= datetime.combine(e, time.max))
    return jsonify(paginate(q, _order, (Order.order_number, Customer.name),
                            {"order_date": Order.order_date, "total": Order.total, "status": Order.status,
                             "order_number": Order.order_number}, "order_date"))


@bp.get("/orders/<int:oid>")
@permission_required(READ)
def get_order(oid):
    return jsonify(_order(_own(Order, oid, biz_id()), True))


@bp.post("/orders")
@permission_required(WRITE)
def post_order():
    biz = biz_id()
    body = json_body()
    d = validate(body, {"customer_id": {"type": "int"}, "region": {"choices": REGIONS},
                        "status": {"choices": ["completed", "pending"]},
                        "method": {"choices": ["card", "bank transfer", "paypal", "cash"]}})
    items = body.get("items")
    if not isinstance(items, list) or not items or len(items) > 50:
        raise ApiError("Add between 1 and 50 items", 400, {"items": "Add at least one item"})
    clean = []
    for it in items:
        v = validate(it if isinstance(it, dict) else {}, {"product_id": {"type": "int", "required": True},
                                                          "quantity": {"type": "int", "required": True, "min": 1, "max": 10000}})
        clean.append(v)
    if d.get("customer_id"):
        _own(Customer, d["customer_id"], biz)
    try:
        order = create_order(biz, clean, d.get("customer_id"), d.get("status") or "completed", d.get("region"),
                             created_by=current_user().id, method=d.get("method"))
    except ApiError:
        db.session.rollback()
        raise
    audit("create", "order", order.id, f"{order.order_number} total {order.total}")
    db.session.commit()
    return jsonify(_order(order, True)), 201


@bp.patch("/orders/<int:oid>")
@permission_required(WRITE)
def patch_order(oid):
    o = _own(Order, oid, biz_id())
    d = validate(json_body(), {"status": {"required": True, "choices": ORDER_STATUSES}})
    change_order_status(o, d["status"])
    audit("status", "order", o.id, f"{o.order_number} -> {o.status}")
    db.session.commit()
    return jsonify(_order(o, True))


@bp.delete("/orders/<int:oid>")
@permission_required(WRITE)
def remove_order(oid):
    o = _own(Order, oid, biz_id())
    audit("delete", "order", o.id, o.order_number)
    delete_order(o)
    db.session.commit()
    return jsonify({"message": "Order deleted"})


# ---------- expenses ----------
def _exp(e):
    return {"id": e.id, "category": e.category, "description": e.description, "vendor": e.vendor,
            "amount": e.amount, "expense_date": e.expense_date.isoformat(), "is_sample": e.is_sample}


EXPENSE_SCHEMA = {"category": {"required": True, "max_len": 60}, "description": {"max_len": 250},
                  "vendor": {"max_len": 120}, "amount": {"type": "float", "required": True, "min": 0.01, "max": 100_000_000},
                  "expense_date": {"type": "date", "required": True}}


@bp.get("/expenses")
@permission_required(READ)
def list_expenses():
    biz = biz_id()
    q = Expense.query.filter_by(business_id=biz)
    if request.args.get("category"):
        q = q.filter(Expense.category == request.args["category"])
    s, e = parse_date(request.args.get("start"), "start"), parse_date(request.args.get("end"), "end")
    if s:
        q = q.filter(Expense.expense_date >= s)
    if e:
        q = q.filter(Expense.expense_date <= e)
    page = paginate(q, _exp, (Expense.description, Expense.vendor, Expense.category),
                    {"expense_date": Expense.expense_date, "amount": Expense.amount, "category": Expense.category}, "expense_date")
    used = [r[0] for r in db.session.query(Expense.category).filter_by(business_id=biz).distinct().all()]
    page["categories"] = sorted(set(EXPENSE_CATEGORIES) | set(used))
    return jsonify(page)


@bp.post("/expenses")
@permission_required(WRITE)
def create_expense():
    d = validate(json_body(), EXPENSE_SCHEMA)
    e = Expense(business_id=biz_id(), created_by=current_user().id, **d)
    db.session.add(e)
    db.session.flush()
    audit("create", "expense", e.id, f"{e.category} {e.amount}")
    db.session.commit()
    return jsonify(_exp(e)), 201


@bp.put("/expenses/<int:eid>")
@permission_required(WRITE)
def update_expense(eid):
    e = _own(Expense, eid, biz_id())
    for k, v in validate(json_body(), EXPENSE_SCHEMA, partial=True).items():
        if v is not None:
            setattr(e, k, v)
    audit("update", "expense", e.id, f"{e.category} {e.amount}")
    db.session.commit()
    return jsonify(_exp(e))


@bp.delete("/expenses/<int:eid>")
@permission_required(WRITE)
def delete_expense(eid):
    e = _own(Expense, eid, biz_id())
    audit("delete", "expense", e.id, f"{e.category} {e.amount}")
    db.session.delete(e)
    db.session.commit()
    return jsonify({"message": "Expense deleted"})


# ---------- transactions ----------
def _txn(t, customers):
    return {"id": t.id, "type": t.type, "amount": t.amount, "method": t.method, "status": t.status,
            "reference": t.reference, "customer": customers.get(t.order_id, "Walk-in"),
            "created_at": t.created_at.isoformat(), "is_sample": t.is_sample}


@bp.get("/transactions")
@permission_required(READ)
def list_transactions():
    biz = biz_id()
    q = Transaction.query.filter_by(business_id=biz)
    if request.args.get("type") in ("sale", "refund"):
        q = q.filter(Transaction.type == request.args["type"])
    if request.args.get("method"):
        q = q.filter(Transaction.method == request.args["method"])
    s, e = parse_date(request.args.get("start"), "start"), parse_date(request.args.get("end"), "end")
    if s:
        q = q.filter(Transaction.created_at >= datetime.combine(s, time.min))
    if e:
        q = q.filter(Transaction.created_at <= datetime.combine(e, time.max))
    page = paginate(q, lambda t: t, (Transaction.reference, Transaction.method),
                    {"created_at": Transaction.created_at, "amount": Transaction.amount, "type": Transaction.type,
                     "reference": Transaction.reference}, "created_at")
    oids = [t.order_id for t in page["items"] if t.order_id]
    names = {o.id: (o.customer.name if o.customer else "Walk-in") for o in Order.query.filter(Order.id.in_(oids)).all()} if oids else {}
    page["items"] = [_txn(t, names) for t in page["items"]]
    sales = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.business_id == biz, Transaction.type == "sale").scalar()
    refunds = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.business_id == biz, Transaction.type == "refund").scalar()
    page["totals"] = {"sales": round(float(sales), 2), "refunds": round(float(refunds), 2),
                      "net": round(float(sales) - float(refunds), 2)}
    return jsonify(page)
