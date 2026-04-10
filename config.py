import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')

    uri = os.environ.get("DATABASE_URL")
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    VERCEL = bool(os.environ.get("VERCEL"))
    RENDER = bool(os.environ.get("RENDER"))

    # Vercel / Render: ephemeral filesystem — use /tmp for SQLite fallback and uploads
    if VERCEL or RENDER:
        UPLOAD_FOLDER = "/tmp/uploads"
    else:
        UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")

    if uri:
        SQLALCHEMY_DATABASE_URI = uri
    elif VERCEL:
        SQLALCHEMY_DATABASE_URI = "sqlite:////tmp/job_tracker.db"
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///default.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "yaswanthsreerama@gmail.com")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max

    if VERCEL or RENDER or os.environ.get("FLASK_ENV") == "production":
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = "Lax"
