"""Roles/permissions bootstrap and realistic SAMPLE data (every sample row has is_sample=True)."""
import random
from datetime import date, datetime, timedelta

from .extensions import db
from .models import (REGIONS, Business, Category, Customer, Expense, Notification, Order,
                     OrderItem, Permission, Product, Role, Transaction, User, UserSetting)
from .services import PAYMENT_METHODS, add_transaction

PERMISSIONS = {
    "dashboard.view": "View the dashboard",
    "analytics.view": "View analytics pages",
    "data.read": "View customers, products, orders and expenses",
    "data.write": "Create, edit and delete business records",
    "reports.generate": "Generate and export reports",
    "users.manage": "Manage users in the business",
    "settings.edit": "Edit company settings",
    "audit.view": "View audit logs",
    "admin.access": "Use the system admin panel",
}
_ANALYST = ["dashboard.view", "analytics.view", "data.read", "reports.generate"]
_MANAGER = _ANALYST + ["data.write"]
_BADMIN = _MANAGER + ["users.manage", "settings.edit", "audit.view"]
ROLE_PERMS = {
    "super_admin": list(PERMISSIONS), "business_admin": _BADMIN, "manager": _MANAGER,
    "analyst": _ANALYST, "user": ["dashboard.view"],
}
ROLE_DESC = {"super_admin": "Full system access", "business_admin": "Runs a business account",
             "manager": "Manages business data", "analyst": "Reads analytics and builds reports",
             "user": "Dashboard only"}

CATALOG = {
    "Electronics": (["Wireless Earbuds", "Bluetooth Speaker", "Smart Watch", "USB-C Hub", "Webcam HD",
                     "Mechanical Keyboard", "Portable Charger", "Gaming Mouse"], (25, 320)),
    "Home & Kitchen": (["Air Fryer", "Espresso Maker", "Cast Iron Skillet", "Knife Set", "Blender Pro",
                        "Storage Containers", "Electric Kettle", "Dinnerware Set"], (18, 190)),
    "Fitness": (["Yoga Mat", "Adjustable Dumbbells", "Resistance Bands", "Foam Roller", "Jump Rope",
                 "Running Belt", "Kettlebell 12kg", "Fitness Tracker"], (9, 150)),
    "Office": (["Standing Desk Mat", "Ergonomic Chair", "Desk Lamp", "Notebook Pack", "Monitor Stand",
                "Cable Organizer", "Whiteboard", "Label Maker"], (7, 260)),
    "Apparel": (["Merino Hoodie", "Trail Jacket", "Cotton Tee 3-pack", "Running Shorts", "Wool Socks",
                 "Rain Shell", "Denim Jeans", "Canvas Cap"], (12, 140)),
    "Beauty & Care": (["Face Serum", "Beard Kit", "Sunscreen SPF50", "Hair Dryer", "Electric Toothbrush",
                       "Shower Set", "Lip Balm Pack", "Body Lotion"], (5, 110)),
    "Outdoors": (["Camping Tent 2P", "Sleeping Bag", "Headlamp", "Water Bottle 1L", "Trekking Poles",
                  "Dry Bag", "Camp Stove", "Hiking Backpack"], (14, 230)),
    "Toys & Games": (["Board Game Classic", "Puzzle 1000pc", "Building Blocks", "RC Car", "Card Game Set",
                      "Plush Bear", "Art Kit", "Science Lab Kit"], (8, 95)),
}
FIRST = ["Ava", "Liam", "Noah", "Emma", "Olivia", "Mia", "Lucas", "Sofia", "Ethan", "Isla", "Aarav", "Priya",
         "Chen", "Yuki", "Mateo", "Lena", "Omar", "Fatima", "Diego", "Hana", "Nina", "Leo", "Zara", "Arjun"]
LAST = ["Smith", "Johnson", "Garcia", "Muller", "Nguyen", "Patel", "Kim", "Rossi", "Silva", "Khan", "Tanaka",
        "Brown", "Dubois", "Santos", "Ivanov", "Haddad", "Okafor", "Larsen", "Costa", "Sharma"]
EXPENSES = [("Rent", 4200, "Harbor Properties"), ("Salaries", 18500, "Payroll"),
            ("Marketing", 3200, "AdWave"), ("Utilities", 780, "City Power"),
            ("Software", 640, "CloudSuite"), ("Shipping", 2100, "FleetLine"), ("Insurance", 450, "SafeGuard")]


def ensure_roles():
    """Idempotent: create permissions, roles and role->permission links."""
    perms = {}
    for code, desc in PERMISSIONS.items():
        p = Permission.query.filter_by(code=code).first() or Permission(code=code, description=desc)
        db.session.add(p)
        perms[code] = p
    for name, codes in ROLE_PERMS.items():
        r = Role.query.filter_by(name=name).first() or Role(name=name)
        r.description = ROLE_DESC[name]
        r.permissions = [perms[c] for c in codes]
        db.session.add(r)
    db.session.commit()


def _user(email, name, role, business, pw="Demo@1234"):
    u = User.query.filter_by(email=email).first()
    if u:
        return u
    u = User(email=email, full_name=name, role=Role.query.filter_by(name=role).first(),
             business_id=business.id if business else None)
    u.set_password(pw)
    u.settings = UserSetting()
    db.session.add(u)
    return u


def seed_demo(n_customers=120, n_orders=400, months=18, seed=42):
    """Create a demo business with sample data and demo users. Returns the Business."""
    rnd = random.Random(seed)
    ensure_roles()
    biz = Business(name="Northwind Outfitters (Sample Data)", industry="Retail", currency="USD",
                   email="hello@northwind.example", phone="+1 555 0100",
                   address="12 Harbor Street, Portland", is_sample_data=True)
    db.session.add(biz)
    db.session.flush()
    for email, name, role in [("super@insightflow.demo", "Sam Super", "super_admin"),
                              ("admin@insightflow.demo", "Alex Admin", "business_admin"),
                              ("manager@insightflow.demo", "Maya Manager", "manager"),
                              ("analyst@insightflow.demo", "Andre Analyst", "analyst"),
                              ("user@insightflow.demo", "Uma User", "user")]:
        _user(email, name, role, biz)
    today = date.today()
    # categories + products
    products = []
    for cname, (names, (lo, hi)) in CATALOG.items():
        cat = Category(business_id=biz.id, name=cname)
        db.session.add(cat)
        db.session.flush()
        for i, pname in enumerate(names):
            price = round(rnd.uniform(lo, hi) * (0.6 + 0.8 * (i / len(names))), 2)
            low = rnd.random() < 0.12
            p = Product(business_id=biz.id, category_id=cat.id, name=pname, price=price,
                        cost=round(price * rnd.uniform(0.45, 0.72), 2),
                        sku=f"{cname[:3].upper()}-{100 + len(products)}",
                        stock=rnd.randint(0, 8) if low else rnd.randint(30, 260),
                        reorder_level=rnd.randint(10, 25), is_sample=True)
            products.append(p)
            db.session.add(p)
    db.session.flush()
    popularity = [rnd.paretovariate(1.6) for _ in products]
    # customers
    start = today - timedelta(days=months * 30)
    customers = []
    for i in range(n_customers):
        joined = start + timedelta(days=int(rnd.random() ** 1.3 * (months * 30 - 3)))
        name = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
        c = Customer(business_id=biz.id, name=name, region=rnd.choice(REGIONS), is_sample=True,
                     email=f"{name.lower().replace(' ', '.')}{i}@example.com",
                     phone=f"+1 555 {rnd.randint(1000, 9999)}",
                     created_at=datetime.combine(joined, datetime.min.time()))
        customers.append(c)
        db.session.add(c)
    db.session.flush()
    cust_weight = [rnd.paretovariate(1.3) for _ in customers]
    # orders: more recent days weighted higher (growth) + Nov/Dec seasonal bump
    days = list(range(months * 30))
    weights = []
    for d in days:
        day = today - timedelta(days=d)
        growth = 1 + 1.2 * (1 - d / (months * 30))
        season = 1.5 if day.month in (11, 12) else 1.0
        weights.append(growth * season * (0.7 if day.weekday() >= 5 else 1))
    for _ in range(n_orders):
        d = rnd.choices(days, weights)[0]
        odate = datetime.combine(today - timedelta(days=d), datetime.min.time()) + timedelta(
            hours=rnd.randint(8, 21), minutes=rnd.randint(0, 59))
        eligible = [(c, w) for c, w in zip(customers, cust_weight) if c.created_at <= odate]
        if not eligible:
            continue
        cust = rnd.choices([c for c, _ in eligible], [w for _, w in eligible])[0]
        status = rnd.choices(["completed", "cancelled", "refunded", "pending"], [88, 5, 3, 4])[0]
        if status == "pending" and d > 10:
            status = "completed"
        order = Order(business_id=biz.id, customer_id=cust.id, status=status, region=cust.region,
                      order_date=odate, is_sample=True, order_number=f"TMP-{rnd.random()}")
        total = 0.0
        for p in rnd.choices(products, popularity, k=rnd.choice([1, 1, 2, 2, 3, 4])):
            qty = rnd.choice([1, 1, 1, 2, 2, 3])
            order.items.append(OrderItem(product_id=p.id, quantity=qty, unit_price=p.price, unit_cost=p.cost))
            total += p.price * qty
        order.total = round(total, 2)
        db.session.add(order)
        db.session.flush()
        order.order_number = f"ORD-{1000 + order.id}"
        method = rnd.choice(PAYMENT_METHODS)
        if status in ("completed", "refunded"):
            add_transaction(order, "sale", method)
        if status == "refunded":
            add_transaction(order, "refund", method, when=odate + timedelta(days=3))
    # monthly expenses with mild growth
    for m in range(months + 1):
        base = today.replace(day=1) - timedelta(days=30 * m)
        for cat, amount, vendor in EXPENSES:
            d = base.replace(day=min(rnd.randint(1, 27), 28))
            if d > today:
                continue
            db.session.add(Expense(business_id=biz.id, category=cat, vendor=vendor, is_sample=True,
                                   description=f"{cat} - {d.strftime('%B %Y')}", expense_date=d,
                                   amount=round(amount * rnd.uniform(0.92, 1.12) * (1 + 0.01 * (months - m) / 3), 2)))
    db.session.add(Notification(business_id=biz.id, type="system", severity="info",
                                title="Welcome to InsightFlow",
                                message="This workspace is filled with SAMPLE data. Remove it in Settings when you are ready."))
    db.session.commit()
    return biz
