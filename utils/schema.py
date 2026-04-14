"""Add missing columns and tables on existing databases (SQLite / Postgres)."""

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from models.models import db


def _exec(stmt):
    try:
        db.session.execute(text(stmt))
        db.session.commit()
    except (OperationalError, ProgrammingError):
        db.session.rollback()


def ensure_schema():
    insp = inspect(db.engine)
    dialect = db.engine.dialect.name
    tables = insp.get_table_names()

    if "job" in tables:
        cols = {c["name"] for c in insp.get_columns("job")}
        if "updated_at" not in cols:
            if dialect == "sqlite":
                _exec(
                    "ALTER TABLE job ADD COLUMN updated_at DATETIME "
                    "DEFAULT CURRENT_TIMESTAMP"
                )
                _exec("UPDATE job SET updated_at = timestamp WHERE updated_at IS NULL")
            else:
                _exec(
                    "ALTER TABLE job ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE "
                    "DEFAULT NOW()"
                )
                _exec("UPDATE job SET updated_at = COALESCE(updated_at, timestamp)")
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("job")}
        if "status_changed_at" not in cols:
            if dialect == "sqlite":
                _exec(
                    "ALTER TABLE job ADD COLUMN status_changed_at DATETIME "
                    "DEFAULT CURRENT_TIMESTAMP"
                )
                _exec(
                    "UPDATE job SET status_changed_at = COALESCE(updated_at, timestamp) "
                    "WHERE status_changed_at IS NULL"
                )
            else:
                _exec(
                    "ALTER TABLE job ADD COLUMN status_changed_at TIMESTAMP WITH TIME ZONE "
                    "DEFAULT NOW()"
                )
                _exec(
                    "UPDATE job SET status_changed_at = COALESCE(updated_at, timestamp) "
                    "WHERE status_changed_at IS NULL"
                )
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("job")}
        if "tags" not in cols:
            if dialect == "sqlite":
                _exec("ALTER TABLE job ADD COLUMN tags VARCHAR(200) DEFAULT ''")
            else:
                _exec("ALTER TABLE job ADD COLUMN tags VARCHAR(200) DEFAULT ''")
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("job")}
        if "archived" not in cols:
            if dialect == "sqlite":
                _exec("ALTER TABLE job ADD COLUMN archived BOOLEAN DEFAULT 0 NOT NULL")
            else:
                _exec(
                    "ALTER TABLE job ADD COLUMN archived BOOLEAN DEFAULT false NOT NULL"
                )
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("job")}
        if "snoozed_until" not in cols:
            if dialect == "sqlite":
                _exec("ALTER TABLE job ADD COLUMN snoozed_until DATE")
            else:
                _exec("ALTER TABLE job ADD COLUMN snoozed_until DATE")

    insp = inspect(db.engine)
    tables = insp.get_table_names()
    if "public_job" in tables:
        cols = {c["name"] for c in insp.get_columns("public_job")}
        if "featured" not in cols:
            if dialect == "sqlite":
                _exec("ALTER TABLE public_job ADD COLUMN featured BOOLEAN DEFAULT 0")
                _exec("UPDATE public_job SET featured = 0 WHERE featured IS NULL")
            else:
                _exec(
                    "ALTER TABLE public_job ADD COLUMN featured BOOLEAN DEFAULT false NOT NULL"
                )

    insp = inspect(db.engine)
    tables = insp.get_table_names()
    if "user" in tables:
        cols = {c["name"] for c in insp.get_columns("user")}
        if "email_verified" not in cols:
            if dialect == "sqlite":
                _exec(
                    "ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 1 NOT NULL"
                )
            else:
                _exec(
                    'ALTER TABLE "user" ADD COLUMN email_verified BOOLEAN DEFAULT true NOT NULL'
                )
            if dialect == "sqlite":
                _exec("UPDATE user SET email_verified = 1 WHERE email_verified IS NULL")
            else:
                _exec(
                    'UPDATE "user" SET email_verified = true WHERE email_verified IS NULL'
                )

    insp = inspect(db.engine)
    tables = insp.get_table_names()
    if "job_status_history" not in tables:
        if dialect == "sqlite":
            _exec(
                """
                CREATE TABLE job_status_history (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    old_status VARCHAR(50),
                    new_status VARCHAR(50) NOT NULL,
                    changed_at DATETIME NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES job (id)
                )
                """
            )
        else:
            _exec(
                """
                CREATE TABLE job_status_history (
                    id SERIAL PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES job(id),
                    old_status VARCHAR(50),
                    new_status VARCHAR(50) NOT NULL,
                    changed_at TIMESTAMP WITH TIME ZONE NOT NULL
                )
                """
            )

    insp = inspect(db.engine)
    tables = insp.get_table_names()
    if "interview" not in tables:
        if dialect == "sqlite":
            _exec(
                """
                CREATE TABLE interview (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    interview_at DATETIME NOT NULL,
                    kind VARCHAR(40) NOT NULL DEFAULT 'phone',
                    notes TEXT,
                    FOREIGN KEY(job_id) REFERENCES job (id)
                )
                """
            )
        else:
            _exec(
                """
                CREATE TABLE interview (
                    id SERIAL PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES job(id),
                    interview_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    kind VARCHAR(40) NOT NULL DEFAULT 'phone',
                    notes TEXT
                )
                """
            )
