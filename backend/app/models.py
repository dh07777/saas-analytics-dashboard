"""Relational models for InsightFlow."""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ROLES = ["super_admin", "business_admin", "manager", "analyst", "user"]
ROLE_LABELS = {"super_admin": "Super Admin", "business_admin": "Business Admin",
               "manager": "Manager", "analyst": "Analyst", "user": "Standard User"}
REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East & Africa"]
ORDER_STATUSES = ["completed", "pending", "cancelled", "refunded"]

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.String(200))


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles", lazy="joined")

    @property
    def label(self):
        return ROLE_LABELS.get(self.name, self.name)


class Business(db.Model):
    __tablename__ = "businesses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    industry = db.Column(db.String(100))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(250))
    currency = db.Column(db.String(3), default="USD", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_sample_data = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "industry": self.industry, "email": self.email,
                "phone": self.phone, "address": self.address, "currency": self.currency,
                "is_active": self.is_active, "is_sample_data": self.is_sample_data,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime)
    reset_token_hash = db.Column(db.String(64), index=True)
    reset_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    role = db.relationship("Role")
    business = db.relationship("Business", backref="users")
    settings = db.relationship("UserSetting", uselist=False, backref="user", cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def permission_codes(self):
        return {p.code for p in self.role.permissions}

    def to_dict(self, full=False):
        d = {"id": self.id, "email": self.email, "full_name": self.full_name, "role": self.role.name,
             "role_label": self.role.label, "business_id": self.business_id,
             "business_name": self.business.name if self.business else None,
             "is_active": self.is_active,
             "last_login": self.last_login.isoformat() if self.last_login else None,
             "created_at": self.created_at.isoformat() if self.created_at else None}
        if full:
            d["permissions"] = sorted(self.permission_codes())
            d["business"] = self.business.to_dict() if self.business else None
            d["settings"] = (self.settings or UserSetting()).to_dict()
        return d


class UserSetting(db.Model):
    __tablename__ = "user_settings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    theme = db.Column(db.String(10), default="light")
    date_format = db.Column(db.String(12), default="YYYY-MM-DD")
    notify_revenue = db.Column(db.Boolean, default=True)
    notify_inventory = db.Column(db.Boolean, default=True)
    notify_activity = db.Column(db.Boolean, default=True)
    dashboard_widgets = db.Column(db.String(200), default="trend,categories,topProducts,transactions,activity")

    def to_dict(self):
        widgets = self.dashboard_widgets or "trend,categories,topProducts,transactions,activity"
        return {"theme": self.theme or "light", "date_format": self.date_format or "YYYY-MM-DD",
                "notify_revenue": self.notify_revenue is not False,
                "notify_inventory": self.notify_inventory is not False,
                "notify_activity": self.notify_activity is not False,
                "dashboard_widgets": [w for w in widgets.split(",") if w]}


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    __table_args__ = (db.UniqueConstraint("business_id", "name", name="uq_category_biz_name"),)


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150))
    phone = db.Column(db.String(40))
    region = db.Column(db.String(40))
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    sku = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=10)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    category = db.relationship("Category")
    __table_args__ = (db.UniqueConstraint("business_id", "sku", name="uq_product_biz_sku"),)


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(12), nullable=False, default="completed")
    region = db.Column(db.String(40))
    order_date = db.Column(db.DateTime, nullable=False, default=utcnow)
    total = db.Column(db.Float, nullable=False, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    customer = db.relationship("Customer")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    __table_args__ = (db.Index("ix_orders_biz_date", "business_id", "order_date"),
                      db.Index("ix_orders_biz_status", "business_id", "status"))


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False, default=0)
    product = db.relationship("Product")


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), index=True)
    type = db.Column(db.String(10), nullable=False)  # sale | refund
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(20))
    status = db.Column(db.String(12), default="success")
    reference = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=utcnow)
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    __table_args__ = (db.Index("ix_txn_biz_date", "business_id", "created_at"),)


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(250))
    vendor = db.Column(db.String(120))
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    __table_args__ = (db.Index("ix_expenses_biz_date", "business_id", "expense_date"),)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # null = whole business
    type = db.Column(db.String(20), nullable=False)  # revenue | inventory | activity | system
    severity = db.Column(db.String(10), default="info")
    audience = db.Column(db.String(10), default="all")  # all | admin
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(400))
    dedupe_key = db.Column(db.String(80), index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    row_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity = db.Column(db.String(40))
    entity_id = db.Column(db.String(40))
    details = db.Column(db.String(400))
    ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    user = db.relationship("User")


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class AppConfig(db.Model):
    __tablename__ = "app_config"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(500))
