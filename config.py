import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')

    # Normalize DATABASE_URL for PostgreSQL
    uri = os.environ.get("DATABASE_URL")
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = uri or 'sqlite:///default.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload configuration
    if os.environ.get("RENDER"):
        # Render allows writing only to /tmp
        UPLOAD_FOLDER = '/tmp/uploads'
    else:
        UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limit uploads to 16MB
