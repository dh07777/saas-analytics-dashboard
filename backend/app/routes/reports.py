"""Report generation with CSV / PDF export."""
import csv
import io
from datetime import datetime, time, timedelta

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import Category, Customer, Expense, Order, OrderItem, Product, Report
from ..utils import (ApiError, audit, biz_id, current_user, date_range, json_body, paginate,
                     parse_date, permission_required, validate)
from .analytics import series

bp = Blueprint("reports", __name__)
TYPES = {"revenue": "Revenue report", "sales": "Sales report", "customers": "Customer report",
         "products": "Product report", "expenses": "Expense report"}
PERM = "reports.generate"


def build_report(rtype, biz, start, end):
    a, b = datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)
    if rtype == "revenue":
        gran = "daily" if (end - start).days <= 92 else "monthly"
        cols = ["Period", "Orders", "Revenue", "Cost of goods", "Gross profit", "Expenses", "Net profit"]
        rows = [[r["period"], int(r["orders"]), r["revenue"], r["cogs"], r["gross_profit"], r["expenses"], r["profit"]]
                for r in series(biz, gran, start, end)]
    elif rtype == "sales":
        cols = ["Order", "Date", "Customer", "Region", "Status", "Items", "Total"]
        q = (Order.query.filter(Order.business_id == biz, Order.order_date >= a, Order.order_date < b)
             .order_by(Order.order_date.desc()))
        rows = [[o.order_number, o.order_date.strftime("%Y-%m-%d"), o.customer.name if o.customer else "Walk-in",
                 o.region or "", o.status, sum(i.quantity for i in o.items), round(o.total, 2)] for o in q.all()]
    elif rtype == "customers":
        cols = ["Customer", "Email", "Region", "Joined", "Orders in period", "Revenue in period"]
        stats = {r[0]: (r[1], float(r[2])) for r in db.session.query(
            Order.customer_id, func.count(Order.id), func.sum(Order.total)).filter(
            Order.business_id == biz, Order.status == "completed", Order.order_date >= a, Order.order_date < b
        ).group_by(Order.customer_id).all()}
        rows = [[c.name, c.email or "", c.region or "", c.created_at.strftime("%Y-%m-%d"),
                 stats.get(c.id, (0, 0))[0], round(stats.get(c.id, (0, 0))[1], 2)]
                for c in Customer.query.filter_by(business_id=biz).order_by(Customer.name).all()]
        rows.sort(key=lambda r: -r[5])
    elif rtype == "products":
        cols = ["Product", "SKU", "Category", "Units sold", "Revenue", "Profit", "Stock"]
        sold = {r[0]: (int(r[1]), float(r[2]), float(r[3])) for r in db.session.query(
            OrderItem.product_id, func.sum(OrderItem.quantity),
            func.sum(OrderItem.quantity * OrderItem.unit_price), func.sum(OrderItem.quantity * OrderItem.unit_cost)
        ).join(Order, Order.id == OrderItem.order_id).filter(
            Order.business_id == biz, Order.status == "completed", Order.order_date >= a, Order.order_date < b
        ).group_by(OrderItem.product_id).all()}
        rows = []
        for p, cname in db.session.query(Product, Category.name).outerjoin(Category, Category.id == Product.category_id).filter(Product.business_id == biz).all():
            u, rev, cost = sold.get(p.id, (0, 0.0, 0.0))
            rows.append([p.name, p.sku, cname or "", u, round(rev, 2), round(rev - cost, 2), p.stock])
        rows.sort(key=lambda r: -r[4])
    elif rtype == "expenses":
        cols = ["Date", "Category", "Description", "Vendor", "Amount"]
        rows = [[e.expense_date.isoformat(), e.category, e.description or "", e.vendor or "", round(e.amount, 2)]
                for e in Expense.query.filter(Expense.business_id == biz, Expense.expense_date >= start,
                                              Expense.expense_date <= end).order_by(Expense.expense_date.desc()).all()]
    else:
        raise ApiError("Unknown report type", 400)
    return cols, rows


def _csv_safe(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not _is_number(s) else s


def _is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def to_csv(cols, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols)
    for r in rows:
        w.writerow([_csv_safe(v) if isinstance(v, str) else v for v in r])
    return out.getvalue().encode("utf-8-sig")


def to_pdf(title, subtitle, cols, rows):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28)
    st = getSampleStyleSheet()
    data = [cols] + [[("" if v is None else v) for v in r] for r in rows[:2000]] if rows else [cols, ["No data for this period"] + [""] * (len(cols) - 1)]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2A36")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF2F4")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D3D9")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    doc.build([Paragraph(title, st["Title"]), Paragraph(subtitle, st["Normal"]), Spacer(1, 12), table])
    return buf.getvalue()


def _params():
    rtype = request.args.get("type", "revenue")
    if rtype not in TYPES:
        raise ApiError("Unknown report type", 400)
    start, end = date_range(30)
    return rtype, start, end


@bp.post("/reports")
@permission_required(PERM)
def generate():
    biz = biz_id()
    d = validate(json_body(), {"type": {"required": True, "choices": list(TYPES)}, "start": {"type": "date", "required": True},
                               "end": {"type": "date", "required": True}, "name": {"max_len": 150}})
    if d["start"] > d["end"]:
        raise ApiError("Start date must be before end date", 400, {"start": "Must be before end"})
    cols, rows = build_report(d["type"], biz, d["start"], d["end"])
    name = d.get("name") or f"{TYPES[d['type']]} {d['start']} to {d['end']}"
    rep = Report(business_id=biz, user_id=current_user().id, name=name, type=d["type"], start_date=d["start"],
                 end_date=d["end"], row_count=len(rows))
    db.session.add(rep)
    db.session.flush()
    audit("generate", "report", rep.id, name)
    db.session.commit()
    return jsonify({"id": rep.id, "name": name, "type": d["type"], "columns": cols, "rows": rows[:1000],
                    "row_count": len(rows), "truncated": len(rows) > 1000}), 201


@bp.get("/reports")
@permission_required(PERM)
def history():
    q = Report.query.filter_by(business_id=biz_id())
    return jsonify(paginate(q, lambda r: {"id": r.id, "name": r.name, "type": r.type, "start": r.start_date.isoformat(),
                                          "end": r.end_date.isoformat(), "row_count": r.row_count,
                                          "created_at": r.created_at.isoformat()},
                            (Report.name,), {"created_at": Report.created_at, "name": Report.name}, "created_at"))


@bp.get("/reports/export")
@permission_required(PERM)
def export():
    biz = biz_id()
    rtype, start, end = _params()
    fmt = request.args.get("format", "csv")
    if fmt not in ("csv", "pdf"):
        raise ApiError("format must be csv or pdf", 400)
    cols, rows = build_report(rtype, biz, start, end)
    fname = f"insightflow-{rtype}-{start}-to-{end}.{fmt}"
    audit("export", "report", None, f"{rtype} {fmt} {start}..{end}")
    db.session.commit()
    if fmt == "csv":
        body, mime = to_csv(cols, rows), "text/csv; charset=utf-8"
    else:
        biz_name = current_user().business.name if current_user().business else "InsightFlow"
        body, mime = to_pdf(TYPES[rtype], f"{biz_name} | {start} to {end} | {len(rows)} rows", cols, rows), "application/pdf"
    return Response(body, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{fname}"',
                                                  "Access-Control-Expose-Headers": "Content-Disposition"})


@bp.delete("/reports/<int:rid>")
@permission_required(PERM)
def delete_report(rid):
    r = db.session.get(Report, rid)
    if not r or r.business_id != biz_id():
        raise ApiError("Report not found", 404)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"message": "Report removed from history"})
