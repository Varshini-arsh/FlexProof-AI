"""Common-random-number held-out comparison of the four FP-001 controllers."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from statistics import NormalDist
from time import perf_counter
from typing import Any

from baselines.deterministic_mpc import solve_deterministic_dispatch
from baselines.risk_aware_mpc import run_risk_aware_mpc
from baselines.rule_based import run_rule_based
from evaluation.metrics import wilson_interval
from evaluation.statistical_tests import exact_mcnemar
from optimization.commitment import _scenario_passes
from optimization.rafc_v import run_rafc_v
from optimization.recovery import plan_recovery
from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario


def _run_controller(name: str, config: dict[str, Any], *, calibration_scenarios: int,
                    calibration_seed: int, commitment_step_mw: float) -> dict:
    if name=="rule_based":
        result=run_rule_based(config)
    elif name=="deterministic_mpc":
        result=solve_deterministic_dispatch(config)
    elif name=="risk_aware_mpc":
        result=run_risk_aware_mpc(config,calibration_scenarios=calibration_scenarios,
            calibration_seed=calibration_seed,commitment_step_mw=commitment_step_mw)
    elif name=="rafc_v":
        result=run_rafc_v(config,calibration_scenarios=calibration_scenarios,
            calibration_seed=calibration_seed,commitment_step_mw=commitment_step_mw)
    else:
        raise ValueError(f"unknown benchmark controller: {name}")
    if "recovery" not in result and result.get("status")!="solver_error":
        telemetry=result.get("telemetry",{})
        if "final_battery_soc" in telemetry and "final_workload_backlog_mwh" in telemetry:
            result["recovery"]=plan_recovery(config,
                backlog_mwh=float(telemetry["final_workload_backlog_mwh"]),
                current_soc=float(telemetry["final_battery_soc"]))
    return result


def _scenario_shortfall(config: dict, commitment: float, disturbance,
                        assumptions: UncertaintyAssumptions) -> float:
    facility=config["facility"]
    battery=config["battery"]
    event=config["grid_event"]
    planned=commitment+NormalDist().inv_cdf(0.99)*assumptions.meter_noise_std_mw
    flexible=max(0.0,float(facility["deferrable_compute_mw"])-disturbance.urgent_reclaim_mw)
    compute=min(planned,flexible)
    residual=max(0.0,planned-compute)
    duration_h=float(event["duration_minutes"])/60
    usable_soc=float(battery["initial_soc"])+disturbance.initial_soc_error
    if usable_soc<float(battery["min_soc"]):
        return commitment
    energy=max(0.0,(usable_soc-float(battery["min_soc"]))
        *float(battery["capacity_mwh"])*float(battery["discharge_efficiency"]))
    discharge=min(residual,float(battery["max_discharge_mw"])*disturbance.battery_discharge_scale,
                  energy/duration_h)
    delivered=compute+discharge-disturbance.meter_noise_mw
    return max(0.0,commitment-delivered)


def _scenario_reserve_violation(config: dict, commitment: float, disturbance,
                                assumptions: UncertaintyAssumptions) -> bool:
    facility=config["facility"]
    battery=config["battery"]
    event=config["grid_event"]
    soc=float(battery["initial_soc"])+disturbance.initial_soc_error
    if soc<float(battery["min_soc"])-1e-9:
        return True
    planned=commitment+NormalDist().inv_cdf(0.99)*assumptions.meter_noise_std_mw
    flexible=max(0.0,float(facility["deferrable_compute_mw"])-disturbance.urgent_reclaim_mw)
    residual=max(0.0,planned-min(planned,flexible))
    duration_h=float(event["duration_minutes"])/60
    energy=(soc-float(battery["min_soc"]))*float(battery["capacity_mwh"])*float(battery["discharge_efficiency"])
    discharge=min(residual,float(battery["max_discharge_mw"])*disturbance.battery_discharge_scale,
        max(0.0,energy)/duration_h)
    final_soc=soc-discharge*duration_h/(float(battery["discharge_efficiency"])*float(battery["capacity_mwh"]))
    return final_soc<float(battery["min_soc"])-1e-9


def compare_controllers(config: dict[str, Any], *, calibration_scenarios: int = 1000,
                        calibration_seed: int = 100_000, test_scenarios: int = 1000,
                        test_seed: int = 200_000, commitment_step_mw: float = 0.5,
                        confidence: float = 0.95,
                        assumptions: UncertaintyAssumptions | None = None,
                        output_dir: str | Path | None = None) -> dict:
    """Run four controllers and score them on one disjoint held-out seed set.

    Calibration and test seed ranges must not overlap. All controllers receive
    the same test disturbances, and event and joint event/recovery rates are
    reported separately with Wilson intervals.
    """
    if calibration_scenarios<=0 or test_scenarios<=0:
        raise ValueError("calibration_scenarios and test_scenarios must be positive")
    if calibration_seed<0 or test_seed<0:
        raise ValueError("seed starts must be nonnegative")
    calibration_range=set(range(calibration_seed,calibration_seed+calibration_scenarios))
    test_range=set(range(test_seed,test_seed+test_scenarios))
    if calibration_range & test_range:
        raise ValueError("calibration and held-out test seed ranges must be disjoint")
    a=assumptions or UncertaintyAssumptions()
    test=[generate_uncertainty_scenario(test_seed+i,a) for i in range(test_scenarios)]
    summaries=[]
    heldout_outcomes={}
    for name in ("rule_based","deterministic_mpc","risk_aware_mpc","rafc_v"):
        started=perf_counter()
        result=_run_controller(name,config,calibration_scenarios=calibration_scenarios,
            calibration_seed=calibration_seed,commitment_step_mw=commitment_step_mw)
        runtime=perf_counter()-started
        commitment=result.get("accepted_commitment_mw")
        valid=(result.get("status") in ("completed","infeasible") and commitment is not None)
        if not valid:
            summaries.append({"controller":name,"status":result.get("status"),
                "accepted_commitment_mw":commitment,"heldout_sample_count":test_scenarios,
                "complete_event_success_probability":None,"event_wilson_interval":None,
                "event_and_recovery_success_probability":None,"joint_wilson_interval":None,
                "mean_shortfall_mw":None,"event_shortfall_scenarios":None,
                "solver_runtime_seconds":runtime,"computational_failure":True,
                "evidence_complete":False,
                "evidence_split":"heldout_test","controller_result":result})
            continue
        commitment=float(commitment)
        event_pass=[_scenario_passes(config,commitment,s,a,recovery_aware=False) for s in test]
        joint_pass=[_scenario_passes(config,commitment,s,a,recovery_aware=True) for s in test]
        heldout_outcomes[name]={"event":event_pass,"event_and_recovery":joint_pass}
        event_success=sum(event_pass)
        joint_success=sum(joint_pass)
        shortfalls=[_scenario_shortfall(config,commitment,s,a) for s in test]
        reserve_violations=sum(_scenario_reserve_violation(config,commitment,s,a) for s in test)
        reliability=result.get("reliability") or {}
        recovery=result.get("recovery") or {}
        recovery_telemetry=recovery.get("telemetry",{})
        summaries.append({"controller":name,"status":result.get("status"),
            "nominal_dispatch_feasible":result.get("status")=="completed",
            "accepted_commitment_mw":commitment,"commitment_calibration_status":reliability.get("status"),
            "calibration_estimate":reliability.get("estimate"),
            "calibration_lower_confidence_bound":reliability.get("confidence_lower_bound"),
            "heldout_sample_count":test_scenarios,"heldout_seed_start":test_seed,
            "complete_event_successes":event_success,
            "complete_event_success_probability":event_success/test_scenarios,
            "event_wilson_interval":wilson_interval(event_success,test_scenarios,confidence=confidence),
            "event_and_recovery_successes":joint_success,
            "event_and_recovery_success_probability":joint_success/test_scenarios,
            "joint_wilson_interval":wilson_interval(joint_success,test_scenarios,confidence=confidence),
            "event_shortfall_scenarios":sum(x>1e-9 for x in shortfalls),
            "battery_reserve_violation_scenarios":reserve_violations,
            "mean_shortfall_mw":sum(shortfalls)/len(shortfalls),
            "mean_shortfall_when_failed_mw":(sum(shortfalls)/sum(x>1e-9 for x in shortfalls)
                if any(x>1e-9 for x in shortfalls) else 0.0),
            "recovery_feasibility_given_event_success":(joint_success/event_success if event_success else None),
            "nominal_recovery_status":recovery.get("status"),
            "nominal_recovery_complete":recovery.get("status")=="completed",
            "nominal_recovery_max_grid_import_mw":recovery_telemetry.get("max_grid_import_mw"),
            "critical_workload_violations":"not modeled by current uncertainty scenario pass check",
            "solver_termination":(result.get("solver_metadata") or {}).get("termination"),
            "solver_runtime_seconds":runtime,"computational_failure":False,
            "evidence_complete":bool(result.get("telemetry") is not None and result.get("solver_metadata") is not None),
            "evidence_split":"heldout_test","controller_result":result})
    paired_tests={}
    valid_names=list(heldout_outcomes)
    for metric in ("event","event_and_recovery"):
        paired_tests[metric]={}
        for i,first in enumerate(valid_names):
            for second in valid_names[i+1:]:
                paired_tests[metric][f"{first}_vs_{second}"]=exact_mcnemar(
                    heldout_outcomes[first][metric],heldout_outcomes[second][metric])
    by_name={row["controller"]:row for row in summaries}
    ablations={
        "reliability_calibration_disabled":{
            "comparison":"deterministic_mpc_vs_risk_aware_mpc",
            "interpretation":"The deterministic controller attempts the full request; risk-aware MPC calibrates the commitment.",
            "commitment_delta_mw":(by_name["risk_aware_mpc"].get("accepted_commitment_mw")-
                by_name["deterministic_mpc"].get("accepted_commitment_mw")
                if by_name["risk_aware_mpc"].get("accepted_commitment_mw") is not None
                and by_name["deterministic_mpc"].get("accepted_commitment_mw") is not None else None),
            "paired_event_and_recovery_test":paired_tests["event_and_recovery"].get(
                "deterministic_mpc_vs_risk_aware_mpc")},
        "recovery_aware_commitment_disabled":{
            "comparison":"risk_aware_mpc_vs_rafc_v",
            "interpretation":"Both use reliability calibration; RAFC-V additionally screens commitment for recovery feasibility.",
            "commitment_delta_mw":(by_name["rafc_v"].get("accepted_commitment_mw")-
                by_name["risk_aware_mpc"].get("accepted_commitment_mw")
                if by_name["rafc_v"].get("accepted_commitment_mw") is not None
                and by_name["risk_aware_mpc"].get("accepted_commitment_mw") is not None else None),
            "paired_event_and_recovery_test":paired_tests["event_and_recovery"].get(
                "risk_aware_mpc_vs_rafc_v")},
        "rolling_reoptimization_disabled":{
            "status":"not_implemented",
            "reason":"Current controllers use a fixed event schedule; rolling event re-optimization is not yet available."}}
    output={"schema_version":"1.0.0","experiment_id":f"{config['scenario_id']}-four-controller-comparison",
        "scenario_id":config["scenario_id"],"calibration_seed_start":calibration_seed,
        "calibration_sample_count":calibration_scenarios,"heldout_seed_start":test_seed,
        "heldout_sample_count":test_scenarios,"confidence_level":confidence,
        "shared_test_scenarios":True,"assumptions":a.__dict__ if hasattr(a,"__dict__") else {
            key:getattr(a,key) for key in a.__dataclass_fields__},
        "results":summaries,"paired_tests":paired_tests,"ablations":ablations,
        "computational_failure_rate":(sum(row["computational_failure"] for row in summaries)/len(summaries)
            if summaries else 1.0),
        "evidence_complete":bool(summaries) and all(row["evidence_complete"] for row in summaries),
        "limitations":["Disturbance distributions are modeled assumptions.",
            "Held-out outcomes use the same declared scenario pass model as commitment calibration.",
            "Recovery outcomes are evaluated with the exact aggregate feasibility screen for the current RecoveryGuard LP.",
            "No external facility or utility certification is implied."]}
    if output_dir is not None:
        directory=Path(output_dir)
        directory.mkdir(parents=True,exist_ok=True)
        (directory/"four_controller_comparison.json").write_text(json.dumps(output,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        flat=[]
        for row in summaries:
            flat.append({key:value for key,value in row.items() if key!="controller_result"})
        if flat:
            with (directory/"four_controller_comparison.csv").open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=list(flat[0]))
                writer.writeheader()
                writer.writerows(flat)
    return output
