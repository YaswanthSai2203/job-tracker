import os

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from auth.routes import auth_bp
from config import Config
from jobs.routes import jobs_bp
from extensions import csrf, limiter, migrate
from models.models import User, db
from utils.logging_setup import init_app_logging
from utils.schema import ensure_schema


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    init_app_logging(app)

    if app.config.get("VERCEL"):
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
        )

    upload_folder = app.config["UPLOAD_FOLDER"]
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(jobs_bp)

    with app.app_context():
        try:
            from flask_migrate import stamp as _db_stamp
            from flask_migrate import upgrade as _db_upgrade

            _db_upgrade()
        except Exception as exc:
            app.logger.warning("Database migration issue: %s", exc)
            err = str(exc).lower()
            if "already exists" in err or "duplicate" in err:
                try:
                    _db_stamp(revision="head")
                except Exception as stamp_exc:
                    app.logger.warning("Could not stamp alembic version: %s", stamp_exc)
            db.create_all()
        ensure_schema()

    _auth_ok_unverified = frozenset(
        {
            "auth.login",
            "auth.signup",
            "auth.logout",
            "auth.reset_request",
            "auth.reset_token",
            "auth.verify_email",
            "auth.resend_verification",
            "auth.verification_required",
        }
    )

    @app.before_request
    def _require_verified_email():
        if not current_user.is_authenticated:
            return None
        if getattr(current_user, "email_verified", True):
            return None
        ep = request.endpoint
        if ep in _auth_ok_unverified or ep == "static":
            return None
        if ep in ("health", "privacy", "terms"):
            return None
        return redirect(
            url_for("auth.verification_required", email=current_user.email)
        )

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/")
    def home():
        if current_user.is_authenticated:
            if not getattr(current_user, "email_verified", True):
                return redirect(url_for("auth.verification_required"))
            return redirect(url_for("jobs.dashboard"))
        return render_template("landing.html")

    @app.route("/privacy")
    def privacy():
        return render_template("legal/privacy.html")

    @app.route("/terms")
    def terms():
        return render_template("legal/terms.html")

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(429)
    def too_many(_e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    @app.after_request
    def security_headers(response):
        if app.config.get("VERCEL") or app.config.get("RENDER") or os.environ.get(
            "FLASK_ENV"
        ) == "production":
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            response.headers.setdefault(
                "Referrer-Policy",
                "strict-origin-when-cross-origin",
            )
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=()",
            )
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5005)
