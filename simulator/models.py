"""Typed JSON-compatible input and output models for the public engine boundary."""
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

import json

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

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ScenarioConfig":
        """Create and semantically validate the stable public scenario type."""
        if not isinstance(value, dict):
            raise ValueError("scenario must be an object")
        required=("schema_version","scenario_id","random_seed","facility","battery","grid_event","recovery")
        missing=[key for key in required if key not in value]
        if missing:
            raise ValueError(f"scenario missing required fields: {', '.join(missing)}")
        if value["schema_version"]!="1.0.0":
            raise ValueError("unsupported schema_version; expected 1.0.0")
        if not isinstance(value["scenario_id"],str) or not value["scenario_id"].strip():
            raise ValueError("scenario_id must be a non-empty string")
        if isinstance(value["random_seed"],bool) or not isinstance(value["random_seed"],int):
            raise ValueError("random_seed must be an integer")
        for section in ("facility","battery","grid_event","recovery"):
            if not isinstance(value[section],dict):
                raise ValueError(f"{section} must be an object")
        target=float(value.get("reliability_target",
            value["grid_event"].get("target_complete_event_success_probability",0.95)))
        if not 0<=target<=1:
            raise ValueError("reliability_target must be between 0 and 1")
        payload=json.loads(json.dumps(value))
        payload["reliability_target"]=target
        return cls(schema_version=payload["schema_version"],scenario_id=payload["scenario_id"],
            random_seed=payload["random_seed"],facility=payload["facility"],battery=payload["battery"],
            grid_event=payload["grid_event"],recovery=payload["recovery"],
            workloads=payload.get("workloads"),controller=payload.get("controller","rule_based"),
            reliability_target=target)

    def to_dict(self) -> dict[str, Any]:
        payload={"schema_version":self.schema_version,"scenario_id":self.scenario_id,
            "random_seed":self.random_seed,"facility":self.facility,"battery":self.battery,
            "grid_event":self.grid_event,"recovery":self.recovery,
            "controller":self.controller,"reliability_target":self.reliability_target}
        if self.workloads is not None:
            payload["workloads"]=self.workloads
        return payload

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
