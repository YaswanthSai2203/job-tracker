import os
import tempfile

import pytest

from app import create_app
from config import Config
from models.models import db


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    VERCEL = False
    RENDER = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False  # disable rate limits in tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    MAIL_SERVER = None


@pytest.fixture
def app():
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("VERCEL", None)
    uploads = tempfile.mkdtemp()
    TestConfig.UPLOAD_FOLDER = uploads
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
    os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def client(app):
    return app.test_client()
