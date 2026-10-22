"""Small SQLite persistence layer for reproducible prototype runs."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def database_path() -> Path:
    configured = os.getenv("FLEXPROOF_DB_PATH")
    return Path(configured) if configured else ROOT / "data" / "flexproof_runs.sqlite3"


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS simulation_runs (
            run_id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            controller TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            request_json TEXT NOT NULL,
            config_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            verification_json TEXT NOT NULL
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_created ON simulation_runs(created_at DESC)")
    return connection


def save_run(request: dict[str, Any], config: dict[str, Any], result: dict[str, Any],
             verification: dict[str, Any]) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute("""
            INSERT INTO simulation_runs
            (run_id, scenario_id, controller, status, created_at, request_json, config_json, result_json, verification_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (result["run_id"], result["scenario_id"], result["controller"], result["status"], created_at,
              json.dumps(request, allow_nan=False), json.dumps(config, allow_nan=False),
              json.dumps(result, allow_nan=False), json.dumps(verification, allow_nan=False)))


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("""
            SELECT run_id, scenario_id, controller, status, created_at,
                   json_extract(result_json, '$.accepted_commitment_mw') AS accepted_commitment_mw,
                   json_extract(verification_json, '$.status') AS verification_status
            FROM simulation_runs ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("""
            SELECT run_id, scenario_id, controller, status, created_at,
                   request_json, config_json, result_json, verification_json
            FROM simulation_runs WHERE run_id = ?
        """, (run_id,)).fetchone()
    if row is None:
        return None
    value = dict(row)
    for field in ("request_json", "config_json", "result_json", "verification_json"):
        value[field.removesuffix("_json")] = json.loads(value.pop(field))
    return value
