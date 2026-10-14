"""Typed JSON-compatible input and output models for the public engine boundary."""
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    schema_version: str
    scenario_id: str
    random_seed: int
    facility: dict[str, Any]
    battery: dict[str, Any]
    grid_event: dict[str, Any]
    recovery: dict[str, Any]
    workloads: dict[str, Any] | None = None
    controller: str = "rule_based"
    reliability_target: float = 0.95

class Result(TypedDict, total=False):
    schema_version: str
    scenario_id: str
    run_id: str
    controller: str
    status: Literal["completed", "infeasible", "solver_error", "invalid_input"]
    accepted_commitment_mw: float | None
    infeasibility_reason: str | None
    reliability: dict[str, Any] | None
    telemetry: dict[str, Any]
    violations: list[dict[str, Any]]
    solver_metadata: dict[str, Any]
    random_seed: int
