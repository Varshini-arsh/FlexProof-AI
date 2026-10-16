"""Persistence boundary shared by the API and the PostgreSQL deployment."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db_models import ReportMetadata, ScenarioConfig, SimulationRun, TelemetryInterval, VerificationRecord
from backend.app.services.verification import canonical_hash, evidence_hash


def database_url() -> str:
    return __import__("os").getenv("DATABASE_URL", "sqlite:///./.cache/flexproof.sqlite3")


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite:"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url != "sqlite:///:memory:":
            db_file = url.removeprefix("sqlite:///")
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, **kwargs)


@lru_cache(maxsize=4)
def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False)


def database_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def persist_run(config: dict, result: dict, verification: dict, request: dict) -> None:
    run_id = result.get("run_id")
    if not run_id:
        raise ValueError("Cannot persist a result without a run_id")
    cfg_hash = canonical_hash(config)
    result_copy = deepcopy(result)
    telemetry = result_copy.setdefault("telemetry", {})
    event_rows = telemetry.pop("event_time_series", [])
    recovery = result_copy.get("recovery") or {}
    recovery_telemetry = recovery.get("telemetry") or {}
    recovery_rows = recovery_telemetry.pop("recovery_time_series", [])
    hashes = verification.get("metrics", {})
    factory = get_session_factory()
    with factory.begin() as session:
        existing = session.get(SimulationRun, run_id)
        if existing:
            if existing.scenario_hash != cfg_hash:
                raise ValueError("run_id already belongs to different scenario evidence")
            return
        if session.get(ScenarioConfig, cfg_hash) is None:
            session.add(ScenarioConfig(scenario_hash=cfg_hash, scenario_id=config["scenario_id"],
                schema_version=config["schema_version"], payload=deepcopy(config)))
        run = SimulationRun(run_id=run_id, scenario_hash=cfg_hash, controller=result["controller"],
            controller_version=result["controller_version"], status=result["status"],
            execution_status=result["execution_status"], request_payload=deepcopy(request),
            result_metadata=result_copy)
        session.add(run)
        for phase, rows in (("event", event_rows), ("recovery", recovery_rows)):
            session.add_all(TelemetryInterval(run_id=run_id, phase=phase, step=int(row.get("step", index)), payload=row)
                            for index, row in enumerate(rows))
        session.add(VerificationRecord(run_id=run_id, input_hash=hashes.get("input_hash", cfg_hash),
            evidence_hash=hashes.get("evidence_hash", evidence_hash(config, result)), payload=deepcopy(verification)))


def record_report(run_id: str | None, format: str, filename: str, digest: str) -> bool:
    if not run_id:
        return False
    factory = get_session_factory()
    with factory.begin() as session:
        if session.get(SimulationRun, run_id) is None:
            return False
        report_id = f"{run_id}:{format}:{digest[:12]}"
        if session.get(ReportMetadata, report_id) is None:
            session.add(ReportMetadata(report_id=report_id, run_id=run_id, format=format,
                                       filename=filename, sha256=digest))
    return True


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    factory = get_session_factory()
    with factory() as session:
        rows = session.execute(select(SimulationRun, ScenarioConfig.scenario_id)
            .join(ScenarioConfig, SimulationRun.scenario_hash == ScenarioConfig.scenario_hash)
            .order_by(SimulationRun.created_at.desc()).limit(limit)).all()
        return [{"run_id": run.run_id, "scenario_id": scenario_id, "controller": run.controller,
                 "controller_version": run.controller_version, "status": run.status,
                 "execution_status": run.execution_status,
                 "created_at": run.created_at.isoformat() if run.created_at else None}
                for run, scenario_id in rows]


def load_run(run_id: str) -> dict[str, Any] | None:
    factory = get_session_factory()
    with factory() as session:
        run = session.get(SimulationRun, run_id)
        if run is None:
            return None
        config = session.get(ScenarioConfig, run.scenario_hash)
        check = session.get(VerificationRecord, run_id)
        intervals = session.execute(select(TelemetryInterval).where(TelemetryInterval.run_id == run_id)
                                    .order_by(TelemetryInterval.phase, TelemetryInterval.step)).scalars().all()
        result = deepcopy(run.result_metadata)
        result.setdefault("telemetry", {})["event_time_series"] = [row.payload for row in intervals if row.phase == "event"]
        if result.get("recovery") is not None:
            result["recovery"].setdefault("telemetry", {})["recovery_time_series"] = [row.payload for row in intervals if row.phase == "recovery"]
        return {"request": deepcopy(run.request_payload), "scenario": deepcopy(config.payload),
                "result": result, "independent_verification": deepcopy(check.payload) if check else None}
