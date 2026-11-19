import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from config import BASE_DIR, Config
from .extensions import cors, db, jwt, migrate
from .utils import ApiError, check_global_rate_limit, error_response, reset_rate_limits


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config["APP_ENV"] == "production" and (
            "change-me" in app.config["SECRET_KEY"] or "change-me" in app.config["JWT_SECRET_KEY"]):
        raise RuntimeError("Set strong SECRET_KEY and JWT_SECRET_KEY in the environment for production.")

    _setup_logging(app)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
                  supports_credentials=False, allow_headers=["Content-Type", "Authorization"])
    reset_rate_limits()

    from . import models  # noqa: F401  (register tables with SQLAlchemy)
    from .routes import admin, analytics, auth, data, misc, reports, users
    for mod, prefix in [(auth, "/api/auth"), (analytics, "/api/analytics"), (data, "/api"),
                        (users, "/api"), (misc, "/api"), (reports, "/api"), (admin, "/api/admin")]:
        app.register_blueprint(mod.bp, url_prefix=prefix)

    @app.before_request
    def _limit():
        check_global_rate_limit()

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    _register_handlers(app)
    _register_cli(app)
    if not app.config.get("TESTING"):
        _bootstrap(app)
    return app


def _bootstrap(app):
    """Make a fresh checkout work: create tables and roles, and (development only) load demo data
    when the database has no users yet. Set AUTO_SEED=false to turn the demo data off."""
    log = logging.getLogger("insightflow")
    with app.app_context():
        try:
            from .models import User
            from .seed import ensure_roles, seed_demo
            db.create_all()
            ensure_roles()
            if (app.config["APP_ENV"] == "development" and os.getenv("AUTO_SEED", "true").lower() != "false"
                    and User.query.count() == 0):
                log.info("Empty database: loading sample data (this takes a few seconds)...")
                seed_demo()
                log.info("Sample data ready. Sign in as admin@insightflow.demo / Demo@1234")
        except Exception:
            db.session.rollback()
            log.exception("Database bootstrap failed")


def _setup_logging(app):
    level = getattr(logging, app.config["LOG_LEVEL"].upper(), logging.INFO)
    log = logging.getLogger("insightflow")
    log.setLevel(level)
    if log.handlers:
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(console)
    if not app.config.get("TESTING"):
        os.makedirs(BASE_DIR / "logs", exist_ok=True)
        fh = RotatingFileHandler(BASE_DIR / "logs" / "insightflow.log", maxBytes=1_000_000, backupCount=3)
        fh.setFormatter(fmt)
        log.addHandler(fh)


def _register_handlers(app):
    from .models import TokenBlocklist
    log = logging.getLogger("insightflow")

    @jwt.token_in_blocklist_loader
    def _blocked(_header, payload):
        return TokenBlocklist.query.filter_by(jti=payload["jti"]).first() is not None

    @jwt.expired_token_loader
    def _expired(_h, _p):
        return jsonify({"error": "Your session has expired. Please sign in again.", "code": "token_expired"}), 401

    @jwt.invalid_token_loader
    def _invalid(_reason):
        return jsonify({"error": "Invalid session. Please sign in again.", "code": "token_invalid"}), 401

    @jwt.unauthorized_loader
    def _missing(_reason):
        return jsonify({"error": "Authentication required.", "code": "token_missing"}), 401

    @jwt.revoked_token_loader
    def _revoked(_h, _p):
        return jsonify({"error": "You have been signed out.", "code": "token_revoked"}), 401

    @app.errorhandler(ApiError)
    def _api_error(e):
        return error_response(e)

    @app.errorhandler(HTTPException)
    def _http_error(e):
        return jsonify({"error": e.description or e.name}), e.code

    @app.errorhandler(Exception)
    def _unhandled(e):
        db.session.rollback()
        log.exception("Unhandled error")
        return jsonify({"error": "Something went wrong on our side. Please try again."}), 500


def _register_cli(app):
    import click
    from .models import Business, Role, User, UserSetting
    from .seed import ensure_roles, seed_demo

    @app.cli.command("init-db")
    def init_db():
        """Create tables and the roles/permissions."""
        db.create_all()
        ensure_roles()
        click.echo("Database ready.")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Drop all tables first.")
    @click.option("--customers", default=120, show_default=True)
    @click.option("--orders", default=400, show_default=True)
    def seed(reset, customers, orders):
        """Load SAMPLE business data and demo users."""
        if reset:
            db.drop_all()
        db.create_all()
        ensure_roles()
        if User.query.filter_by(email="admin@insightflow.demo").first():
            click.echo("Sample data already exists. Use --reset to rebuild.")
            return
        seed_demo(customers, orders)
        click.echo("Sample data created. Demo logins (password Demo@1234):")
        for e in ("super", "admin", "manager", "analyst", "user"):
            click.echo(f"  {e}@insightflow.demo")

    @app.cli.command("create-superadmin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option()
    def create_superadmin(email, name, password):
        """Create a real super admin without sample data."""
        db.create_all()
        ensure_roles()
        biz = Business.query.first() or Business(name="My Company")
        db.session.add(biz)
        db.session.flush()
        u = User(email=email.lower(), full_name=name, business_id=biz.id,
                 role=Role.query.filter_by(name="super_admin").first())
        u.set_password(password)
        u.settings = UserSetting()
        db.session.add(u)
        db.session.commit()
        click.echo("Super admin created.")
