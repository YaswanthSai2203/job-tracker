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
