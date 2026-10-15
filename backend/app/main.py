"""HTTP adapter for the nominal FP-001 checkpoint."""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.services.simulation import run_fp001_nominal

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

    @field_validator("duration_minutes")
    @classmethod
    def complete_intervals(cls, value: int) -> int:
        if value % 5:
            raise ValueError("duration must be a multiple of the 5-minute interval")
        return value


@app.get("/")
def home():
    return {"service": "FlexProof AI API", "status": "running", "api_version": app.version}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FlexProof AI", "simulation_connected": True}


@app.post("/api/scenarios/validate")
def validate_scenario(scenario: ScenarioRequest):
    return {"status": "validated", "scenario": scenario.model_dump(),
            "simulation_connected": True,
            "message": "Scenario inputs are valid; physical feasibility has not yet been evaluated."}


@app.post("/api/scenarios/run")
def execute_scenario(scenario: ScenarioRequest):
    try:
        result = run_fp001_nominal(**scenario.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": result["status"], "simulation_type": "nominal",
            "reliability_certified": False, "result": result}
