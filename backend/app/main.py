
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="FlexProof AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ScenarioRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    requested_reduction_mw: float = Field(gt=0, le=20)
    duration_minutes: int = Field(ge=15, le=60)
    reliability_target: float = Field(gt=0, le=1)
    battery_soc_percent: float = Field(ge=20, le=100)


@app.get("/")
def home():
    return {
        "message": "Welcome to FlexProof AI Backend",
        "status": "running"
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "FlexProof AI",
        "simulation_connected": False
    }


@app.post("/api/scenarios/validate")
def validate_scenario(scenario: ScenarioRequest):
    return {
        "status": "validated",
        "scenario": scenario.model_dump(),
        "simulation_connected": False,
        "message": (
            "Scenario input validated successfully. "
            "Optimization has not yet been executed."
        )
    }
