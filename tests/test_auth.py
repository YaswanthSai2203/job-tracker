def test_signup_login_dashboard(client):
    r = client.post(
        "/auth/signup",
        data={"email": "u@test.local", "password": "abc12345"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    client.post("/auth/logout", follow_redirects=True, data={})

    r = client.post(
        "/auth/login",
        data={"email": "u@test.local", "password": "abc12345"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"Dashboard" in r.data or b"dashboard" in r.data.lower()


def test_weak_password_rejected(client):
    r = client.post(
        "/auth/signup",
        data={"email": "weak@test.local", "password": "short"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"8" in r.data or b"characters" in r.data


def test_csrf_enforced_without_test_config():
    from app import create_app
    from config import Config
    from models.models import db

    class CSRFConfig(Config):
        TESTING = True
        SECRET_KEY = "csrf-test"
        WTF_CSRF_ENABLED = True
        RATELIMIT_ENABLED = False
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_ENGINE_OPTIONS = {}

    app = create_app(CSRFConfig)
    with app.app_context():
        db.create_all()
    c = app.test_client()
    r = c.post("/auth/login", data={"email": "a@b.co", "password": "x"})
    assert r.status_code == 400
