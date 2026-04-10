import os

def _normalize_database_url(raw: str, *, require_ssl: bool) -> str:
    uri = raw.strip()
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    if require_ssl and uri.startswith("postgresql") and "sslmode=" not in uri and "ssl=" not in uri:
        sep = "&" if "?" in uri else "?"
        uri = f"{uri}{sep}sslmode=require"
    return uri

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')

    _raw_db = os.environ.get("DATABASE_URL", "").strip()

    VERCEL = bool(os.environ.get("VERCEL"))
    RENDER = bool(os.environ.get("RENDER"))

    # Vercel / Render: ephemeral filesystem — use /tmp for SQLite fallback and uploads
    if VERCEL or RENDER:
        UPLOAD_FOLDER = "/tmp/uploads"
    else:
        UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")

    if _raw_db:
        SQLALCHEMY_DATABASE_URI = _normalize_database_url(
            _raw_db, require_ssl=VERCEL or RENDER
        )
    elif VERCEL:
        SQLALCHEMY_DATABASE_URI = "sqlite:////tmp/job_tracker.db"
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///default.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SQLite + Flask threads (e.g. Vercel / dev server): avoid thread errors
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"connect_args": {"check_same_thread": False}}
        if SQLALCHEMY_DATABASE_URI.startswith("sqlite")
        else {}
    )

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "yaswanthsreerama@gmail.com")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max

    if VERCEL or RENDER or os.environ.get("FLASK_ENV") == "production":
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = "Lax"

    # Flask-WTF CSRF (enabled unless explicitly disabled)
    WTF_CSRF_ENABLED = os.environ.get("WTF_CSRF_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
    )
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", "43200"))

    # Optional SMTP (stdlib smtplib only — set MAIL_SERVER to enable)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "").strip() or None
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "").strip() or None
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "").strip() or None
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "").strip() or None

    # Rate limits (Flask-Limiter; in-memory storage unless you set RATELIMIT_STORAGE_URI)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
    )
