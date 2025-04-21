import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')

    uri = os.environ.get("DATABASE_URL")
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = uri or 'sqlite:///default.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_EMAIL = "yaswanthsreerama@gmail.com"

    if os.environ.get("RENDER"):
        UPLOAD_FOLDER = '/tmp/uploads'
    else:
        UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
