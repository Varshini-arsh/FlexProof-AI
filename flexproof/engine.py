"""Stable, web-framework-independent entry points for Member 2 and researchers."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import jsonschema

from baselines.deterministic_mpc import solve_deterministic_dispatch
from baselines.risk_aware_mpc import run_risk_aware_mpc
from baselines.rule_based import run_rule_based
from optimization.commitment import calibrate_commitment
from optimization.rafc_v import run_rafc_v
from optimization.recovery import plan_recovery
from simulator.engine import load_config as _load_config
from simulator.engine import run_nominal_event
from simulator.battery import Battery
from simulator.facility import Facility
from simulator.grid import GridEvent
from simulator.models import Result, ScenarioConfig

_ROOT=Path(__file__).resolve().parents[1]
_SCENARIO_SCHEMA=json.loads((_ROOT/"contracts"/"scenario.schema.json").read_text(encoding="utf-8"))
_RESULT_SCHEMA=json.loads((_ROOT/"contracts"/"result.schema.json").read_text(encoding="utf-8"))
_CONTROLLERS={"nominal","nominal_illustration","rule_based","deterministic_mpc","risk_aware_mpc","rafc_v"}


def load_scenario(source: str | Path | dict[str, Any] | ScenarioConfig) -> ScenarioConfig:
    """Load YAML/JSON or a mapping and return the validated public scenario model."""
    if isinstance(source,ScenarioConfig):
        config=source.to_dict()
    else:
        config=_load_config(source)
    model=ScenarioConfig.from_mapping(config)
    normalized=model.to_dict()
    normalized["grid_event"]["target_complete_event_success_probability"]=model.reliability_target
    jsonschema.validate(normalized,_SCENARIO_SCHEMA)
    facility=normalized["facility"]
    Facility(facility["critical_inference_mw"],facility["fixed_auxiliary_mw"],
             facility["deferrable_compute_mw"])
    battery=Battery(**normalized["battery"])
    event=normalized["grid_event"]
    GridEvent(event["start_minute"],event["requested_reduction_mw"],
              event["duration_minutes"],event["interval_minutes"],event["requested_reduction_mw"])
    recovery=normalized["recovery"]
    if recovery["horizon_minutes"]%recovery["interval_minutes"]:
        raise ValueError("recovery horizon must be a multiple of recovery interval")
    if recovery["grid_import_ceiling_mw"]<recovery["nominal_base_demand_mw"]:
        raise ValueError("recovery grid ceiling must be at least the nominal base demand")
    if not battery.min_soc<=recovery["target_soc"]<=battery.max_soc:
        raise ValueError("recovery target SoC must be within battery limits")
    event_end=event["start_minute"]+event["duration_minutes"]
    recovery_end=event_end+recovery["horizon_minutes"]
    for deadline_key in ("target_minute","clear_deferred_work_by_minute"):
        if deadline_key in recovery and not event_end<=recovery[deadline_key]<=recovery_end:
            raise ValueError(f"recovery {deadline_key} must fall between event end and horizon end")
    return ScenarioConfig.from_mapping(normalized)


def evaluate_commitment(config: str | Path | dict[str, Any] | ScenarioConfig, *,
                        n_scenarios: int = 1000, seed: int | None = None,
                        step_mw: float = 0.1, recovery_aware: bool = True,
                        confidence: float = 0.95) -> dict[str, Any]:
    """Calibrate a dependable commitment; output contains calibration evidence only."""
    scenario=load_scenario(config).to_dict()
    return calibrate_commitment(scenario,n_scenarios=n_scenarios,
        seed=scenario["random_seed"] if seed is None else seed,
        step_mw=step_mw,recovery_aware=recovery_aware,confidence=confidence,
        target_reliability=scenario["reliability_target"])


def run_scenario(config: str | Path | dict[str, Any] | ScenarioConfig, *,
                 controller: str | None = None, calibration_scenarios: int = 1000,
                 calibration_seed: int | None = None, commitment_step_mw: float = 0.1) -> Result:
    """Run one reproducible scenario through a selected controller and recovery check.

    Supported controllers are ``nominal``, ``rule_based``, ``deterministic_mpc``,
    ``risk_aware_mpc``, and ``rafc_v``. Results are JSON-compatible and schema 1.0.0.
    """
    try:
        typed=load_scenario(config)
        normalized=typed.to_dict()
    except (ValueError,TypeError,KeyError,jsonschema.ValidationError) as exc:
        scenario_id=(config.get("scenario_id","unknown") if isinstance(config,dict) else "unknown")
        return _invalid_result(str(scenario_id),str(exc))
    selected=controller or typed.controller
    if selected not in _CONTROLLERS:
        return _invalid_result(typed.scenario_id,
            f"unknown controller {selected!r}; choose one of {sorted(_CONTROLLERS)}")
    seed=typed.random_seed if calibration_seed is None else calibration_seed
    if selected in ("nominal","nominal_illustration"):
        result=run_nominal_event(normalized)
    elif selected=="rule_based":
        result=run_rule_based(normalized)
    elif selected=="deterministic_mpc":
        result=solve_deterministic_dispatch(normalized)
    elif selected=="risk_aware_mpc":
        result=run_risk_aware_mpc(normalized,calibration_scenarios=calibration_scenarios,
            calibration_seed=seed,commitment_step_mw=commitment_step_mw)
    else:
        result=run_rafc_v(normalized,calibration_scenarios=calibration_scenarios,
            calibration_seed=seed,commitment_step_mw=commitment_step_mw)
    if "recovery" not in result and result.get("status")!="solver_error":
        telemetry=result.get("telemetry",{})
        if "final_battery_soc" in telemetry and "final_workload_backlog_mwh" in telemetry:
            result["recovery"]=plan_recovery(normalized,
                backlog_mwh=float(telemetry["final_workload_backlog_mwh"]),
                current_soc=float(telemetry["final_battery_soc"]))
    jsonschema.validate(result,_RESULT_SCHEMA)
    return result


def _invalid_result(scenario_id: str,reason: str) -> Result:
    return {"schema_version":"1.0.0","scenario_id":scenario_id,
        "run_id":f"{scenario_id}-invalid-input","controller":"invalid_input",
        "status":"invalid_input","execution_status":"invalid_input",
        "accepted_commitment_mw":None,"infeasibility_reason":reason,
        "reliability":None,"telemetry":{},"violations":[{"type":"invalid_input","reason":reason}],
        "solver_metadata":{"solver":None},"random_seed":0}
