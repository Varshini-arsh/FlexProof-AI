"""Give API tests a migrated, disposable SQLite database."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def pytest_sessionstart(session):
    # Keep local tests isolated by default. CI can opt into its disposable
    # PostgreSQL service using a dedicated test-only URL variable.
    test_database_url = os.environ.get("FLEXPROOF_TEST_DATABASE_URL")
    if test_database_url:
        if not test_database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("FLEXPROOF_TEST_DATABASE_URL must target a disposable PostgreSQL test database")
        os.environ["DATABASE_URL"] = test_database_url
    else:
        database_path = Path(".cache/test-flexproof.sqlite3")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    command.upgrade(Config("alembic.ini"), "head")
