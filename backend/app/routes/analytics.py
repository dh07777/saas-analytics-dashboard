"""Analytics computed from real database rows with pandas. Nothing here is hardcoded."""
import json
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import (AuditLog, Category, Customer, Expense, Order, OrderItem, Product, Transaction)
from ..services import refresh_alerts
from ..utils import (ApiError, audit_dict, biz_id, date_range, permission_required, previous_range)

bp = Blueprint("analytics", __name__)

RESAMPLE = {"daily": dict(rule="D"), "weekly": dict(rule="W-MON", closed="left", label="left"),
            "monthly": dict(rule="MS"), "yearly": dict(rule="YS")}
LABEL = {"daily": "%Y-%m-%d", "weekly": "%Y-%m-%d", "monthly": "%Y-%m", "yearly": "%Y"}


# ---------- data loading ----------
def _bounds(start, end):
    return (datetime.combine(start, time.min) if start else None,
            datetime.combine(end + timedelta(days=1), time.min) if end else None)


def orders_df(biz, start=None, end=None):
    a, b = _bounds(start, end)
    q = (db.session.query(Order.id, Order.order_date, Order.customer_id, Order.region, Order.total,
                          func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_cost), 0.0))
         .outerjoin(OrderItem, OrderItem.order_id == Order.id)
         .filter(Order.business_id == biz, Order.status == "completed"))
    if a:
        q = q.filter(Order.order_date >= a)
    if b:
        q = q.filter(Order.order_date < b)
    df = pd.DataFrame([tuple(r) for r in q.group_by(Order.id).all()],
                      columns=["id", "date", "customer_id", "region", "total", "cogs"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df[["total", "cogs"]] = df[["total", "cogs"]].astype(float)
    return df


def expenses_df(biz, start=None, end=None):
    q = db.session.query(Expense.expense_date, Expense.category, Expense.amount).filter(Expense.business_id == biz)
    if start:
        q = q.filter(Expense.expense_date >= start)
    if end:
        q = q.filter(Expense.expense_date <= end)
    df = pd.DataFrame([tuple(r) for r in q.all()], columns=["date", "category", "amount"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = df["amount"].astype(float)
    return df


def items_df(biz, start=None, end=None):
    a, b = _bounds(start, end)
    q = (db.session.query(Order.id, Order.order_date, Order.region, Product.id, Product.name,
                          Category.name, OrderItem.quantity, OrderItem.quantity * OrderItem.unit_price,
                          OrderItem.quantity * OrderItem.unit_cost)
         .join(OrderItem, OrderItem.order_id == Order.id)
         .join(Product, Product.id == OrderItem.product_id)
         .outerjoin(Category, Category.id == Product.category_id)
         .filter(Order.business_id == biz, Order.status == "completed"))
    if a:
        q = q.filter(Order.order_date >= a)
    if b:
        q = q.filter(Order.order_date < b)
    df = pd.DataFrame([tuple(r) for r in q.all()],
                      columns=["order_id", "date", "region", "product_id", "product", "category", "qty", "revenue", "cost"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["category"] = df["category"].fillna("Uncategorized")
        df["region"] = df["region"].fillna("Unspecified")
        df[["revenue", "cost"]] = df[["revenue", "cost"]].astype(float)
    return df


# ---------- small helpers ----------
def rec(df):
    """DataFrame -> JSON-safe list of dicts (NaN becomes null)."""
    return json.loads(df.to_json(orient="records")) if len(df) else []


def r2(x):
    return round(float(x), 2)


def pct(cur, prev):
    return None if not prev else round((cur - prev) / abs(prev) * 100, 1)


def summary(biz, start, end):
    od, ed = orders_df(biz, start, end), expenses_df(biz, start, end)
    revenue = r2(od["total"].sum()) if not od.empty else 0.0
    cogs = r2(od["cogs"].sum()) if not od.empty else 0.0
    expenses = r2(ed["amount"].sum()) if not ed.empty else 0.0
    orders = int(len(od))
    return {"revenue": revenue, "cogs": cogs, "gross_profit": r2(revenue - cogs), "expenses": expenses,
            "profit": r2(revenue - cogs - expenses), "orders": orders,
            "aov": r2(revenue / orders) if orders else 0.0,
            "margin": round((revenue - cogs - expenses) / revenue * 100, 1) if revenue else None}


def series(biz, gran, start=None, end=None):
    """Revenue / COGS / expenses / profit per period."""
    od, ed = orders_df(biz, start, end), expenses_df(biz, start, end)
    if od.empty and ed.empty:
        return []
    kw = RESAMPLE[gran]
    parts = []
    if not od.empty:
        o = od.set_index("date")
        parts += [o["total"].resample(**kw).sum().rename("revenue"),
                  o["cogs"].resample(**kw).sum().rename("cogs"),
                  o["id"].resample(**kw).count().rename("orders")]
    if not ed.empty:
        parts.append(ed.set_index("date")["amount"].resample(**kw).sum().rename("expenses"))
    m = pd.concat(parts, axis=1).fillna(0).sort_index()
    for c in ("revenue", "cogs", "orders", "expenses"):
        if c not in m:
            m[c] = 0.0
    m["gross_profit"] = m["revenue"] - m["cogs"]
    m["profit"] = m["gross_profit"] - m["expenses"]
    m["growth_pct"] = m["revenue"].pct_change().replace([np.inf, -np.inf], np.nan) * 100
    m = m.round(2)
    m["period"] = m.index.strftime(LABEL[gran])
    return rec(m.reset_index(drop=True)[["period", "revenue", "cogs", "gross_profit", "expenses",
                                          "profit", "orders", "growth_pct"]])


def forecast(biz, months=3):
    rows = series(biz, "monthly")
    today = date.today()
    if rows and rows[-1]["period"] == today.strftime("%Y-%m") and (today + timedelta(days=1)).day != 1:
        rows = rows[:-1]  # drop the month that is still in progress
    used = rows[-12:]
    meta = {"method": "Linear trend regression on recent full months", "months_used": len(used)}
    if len(used) < 3:
        return {"history": used, "forecast": [], "meta": {**meta, "note": "At least 3 full months of data are needed."}}
    y = np.array([r["revenue"] for r in used], dtype=float)
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    fit = slope * x + intercept
    resid = y - fit
    sd = float(resid.std(ddof=1)) if len(y) > 2 else 0.0
    ss_tot = float(((y - y.mean()) ** 2).sum())
    meta["r2"] = round(1 - float((resid ** 2).sum()) / ss_tot, 3) if ss_tot else None
    meta["monthly_trend"] = r2(slope)
    last = datetime.strptime(used[-1]["period"], "%Y-%m")
    out = []
    for i in range(1, months + 1):
        mth = (last.month - 1 + i) % 12 + 1
        yr = last.year + (last.month - 1 + i) // 12
        val = max(float(slope * (len(y) - 1 + i) + intercept), 0.0)
        out.append({"period": f"{yr}-{mth:02d}", "forecast": r2(val),
                    "lower": r2(max(val - 1.96 * sd, 0)), "upper": r2(val + 1.96 * sd)})
    return {"history": used, "forecast": out, "meta": meta}


# ---------- routes ----------
@bp.get("/dashboard")
@permission_required("dashboard.view")
def dashboard():
    biz = biz_id()
    start, end = date_range(30)
    ps, pe = previous_range(start, end)
    cur, prev = summary(biz, start, end), summary(biz, ps, pe)
    refresh_alerts(biz)
    a, b = _bounds(start, end)
    new_customers = Customer.query.filter(Customer.business_id == biz, Customer.created_at >= a, Customer.created_at < b).count()
    prev_a, prev_b = _bounds(ps, pe)
    prev_new = Customer.query.filter(Customer.business_id == biz, Customer.created_at >= prev_a, Customer.created_at < prev_b).count()
    monthly = series(biz, "monthly")
    full = monthly[:-1] if monthly and monthly[-1]["period"] == date.today().strftime("%Y-%m") else monthly
    monthly_growth = full[-1]["growth_pct"] if full else None
    trend_gran = "daily" if (end - start).days <= 62 else "monthly"
    items = items_df(biz, start, end)
    top_products, by_category = [], []
    if not items.empty:
        top_products = rec(items.groupby("product", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(5).round(2))
        by_category = rec(items.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).round(2))
    txns = (Transaction.query.filter_by(business_id=biz).order_by(Transaction.created_at.desc()).limit(8).all())
    activities = AuditLog.query.filter_by(business_id=biz).order_by(AuditLog.created_at.desc()).limit(8).all()
    orders_by_ref = {o.order_number: o for o in Order.query.filter(
        Order.order_number.in_([t.reference for t in txns if t.reference])).all()}
    return jsonify({
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "kpis": {**cur,
                 "total_customers": Customer.query.filter_by(business_id=biz).count(),
                 "new_customers": new_customers,
                 "revenue_growth": pct(cur["revenue"], prev["revenue"]),
                 "profit_growth": pct(cur["profit"], prev["profit"]),
                 "orders_growth": pct(cur["orders"], prev["orders"]),
                 "customers_growth": pct(new_customers, prev_new),
                 "monthly_growth": monthly_growth},
        "previous": prev,
        "trend": series(biz, trend_gran, start, end), "trend_granularity": trend_gran,
        "top_products": top_products, "by_category": by_category,
        "recent_transactions": [{
            "id": t.id, "type": t.type, "amount": t.amount, "method": t.method, "reference": t.reference,
            "customer": (orders_by_ref[t.reference].customer.name if t.reference in orders_by_ref and orders_by_ref[t.reference].customer else "Walk-in"),
            "created_at": t.created_at.isoformat()} for t in txns],
        "recent_activities": [audit_dict(x) for x in activities]})


@bp.get("/revenue")
@permission_required("analytics.view")
def revenue():
    biz = biz_id()
    start, end = date_range(90)
    gran = request.args.get("granularity", "monthly")
    if gran not in RESAMPLE:
        raise ApiError("granularity must be daily, weekly, monthly or yearly", 400)
    months = min(max(request.args.get("forecast_months", 3, type=int), 1), 12)
    ps, pe = previous_range(start, end)
    cur, prev = summary(biz, start, end), summary(biz, ps, pe)
    return jsonify({
        "range": {"start": start.isoformat(), "end": end.isoformat()}, "granularity": gran,
        "series": series(biz, gran, start, end), "summary": cur, "previous": prev,
        "comparison": {k: {"current": cur[k], "previous": prev[k], "change_pct": pct(cur[k], prev[k])}
                       for k in ("revenue", "gross_profit", "expenses", "profit", "orders")},
        "forecast": forecast(biz, months)})


@bp.get("/customers")
@permission_required("analytics.view")
def customers():
    biz = biz_id()
    start, end = date_range(90)
    ps, pe = previous_range(start, end)
    allo = orders_df(biz)
    allo = allo[allo["customer_id"].notna()] if not allo.empty else allo
    s, e = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    ps_t, pe_t = pd.Timestamp(ps), pd.Timestamp(pe) + pd.Timedelta(days=1)
    total = Customer.query.filter_by(business_id=biz).count()
    registered = Customer.query.filter(Customer.business_id == biz, Customer.created_at >= _bounds(start, end)[0],
                                       Customer.created_at < _bounds(start, end)[1]).count()
    out = {"range": {"start": start.isoformat(), "end": end.isoformat()}, "total_customers": total,
           "registered_in_period": registered}
    segments, top, ltv = [], [], None
    new_n = ret_n = 0
    retention = None
    if not allo.empty:
        first = allo.groupby("customer_id")["date"].min()
        in_period = allo[(allo["date"] >= s) & (allo["date"] < e)]
        active = set(in_period["customer_id"].astype(int))
        new_ids = {c for c in active if first[c] >= s}
        new_n, ret_n = len(new_ids), len(active - new_ids)
        prev_active = set(allo[(allo["date"] >= ps_t) & (allo["date"] < pe_t)]["customer_id"].astype(int))
        if prev_active:
            retention = round(len(prev_active & active) / len(prev_active) * 100, 1)
        g = allo.groupby("customer_id").agg(spend=("total", "sum"), cogs=("cogs", "sum"),
                                            orders=("id", "count"), last=("date", "max"), first=("date", "min"))
        g["profit"] = g["spend"] - g["cogs"]
        today = pd.Timestamp(date.today())
        thr = g["spend"].quantile(0.8) if len(g) >= 5 else float("inf")

        def seg(r):
            if (today - r["first"]).days <= 30:
                return "New"
            if r["spend"] >= thr:
                return "VIP"
            d = (today - r["last"]).days
            return "Active" if d <= 90 else ("At risk" if d <= 180 else "Lost")
        g["segment"] = g.apply(seg, axis=1)
        segments = rec(g.groupby("segment").agg(customers=("spend", "count"), revenue=("spend", "sum"))
                       .round(2).reset_index())
        ltv = {"avg_revenue_per_customer": r2(g["spend"].mean()), "avg_lifetime_value": r2(g["profit"].mean()),
               "avg_orders_per_customer": round(float(g["orders"].mean()), 2),
               "avg_order_value": r2(g["spend"].sum() / g["orders"].sum())}
        names = {c.id: c.name for c in Customer.query.filter(Customer.id.in_([int(i) for i in g.index])).all()}
        tg = g.sort_values("spend", ascending=False).head(10)
        top = [{"customer_id": int(i), "name": names.get(int(i), "Unknown"), "orders": int(r["orders"]),
                "revenue": r2(r["spend"]), "lifetime_value": r2(r["profit"]), "segment": r["segment"],
                "last_order": r["last"].strftime("%Y-%m-%d")} for i, r in tg.iterrows()]
    cdf = pd.DataFrame([(c[0],) for c in db.session.query(Customer.created_at).filter(Customer.business_id == biz).all()],
                       columns=["date"])
    growth = []
    if not cdf.empty:
        cdf["date"] = pd.to_datetime(cdf["date"])
        m = cdf.set_index("date").assign(n=1)["n"].resample("MS").sum().to_frame("new")
        m["total"] = m["new"].cumsum()
        m["period"] = m.index.strftime("%Y-%m")
        growth = rec(m.reset_index(drop=True).tail(18))
    out.update({"new_customers": new_n, "returning_customers": ret_n, "retention_rate": retention,
                "segments": segments, "lifetime_value": ltv, "top_customers": top, "growth": growth})
    return jsonify(out)


@bp.get("/sales")
@permission_required("analytics.view")
def sales():
    biz = biz_id()
    start, end = date_range(90)
    ps, pe = previous_range(start, end)
    it, prev = items_df(biz, start, end), items_df(biz, ps, pe)
    res = {"range": {"start": start.isoformat(), "end": end.isoformat()},
           "totals": {"sales": 0.0, "units": 0, "orders": 0, "aov": 0.0, "previous_sales": 0.0, "change_pct": None},
           "by_category": [], "by_product": [], "by_region": [], "comparison": [], "trend": []}
    if not it.empty:
        total = r2(it["revenue"].sum())
        orders = int(it["order_id"].nunique())
        prev_total = r2(prev["revenue"].sum()) if not prev.empty else 0.0
        res["totals"] = {"sales": total, "units": int(it["qty"].sum()), "orders": orders,
                         "aov": r2(total / orders), "previous_sales": prev_total, "change_pct": pct(total, prev_total)}
        res["by_category"] = rec(it.groupby("category", as_index=False).agg(revenue=("revenue", "sum"), units=("qty", "sum"))
                                 .sort_values("revenue", ascending=False).round(2))
        res["by_product"] = rec(it.groupby("product", as_index=False).agg(revenue=("revenue", "sum"), units=("qty", "sum"))
                                .sort_values("revenue", ascending=False).head(10).round(2))
        res["by_region"] = rec(it.groupby("region", as_index=False).agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
                               .sort_values("revenue", ascending=False).round(2))
        c = it.groupby("category")["revenue"].sum().rename("current")
        p = prev.groupby("category")["revenue"].sum().rename("previous") if not prev.empty else pd.Series(name="previous", dtype=float)
        cmp_ = pd.concat([c, p], axis=1).fillna(0).round(2)
        cmp_["change_pct"] = ((cmp_["current"] - cmp_["previous"]) / cmp_["previous"].replace(0, np.nan) * 100).round(1)
        res["comparison"] = rec(cmp_.reset_index().rename(columns={"index": "category"}).sort_values("current", ascending=False))
        res["trend"] = series(biz, "daily" if (end - start).days <= 62 else "monthly", start, end)
    return jsonify(res)


@bp.get("/products")
@permission_required("analytics.view")
def products():
    biz = biz_id()
    start, end = date_range(90)
    days = (end - start).days + 1
    it = items_df(biz, start, end)
    rows = (db.session.query(Product, Category.name).outerjoin(Category, Category.id == Product.category_id)
            .filter(Product.business_id == biz).all())
    pdf = pd.DataFrame([{"product_id": p.id, "name": p.name, "sku": p.sku, "category": c or "Uncategorized",
                         "stock": p.stock, "reorder_level": p.reorder_level, "price": p.price, "cost": p.cost,
                         "is_active": p.is_active} for p, c in rows])
    res = {"range": {"start": start.isoformat(), "end": end.isoformat()}, "kpis": {"active_products": 0, "stock_value": 0.0,
           "retail_value": 0.0, "low_stock": 0, "out_of_stock": 0, "overstocked": 0},
           "best_sellers": [], "low_performers": [], "category_performance": [], "low_stock_items": [], "inventory": []}
    if pdf.empty:
        return jsonify(res)
    if it.empty:
        sold = pd.DataFrame({"product_id": pd.Series(dtype="int64"), "revenue": pd.Series(dtype="float64"),
                             "units": pd.Series(dtype="float64"), "cogs": pd.Series(dtype="float64")})
    else:
        sold = (it.groupby("product_id").agg(revenue=("revenue", "sum"), units=("qty", "sum"), cogs=("cost", "sum"))
                .reset_index())
    m = pdf.merge(sold, on="product_id", how="left").fillna({"revenue": 0, "units": 0, "cogs": 0})
    m["profit"] = m["revenue"] - m["cogs"]
    m["margin_pct"] = np.where(m["revenue"] > 0, m["profit"] / m["revenue"].replace(0, np.nan) * 100, np.nan)
    m["days_of_cover"] = np.where(m["units"] > 0, m["stock"] / (m["units"] / days).replace(0, np.nan), np.nan)
    act = m[m["is_active"]]
    cols = ["product_id", "name", "sku", "category", "revenue", "units", "profit", "margin_pct", "stock"]
    res["best_sellers"] = rec(act.sort_values("revenue", ascending=False).head(10)[cols].round(2))
    res["low_performers"] = rec(act.sort_values(["revenue", "units"]).head(10)[cols].round(2))
    res["category_performance"] = rec(act.groupby("category", as_index=False).agg(
        revenue=("revenue", "sum"), profit=("profit", "sum"), units=("units", "sum"), products=("product_id", "count"))
        .sort_values("revenue", ascending=False).round(2))
    low = act[act["stock"] <= act["reorder_level"]].sort_values("stock")
    res["low_stock_items"] = rec(low[["product_id", "name", "sku", "category", "stock", "reorder_level", "days_of_cover"]].head(15).round(1))
    res["inventory"] = rec(act.sort_values("stock")[["product_id", "name", "category", "stock", "reorder_level", "days_of_cover", "units"]].round(1))
    res["kpis"] = {"active_products": int(len(act)), "stock_value": r2((act["stock"] * act["cost"]).sum()),
                   "retail_value": r2((act["stock"] * act["price"]).sum()), "low_stock": int(len(low)),
                   "out_of_stock": int((act["stock"] <= 0).sum()),
                   "overstocked": int((act["days_of_cover"] > 180).sum())}
    return jsonify(res)


@bp.get("/expenses")
@permission_required("analytics.view")
def expense_analytics():
    biz = biz_id()
    start, end = date_range(180)
    ed = expenses_df(biz, start, end)
    by_cat = rec(ed.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False).round(2)) if not ed.empty else []
    return jsonify({"range": {"start": start.isoformat(), "end": end.isoformat()}, "summary": summary(biz, start, end),
                    "by_category": by_cat, "monthly": series(biz, "monthly", start, end)})
