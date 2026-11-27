import os
import sys
import tempfile

import pytest

# Isolated SQLite database for every test run; must be set before core.database is imported.
_tmpdir = tempfile.mkdtemp()
# TEST_DATABASE_URL lets the same suite run against a throwaway Postgres database.
# Never point it at a real/production database: tables are dropped between tests.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmpdir}/test.db"
os.environ.pop("DEMO_MODE", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def db():
    from core.database import Base, engine, init_db, SessionLocal
    Base.metadata.drop_all(bind=engine)
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
