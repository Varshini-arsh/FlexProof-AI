"""FastAPI application for the FlexProof AI end-to-end prototype."""
from __future__ import annotations

import os
from io import BytesIO

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from jsonschema import ValidationError as JSONSchemaValidationError
from pydantic import ValidationError

from backend.app.models import ScenarioRequest
from backend.app.services.reports import build_run_pdf
from backend.app.services.simulation import build_config, execute_scenario
from backend.app.services.storage import get_run, list_runs


app = FastAPI(title="FlexProof AI API", version="1.0.0",
              description="Research prototype API; outputs are simulated and are not grid certification.")
origins = [item.strip() for item in os.getenv(
    "FLEXPROOF_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"], expose_headers=["Content-Disposition"])


@app.get("/")
def home() -> dict:
    return {"service": "FlexProof AI API", "status": "ok", "api_version": app.version}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "FlexProof AI", "simulation_connected": True,
            "database": "sqlite", "engine": "flexproof.engine"}


@app.get("/api/scenarios/fp001")
def fp001_defaults() -> dict:
    try:
        config = build_config(ScenarioRequest())
    except (ValueError, KeyError, JSONSchemaValidationError) as exc:
        raise HTTPException(status_code=500, detail=f"FP-001 configuration is invalid: {exc}") from exc
    return {"scenario": config, "supported_controllers": [
        "rafc_v", "risk_aware_mpc", "deterministic_mpc", "rule_based", "nominal"],
        "reliability_note": "Controller reliability fields are calibration evidence, not held-out validation."}


@app.post("/api/scenarios/validate")
def validate_scenario(request: ScenarioRequest) -> dict:
    try:
        config = build_config(request)
    except (ValueError, TypeError, KeyError, JSONSchemaValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    warnings = []
    if request.controller == "nominal":
        warnings.append("Nominal controller output does not evaluate the reliability target.")
    warnings.append("Calibration evidence is not independent held-out validation.")
    return {"status": "validated", "scenario": config, "warnings": warnings}


@app.post("/api/scenarios/run")
def run_scenario_endpoint(request: ScenarioRequest) -> dict:
    try:
        result, verification = execute_scenario(request)
    except (ValueError, TypeError, KeyError, JSONSchemaValidationError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Simulation execution failed: {type(exc).__name__}: {exc}") from exc
    return {"status": result["status"],
            "simulation_type": "nominal" if request.controller == "nominal" else "optimized",
            "reliability_certified": False, "verification": verification, "result": result}


@app.get("/api/runs")
def recent_runs(limit: int = Query(default=25, ge=1, le=100)) -> dict:
    return {"runs": list_runs(limit)}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    record = get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@app.get("/api/runs/{run_id}/verification")
def run_verification(run_id: str) -> dict:
    record = get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record["verification"]


@app.get("/api/runs/{run_id}/report.pdf")
def run_report(run_id: str) -> StreamingResponse:
    record = get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    pdf = build_run_pdf(record)
    filename = f"flexproof-{record['scenario_id']}-{run_id[:24]}.pdf"
    return StreamingResponse(BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})
