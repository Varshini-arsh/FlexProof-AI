"""Typed HTTP request models for the FlexProof prototype API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Controller = Literal["rafc_v", "risk_aware_mpc", "deterministic_mpc", "rule_based", "nominal"]


class ScenarioRequest(BaseModel):
    scenario_id: str = Field(default="FP-001", min_length=1, max_length=80,
                             pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    requested_reduction_mw: float = Field(default=5.0, gt=0, le=20)
    duration_minutes: int = Field(default=60, ge=5, le=60)
    reliability_target: float = Field(default=0.95, gt=0, lt=1)
    battery_soc_percent: float = Field(default=35.0, ge=20, le=100)
    random_seed: int = Field(default=20261014, ge=0)
    controller: Controller = "rafc_v"
    calibration_scenarios: int = Field(default=1000, ge=100, le=5000)
    commitment_step_mw: float = Field(default=0.1, gt=0, le=1)

    @field_validator("duration_minutes")
    @classmethod
    def duration_matches_fp001_interval(cls, value: int) -> int:
        if value % 5:
            raise ValueError("duration must be a multiple of the FP-001 5-minute interval")
        return value


class ScenarioValidationResponse(BaseModel):
    valid: bool
    scenario: dict
    warnings: list[str]

\n