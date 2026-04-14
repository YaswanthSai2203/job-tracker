import os
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from config import Config
from models.models import Job, User, db
from utils.schema import ensure_schema


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.db_fd)
        cls.uploads = tempfile.mkdtemp()

        class TConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            RATELIMIT_ENABLED = False
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{cls.db_path}"
            SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}
            UPLOAD_FOLDER = cls.uploads
            MAIL_SERVER = None

        cls.app = create_app(TConfig)
        with cls.app.app_context():
            db.create_all()
            ensure_schema()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.drop_all()
        try:
            os.unlink(cls.db_path)
        except OSError:
            pass

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.query(Job).delete()
            db.session.query(User).delete()
            db.session.commit()

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_resume_download_owned_only(self):
        with self.app.app_context():
            u = User(email="own@test.local", password=generate_password_hash("pw"))
            db.session.add(u)
            db.session.commit()
            j = Job(
                company="Co",
                link="https://example.com",
                resume_filename="co_resume.pdf",
                user_id=u.id,
            )
            db.session.add(j)
            db.session.commit()
            path = os.path.join(self.app.config["UPLOAD_FOLDER"], "co_resume.pdf")
            with open(path, "wb") as f:
                f.write(b"%PDF-1.4\n")
        self.client.post(
            "/auth/login",
            data={"email": "own@test.local", "password": "pw"},
            follow_redirects=True,
        )
        r = self.client.get("/resume/co_resume.pdf/download")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/resume/other.pdf/download")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
