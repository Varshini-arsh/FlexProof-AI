import os

os.environ.setdefault("FLEXPROOF_DB_PATH", "/tmp/flexproof_runs.sqlite3")

from backend.app.main import app  # noqa: E402,F401
