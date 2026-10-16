"""Give API tests a migrated, disposable SQLite database."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def pytest_sessionstart(session):
    database_path = Path(".cache/test-flexproof.sqlite3")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    command.upgrade(Config("alembic.ini"), "head")
