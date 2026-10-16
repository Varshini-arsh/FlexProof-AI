"""HTTP adapter for the nominal FP-001 checkpoint."""
import os
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.services.simulation import assess_commitment, build_config, execute_simulation
from backend.app.services.verification import verify_result
from backend.app.services.reports import build_evidence_bundle, telemetry_csv, verification_pdf
from backend.app.services.benchmarks import load_closed_loop_benchmark
from backend.app.database import database_ready, list_runs, load_run, persist_run, record_report
from sqlalchemy.exc import SQLAlchemyError
import hashlib
import json

app = FastAPI(title="FlexProof AI API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FLEXPROOF_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    scenario_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    requested_reduction_mw: float = Field(gt=0, le=20)
    duration_minutes: int = Field(ge=15, le=60)
    reliability_target: float = Field(gt=0, lt=1)
    battery_soc_percent: float = Field(ge=20, le=100)
    random_seed: int = Field(default=20261014, ge=0)
    controller: Literal["nominal", "rule_based", "deterministic_mpc", "risk_aware_mpc", "rafc_v"] = "nominal"
    calibration_scenarios: int = Field(default=1000, ge=100, le=5000)
    commitment_step_mw: float = Field(default=0.1, ge=0.05, le=1)
    recovery_grid_ceiling_mw: float = Field(default=20, ge=17, le=30)

    @field_validator("duration_minutes")
    @classmethod
    def complete_intervals(cls, value: int) -> int:
        if value % 5:
            raise ValueError("duration must be a multiple of the 5-minute interval")
        return value


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    scenario: dict
    result: dict
    expected_input_hash: str | None = Field(default=None, min_length=64, max_length=64)
    expected_evidence_hash: str | None = Field(default=None, min_length=64, max_length=64)


@app.get("/")
def home():
    return {"service": "FlexProof AI API", "status": "running", "api_version": app.version}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FlexProof AI", "simulation_connected": True,
            "database_connected": database_ready()}


@app.get("/api/benchmarks/closed-loop")
def closed_loop_benchmark():
    return load_closed_loop_benchmark()


@app.post("/api/scenarios/validate")
def validate_scenario(scenario: ScenarioRequest):
    try:
        normalized = build_config(scenario.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "validated", "scenario": scenario.model_dump(),
            "normalized_scenario": normalized,
            "simulation_connected": True,
            "message": "Scenario inputs are valid; physical feasibility has not yet been evaluated."}


@app.post("/api/scenarios/run")
def execute_scenario(scenario: ScenarioRequest):
    try:
        config, result = execute_simulation(scenario.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    engine_run_id = result["run_id"]
    result["run_id"] = f"{scenario.scenario_id}-{uuid4().hex[:12]}"
    verification = verify_result(config, result)
    try:
        persist_run(config, result, verification, scenario.model_dump())
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Run completed but persistence failed; inspect database connectivity and migrations.") from exc
    return {"status": result["status"],
            "simulation_type": "nominal" if scenario.controller == "nominal" else "optimized",
            "reliability_certified": False, "scenario": config, "result": result,
            "run_id": result["run_id"], "engine_run_id": engine_run_id,
            "independent_verification": verification, "storage_status": "persisted"}


@app.post("/api/commitments/evaluate")
def evaluate_scenario_commitment(scenario: ScenarioRequest):
    try:
        return assess_commitment(scenario.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/evidence/verify")
def verify_evidence(evidence: EvidenceRequest):
    return verify_result(evidence.scenario, evidence.result,
                         expected_input_hash=evidence.expected_input_hash,
                         expected_evidence_hash=evidence.expected_evidence_hash)


@app.post("/api/evidence/export")
def export_evidence(evidence: EvidenceRequest):
    bundle = build_evidence_bundle(evidence.scenario, evidence.result)
    filename = f"{evidence.result.get('run_id', 'flexproof-run')}-evidence.json"
    bundle["report_metadata_recorded"] = record_report(evidence.result.get("run_id"), "json", filename,
        hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest())
    return bundle


@app.post("/api/evidence/telemetry.csv")
def export_telemetry_csv(evidence: EvidenceRequest):
    filename = f"{evidence.result.get('run_id', 'flexproof-run')}-telemetry.csv"
    content = telemetry_csv(evidence.scenario, evidence.result)
    record_report(evidence.result.get("run_id"), "csv", filename, hashlib.sha256(content.encode("utf-8")).hexdigest())
    return Response(content, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/evidence/report.pdf")
def export_verification_report(evidence: EvidenceRequest):
    bundle = build_evidence_bundle(evidence.scenario, evidence.result)
    filename = f"{evidence.result.get('run_id', 'flexproof-run')}-verification.pdf"
    content = verification_pdf(bundle)
    record_report(evidence.result.get("run_id"), "pdf", filename, hashlib.sha256(content).hexdigest())
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/runs")
def recent_runs(limit: int = Query(default=50, ge=1, le=200)):
    try:
        return {"runs": list_runs(limit)}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Run history database is unavailable or migrations are pending.") from exc


@app.get("/api/runs/{run_id}")
def recorded_run(run_id: str):
    try:
        record = load_run(run_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Run database is unavailable or migrations are pending.") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record
