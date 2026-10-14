"""RAFC-V: reliability-aware commitment with explicit event and recovery plans."""
from __future__ import annotations
from typing import Any

from baselines.deterministic_mpc import solve_deterministic_dispatch
from optimization.commitment import calibrate_commitment
from optimization.recovery import plan_recovery


def run_rafc_v(config: dict[str, Any], *, calibration_scenarios: int = 1000,
               calibration_seed: int = 100_000, commitment_step_mw: float = 0.1,
               confidence: float = 0.95) -> dict:
    """Calibrate an event commitment with a recovery feasibility screen, then optimize.

    Calibration evidence is distinct from held-out performance validation. The
    aggregate recovery screen avoids solving an LP for every sampled scenario;
    the chosen nominal event trace must still pass the RecoveryGuard LP.
    """
    calibration=calibrate_commitment(
        config,n_scenarios=calibration_scenarios,seed=calibration_seed,
        step_mw=commitment_step_mw,confidence=confidence,recovery_aware=True)
    target=float(calibration["target_reliability"])
    passing=[row for row in calibration["candidate_evidence"]
             if row["simultaneous_lower_bound"]>=target]
    passing.sort(key=lambda row:row["commitment_mw"],reverse=True)
    chosen=None
    event_result=None
    recovery_result=None
    recovery_failures=[]
    for row in passing:
        candidate=float(row["commitment_mw"])
        dispatch=solve_deterministic_dispatch(config,accepted_commitment_mw=candidate)
        if dispatch["status"]=="solver_error":
            return _solver_error_result(dispatch,calibration,calibration_seed,
                                        "Event optimizer failed; no fallback schedule was used.")
        if dispatch["status"]!="completed":
            recovery_failures.append({"commitment_mw":candidate,"reason":"event dispatch infeasible or solver failed"})
            continue
        recovery=plan_recovery(config,
            backlog_mwh=float(dispatch["telemetry"]["final_workload_backlog_mwh"]),
            current_soc=float(dispatch["telemetry"]["final_battery_soc"]))
        if recovery["status"]=="solver_error":
            return _solver_error_result(dispatch,calibration,calibration_seed,
                                        "Recovery optimizer failed; no fallback schedule was used.",
                                        recovery_result=recovery)
        if recovery["status"]!="completed":
            recovery_failures.append({"commitment_mw":candidate,
                                      "reason":recovery.get("infeasibility_reason",recovery["status"])})
            continue
        chosen=row
        event_result=dispatch
        recovery_result=recovery
        break

    if chosen is None:
        commitment=0.0
        event_result=solve_deterministic_dispatch(config,accepted_commitment_mw=commitment)
        if event_result["status"]=="solver_error":
            return _solver_error_result(event_result,calibration,calibration_seed,
                                        "Event optimizer failed; no fallback schedule was used.")
        recovery_result=plan_recovery(config,
            backlog_mwh=float(event_result["telemetry"].get("final_workload_backlog_mwh",0.0)),
            current_soc=float(event_result["telemetry"].get("final_battery_soc",config["battery"]["initial_soc"])))
        if recovery_result["status"]=="solver_error":
            return _solver_error_result(event_result,calibration,calibration_seed,
                                        "Recovery optimizer failed; no fallback schedule was used.",
                                        recovery_result=recovery_result)
        status="unconfirmed" if not passing else "infeasible"
        evidence=None
    else:
        commitment=float(chosen["commitment_mw"])
        status="confirmed"
        evidence=chosen

    event_result["controller"]="rafc_v"
    event_result["controller_version"]="rafc-v-0.1.0"
    event_result["commitment_basis"]="simultaneous reliability calibration with shared-capacity recovery screen; nominal RecoveryGuard plan verified"
    event_result["reliability"]={
        "status":status,"estimate":evidence["estimated_reliability"] if evidence else None,
        "confidence_lower_bound":evidence["simultaneous_lower_bound"] if evidence else None,
        "confidence_level":calibration["confidence_level"],
        "sample_count":calibration["calibration_sample_count"],
        "target":target,"evidence_split":"calibration",
        "recovery_aware":True}
    event_result["recovery"]=recovery_result
    event_result["rafc_v"]={
        "commitment_status":status,"calibration_method":calibration["method"],
        "calibration_seed_start":calibration_seed,
        "calibration_sample_count":calibration_scenarios,
        "selected_candidate_evidence":evidence,
        "recovery_feasibility_screen":"cumulative workload and AC charging feasibility by deadline under one shared grid headroom budget",
        "recovery_rejections":recovery_failures,
        "limitations":calibration["limitations"]}
    if status!="confirmed":
        event_result["infeasibility_reason"]=("No commitment passed the calibrated reliability and nominal recovery checks." if passing
                                               else "No commitment met the simultaneous reliability lower-bound target with available calibration evidence.")
    return event_result


def _solver_error_result(event_result: dict, calibration: dict, seed: int,
                         reason: str, recovery_result: dict | None = None) -> dict:
    """Preserve solver failure explicitly and avoid reporting a fallback plan."""
    result=dict(event_result)
    result["controller"]="rafc_v"
    result["controller_version"]="rafc-v-0.1.0"
    result["status"]="solver_error"
    result["execution_status"]="solver_error"
    result["accepted_commitment_mw"]=0.0
    result["infeasibility_reason"]=reason
    result["commitment_basis"]="no accepted commitment because an optimization stage failed"
    result["reliability"]={"status":"solver_error","estimate":None,
        "confidence_lower_bound":None,"confidence_level":calibration["confidence_level"],
        "sample_count":calibration["calibration_sample_count"],
        "target":calibration["target_reliability"],"evidence_split":"calibration"}
    if recovery_result is not None:
        result["recovery"]=recovery_result
    result["rafc_v"]={"commitment_status":"solver_error","calibration_seed_start":seed,
        "calibration_sample_count":calibration["calibration_sample_count"],
        "failure_reason":reason,"fallback_schedule_used":False}
    result["violations"]=[*result.get("violations",[]),
        {"type":"solver_error","reason":reason}]
    return result
