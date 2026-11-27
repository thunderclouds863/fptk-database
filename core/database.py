# core/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Set when the database URL is missing or malformed. The app shows a configuration
# screen instead of crashing at import time (see app.py). Never contains secrets.
CONFIG_ERROR = None


def _resolve_database_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # Fallback untuk Streamlit Cloud (baca dari st.secrets)
    try:
        import streamlit as st
        url = st.secrets["connections"]["postgresql"]["url"]
        if url:
            return url
    except Exception:
        pass
    from core.demo import is_demo
    if is_demo():
        os.makedirs("data", exist_ok=True)
        return "sqlite:///data/fptk_demo.db"
    return None


DATABASE_URL = _resolve_database_url()

if not DATABASE_URL:
    CONFIG_ERROR = "missing_url"
else:
    # Konversi postgres:// ke postgresql:// (SQLAlchemy butuh ini)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    # Pastikan sslmode=require (Neon butuh SSL)
    if DATABASE_URL.startswith("postgresql") and "sslmode" not in DATABASE_URL:
        separator = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL += f"{separator}sslmode=require"

engine = None
if not CONFIG_ERROR:
    try:
        _connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
    except Exception:  # malformed URL or missing driver
        CONFIG_ERROR = "invalid_url"
        engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Buat semua tabel jika belum ada (dipanggil saat startup)."""
    from core import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


# Additive, idempotent column migrations for tables that already exist
# (create_all never alters existing tables). Never drops or rewrites data.
_ADDITIVE_COLUMNS = {
    "users": {
        "email": "VARCHAR(255)",
        "must_change_password": "BOOLEAN DEFAULT FALSE",
    },
}


def _add_missing_columns():
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def describe_target():
    """Non-secret description of the configured database (dialect, host, db name)."""
    if engine is None:
        return "not configured"
    u = engine.url
    return f"{u.get_backend_name()} host={u.host or '-'} db={u.database or '-'}"


def classify_db_error(exc) -> str:
    """Map a database exception to a short, non-sensitive category."""
    from sqlalchemy.exc import ArgumentError, NoSuchModuleError, OperationalError, InterfaceError
    msg = str(getattr(exc, "orig", exc) or exc).lower()
    if isinstance(exc, (ArgumentError, NoSuchModuleError)):
        return "invalid_url"
    if isinstance(exc, (OperationalError, InterfaceError)):
        if "authentication" in msg or "access denied" in msg:
            return "auth_failed"
        if "does not exist" in msg and "database" in msg:
            return "db_missing"
        return "unreachable"
    return "init_failed"  # e.g. ProgrammingError while creating the schema


def check_connection():
    """Raise if the database cannot be reached."""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def get_db():
    """Generator session untuk Streamlit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()