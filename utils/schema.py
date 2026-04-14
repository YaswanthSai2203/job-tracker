"""Add missing columns on existing databases (SQLite / Postgres)."""

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
    tables = insp.get_table_names()
    dialect = db.engine.dialect.name

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
