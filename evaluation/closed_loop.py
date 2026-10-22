"""Paired closed-loop held-out evaluation of RAFC-V and MPC baselines."""
from __future__ import annotations

import csv
import json
from math import ceil, isfinite
from pathlib import Path
from statistics import NormalDist
from time import perf_counter
from typing import Any

import numpy as np

from baselines.deterministic_mpc import solve_deterministic_dispatch
from evaluation.metrics import wilson_interval
from evaluation.statistical_tests import exact_mcnemar
from optimization.commitment import calibrate_commitment
from optimization.dispatch import solve_rolling_event_dispatch
from optimization.recovery import plan_recovery
from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario

METHODS = ("fixed_horizon", "rolling_risk_aware_mpc", "rolling_rafc_v")


def _event_metrics(rows: list[dict], commitment: float, dt: float, minimum_soc: float,
                   initial_soc: float | None = None) -> dict:
    delivered = [float(row["delivered_reduction_mw"]) for row in rows]
    shortfall = [max(0.0, commitment - value) for value in delivered]
    reserve_violations = sum(
        float(row.get("battery_soc_end", 1.0)) < minimum_soc - 1e-8
        for row in rows
    )
    if initial_soc is not None and initial_soc < minimum_soc - 1e-8:
        reserve_violations = max(1, reserve_violations)
    return {
        "delivered_mean_mw": sum(delivered) / len(delivered) if delivered else None,
        "delivered_min_mw": min(delivered) if delivered else None,
        "shortfall_max_mw": max(shortfall, default=0.0),
        "shortfall_energy_mwh": sum(shortfall) * dt,
        "shortfall_steps": sum(value > 1e-7 for value in shortfall),
        "reserve_violation_steps": reserve_violations,
    }


def _recovery_metrics(config: dict, backlog: float, soc: float) -> tuple[dict, dict]:
    bcfg = config["battery"]
    if not isfinite(soc) or soc < float(bcfg["min_soc"]) - 1e-8 or soc > float(bcfg["max_soc"]) + 1e-8:
        return {"status": "infeasible", "telemetry": {}}, {
            "deadline_miss": None, "soc_target_miss": None,
            "recovery_feasible": False, "rebound_peak_mw": None,
            "recovery_runtime_seconds": 0.0,
        }
    recovery = plan_recovery(config, backlog_mwh=max(0.0, backlog), current_soc=soc)
    telemetry = recovery.get("telemetry", {})
    clear = telemetry.get("backlog_cleared")
    target = telemetry.get("soc_target_met")
    success = recovery.get("status") == "completed" and clear is True and target is True
    if recovery.get("status") == "completed":
        deadline_miss = not clear
        soc_target_miss = not target
    elif recovery.get("status") == "infeasible":
        rcfg = config["recovery"]
        bcfg = config["battery"]
        fcfg = config["facility"]
        event = config["grid_event"]
        interval = int(rcfg["interval_minutes"])
        event_end = int(event["start_minute"]) + int(event["duration_minutes"])
        horizon_intervals = int(rcfg["horizon_minutes"]) // interval
        headroom = max(0.0, float(rcfg["grid_import_ceiling_mw"]) - float(rcfg["nominal_base_demand_mw"]))
        clear_intervals = min(horizon_intervals, max(0, ceil((int(rcfg.get("clear_deferred_work_by_minute", event_end + int(rcfg["horizon_minutes"]))) - event_end) / interval)))
        target_intervals = min(horizon_intervals, max(0, ceil((int(rcfg.get("target_minute", event_end + int(rcfg["horizon_minutes"]))) - event_end) / interval)))
        work_capacity = min(float(fcfg["deferrable_compute_mw"]), headroom) * clear_intervals * interval / 60.0
        charge_needed = max(0.0, (float(rcfg["target_soc"]) - soc) * float(bcfg["capacity_mwh"]) / float(bcfg["charge_efficiency"]))
        charge_capacity = min(float(bcfg["max_charge_mw"]), headroom) * target_intervals * interval / 60.0
        deadline_miss = backlog > work_capacity + 1e-8
        soc_target_miss = charge_needed > charge_capacity + 1e-8
    else:
        deadline_miss = None
        soc_target_miss = None
    return recovery, {
        "deadline_miss": deadline_miss,
        "soc_target_miss": soc_target_miss,
        "recovery_feasible": success,
        "rebound_peak_mw": telemetry.get("max_grid_import_mw"),
        "recovery_runtime_seconds": (recovery.get("solver_metadata") or {}).get("runtime_seconds", 0.0),
    }


def _paired_mean_difference_ci(first: list[float], second: list[float], *,
                               seed: int, confidence: float = 0.95,
                               resamples: int = 10_000) -> list[float] | None:
    pairs = [(a, b) for a, b in zip(first, second) if isfinite(a) and isfinite(b)]
    if not pairs:
        return None
    differences = np.asarray([a - b for a, b in pairs], dtype=float)
    rng = np.random.default_rng(seed)
    # Draw in row blocks to bound memory; the stream is consumed in the same order.
    block = max(1, 2_000_000 // max(1, len(differences)))
    draws = np.concatenate([
        rng.choice(differences, size=(min(block, resamples - start), len(differences)),
                   replace=True).mean(axis=1)
        for start in range(0, resamples, block)])
    alpha = (1.0 - confidence) / 2.0
    return [float(np.quantile(draws, alpha)), float(np.quantile(draws, 1.0 - alpha))]


def run_closed_loop_rafc_evaluation(
    config: dict[str, Any], *, calibration_scenarios: int = 1000,
    calibration_seed: int = 100_000, test_scenarios: int = 100,
    test_seed: int = 400_000, commitment_step_mw: float = 0.1,
    confidence: float = 0.95, assumptions: UncertaintyAssumptions | None = None,
    output_dir: str | Path | None = None, dispatch_policy: str = "v1",
) -> dict:
    """Run paired fixed, rolling risk-aware, and rolling RAFC-V test controllers.

    Both commitment calibrations use only the same calibration seed range.
    Held-out disturbance outcomes are never used to pick commitments. Both
    rolling controllers use the same receding-horizon Pyomo/HiGHS dispatcher,
    meter margin, disturbance observations, and RecoveryGuard. They differ in
    commitment calibration: risk-aware MPC screens event reliability only;
    RAFC-V screens event reliability and recovery feasibility.

    The fixed-horizon comparator uses the RAFC-V commitment and plans to meet
    the same one-sided 99% meter margin as rolling dispatch. Its event schedule
    is frozen before held-out disturbances are generated.
    """
    if calibration_scenarios <= 0 or test_scenarios <= 0:
        raise ValueError("scenario counts must be positive")
    if calibration_seed < 0 or test_seed < 0:
        raise ValueError("seed starts must be nonnegative")
    cal_seeds = set(range(calibration_seed, calibration_seed + calibration_scenarios))
    test_seeds = set(range(test_seed, test_seed + test_scenarios))
    if cal_seeds & test_seeds:
        raise ValueError("calibration and held-out seed ranges must be disjoint")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0,1)")
    if dispatch_policy not in ("v1", "v2"):
        raise ValueError("dispatch_policy must be 'v1' or 'v2'")
    # v2 applies to BOTH rolling arms so the comparison isolates the commitment screen.
    cal_margin = 0.0 if dispatch_policy == "v2" else None
    dispatch_kwargs = ({"forecast": "persistence", "soft_margin": True}
                       if dispatch_policy == "v2" else {})

    a = assumptions or UncertaintyAssumptions()
    cal_start = perf_counter()
    rafc_cal = calibrate_commitment(
        config, n_scenarios=calibration_scenarios, seed=calibration_seed,
        step_mw=commitment_step_mw, confidence=confidence,
        recovery_aware=True, assumptions=a, meter_margin_mw=cal_margin,
        observed_noise=dispatch_policy == "v2",
    )
    risk_cal = calibrate_commitment(
        config, n_scenarios=calibration_scenarios, seed=calibration_seed,
        step_mw=commitment_step_mw, confidence=confidence,
        recovery_aware=False, assumptions=a, meter_margin_mw=cal_margin,
        observed_noise=dispatch_policy == "v2",
    )
    calibration_runtime = perf_counter() - cal_start
    commitments = {
        "rolling_rafc_v": float(rafc_cal["accepted_commitment_mw"]),
        "rolling_risk_aware_mpc": float(risk_cal["accepted_commitment_mw"]),
    }
    dt = float(config["grid_event"]["interval_minutes"]) / 60.0
    nsteps = int(config["grid_event"]["duration_minutes"]) // int(config["grid_event"]["interval_minutes"])
    meter_margin = NormalDist().inv_cdf(0.99) * a.meter_noise_std_mw
    fixed_target = commitments["rolling_rafc_v"] + meter_margin
    fixed_start = perf_counter()
    fixed = solve_deterministic_dispatch(config, accepted_commitment_mw=fixed_target)
    fixed_runtime = perf_counter() - fixed_start
    if fixed.get("status") != "completed":
        raise RuntimeError("fixed-horizon nominal dispatch failed: " + str(fixed.get("infeasibility_reason")))
    fixed_rows = fixed["telemetry"]["event_time_series"]
    if len(fixed_rows) != nsteps:
        raise RuntimeError("fixed-horizon dispatcher returned an incomplete event schedule")

    outcomes = {method: {"event": [], "joint": []} for method in METHODS}
    rows_out: list[dict] = []
    controller_samples = {method: [] for method in METHODS}
    experiment_started = perf_counter()

    for offset in range(test_scenarios):
        disturbance = generate_uncertainty_scenario(test_seed + offset, a)
        observed = {
            "available_flexible_compute_mw": max(
                0.0, float(config["facility"]["deferrable_compute_mw"]) - disturbance.urgent_reclaim_mw
            ),
            "battery_discharge_scale": disturbance.battery_discharge_scale,
            "critical_power_delta_mw": disturbance.critical_power_delta_mw,
            "meter_noise_mw": disturbance.meter_noise_mw,
        }
        observations = [dict(observed) for _ in range(nsteps)]
        observations[0]["initial_soc_error"] = disturbance.initial_soc_error
        scenario_row: dict[str, Any] = {
            "seed": disturbance.seed,
            "urgent_reclaim_mw": disturbance.urgent_reclaim_mw,
            "battery_discharge_scale": disturbance.battery_discharge_scale,
            "initial_soc_error": disturbance.initial_soc_error,
            "critical_power_delta_mw": disturbance.critical_power_delta_mw,
            "meter_noise_mw": disturbance.meter_noise_mw,
        }

        dispatch_cache: dict[float, tuple[dict, float, str | None]] = {}
        recovery_cache: dict[tuple[float, float], tuple[dict, dict]] = {}

        # The same scenario is fed to the same rolling controller under the two
        # calibration policies, preserving a paired and operationally fair test.
        for method in ("rolling_risk_aware_mpc", "rolling_rafc_v"):
            commitment = commitments[method]
            if commitment in dispatch_cache:
                dispatch, dispatch_runtime, shared_from = dispatch_cache[commitment]
            else:
                started = perf_counter()
                dispatch = solve_rolling_event_dispatch(
                    config, commitment, observations=observations,
                    delivery_margin_mw=meter_margin if commitment > 1e-12 else 0.0,
                    **dispatch_kwargs,
                )
                dispatch_runtime = perf_counter() - started
                shared_from = None
                dispatch_cache[commitment] = (dispatch, dispatch_runtime, method)
            event_rows = dispatch.get("telemetry", {}).get("event_time_series", [])
            physical = _event_metrics(event_rows, commitment, dt,
                float(config["battery"]["min_soc"]),
                float(config["battery"]["initial_soc"]) + disturbance.initial_soc_error)
            event_ok = physical["reserve_violation_steps"] == 0 and (
                commitment <= 1e-12 or (
                    len(event_rows) == nsteps and physical["shortfall_steps"] == 0
                )
            )
            last = event_rows[-1] if event_rows else {}
            final_soc = dispatch.get("telemetry", {}).get("final_battery_soc", last.get("battery_soc_end"))
            final_backlog = dispatch.get("telemetry", {}).get("final_workload_backlog_mwh", last.get("workload_backlog_mwh", 0.0))
            recovery_key = (float(final_backlog or 0.0), float(final_soc) if final_soc is not None else float("nan"))
            if recovery_key in recovery_cache:
                recovery, recovery_metrics = recovery_cache[recovery_key]
            else:
                recovery, recovery_metrics = _recovery_metrics(config, *recovery_key)
                recovery_cache[recovery_key] = (recovery, recovery_metrics)
            joint_ok = event_ok and recovery_metrics["recovery_feasible"]
            outcomes[method]["event"].append(event_ok)
            outcomes[method]["joint"].append(joint_ok)
            solver_time = (dispatch.get("solver_metadata") or {}).get("runtime_seconds", dispatch_runtime)
            sample = {
                **physical,
                "event_success": event_ok,
                "joint_success": joint_ok,
                "event_status": dispatch.get("status"),
                "event_failure_category": _event_failure_category(dispatch, physical, event_ok),
                "deadline_miss": recovery_metrics["deadline_miss"],
                "soc_target_miss": recovery_metrics["soc_target_miss"],
                "recovery_feasible": recovery_metrics["recovery_feasible"],
                "recovery_status": recovery.get("status"),
                "rebound_peak_mw": recovery_metrics["rebound_peak_mw"],
                "final_soc": final_soc,
                "final_backlog_mwh": final_backlog,
                "solver_runtime_seconds": solver_time,
                "recovery_runtime_seconds": recovery_metrics["recovery_runtime_seconds"],
                "solver_failure": dispatch.get("status") == "solver_error" or recovery.get("status") == "solver_error",
                "dispatch_shared_from": shared_from,
            }
            controller_samples[method].append(sample)
            for key, value in sample.items():
                scenario_row[f"{method}_{key}"] = value

        # Fixed event schedule is determined before any held-out observation.
        method = "fixed_horizon"
        commitment = commitments["rolling_rafc_v"]
        soc = float(config["battery"]["initial_soc"]) + disturbance.initial_soc_error
        backlog = 0.0
        fixed_deliveries = []
        fixed_shortfalls = []
        reserve_violations = 0
        for planned in fixed_rows:
            curtail_request = float(planned["work_deferred_mwh"]) / dt
            curtail = min(curtail_request, observed["available_flexible_compute_mw"])
            reserve_mwh = max(0.0, (soc - float(config["battery"]["min_soc"])) * float(config["battery"]["capacity_mwh"]))
            discharge = min(
                float(planned["battery_discharge_mw"]),
                float(config["battery"]["max_discharge_mw"]) * disturbance.battery_discharge_scale,
                reserve_mwh * float(config["battery"]["discharge_efficiency"]) / dt,
            )
            soc -= discharge / float(config["battery"]["discharge_efficiency"]) * dt / float(config["battery"]["capacity_mwh"])
            if soc < float(config["battery"]["min_soc"]) - 1e-8:
                reserve_violations += 1
            backlog += curtail * dt
            delivered = curtail + discharge - disturbance.meter_noise_mw
            fixed_deliveries.append(delivered)
            fixed_shortfalls.append(max(0.0, commitment - delivered))
        fixed_physical = {
            "delivered_mean_mw": sum(fixed_deliveries) / nsteps,
            "delivered_min_mw": min(fixed_deliveries),
            "shortfall_max_mw": max(fixed_shortfalls),
            "shortfall_energy_mwh": sum(fixed_shortfalls) * dt,
            "shortfall_steps": sum(value > 1e-7 for value in fixed_shortfalls),
            "reserve_violation_steps": reserve_violations,
        }
        fixed_ok = reserve_violations == 0 and (
            commitment <= 1e-12 or fixed_physical["shortfall_steps"] == 0
        )
        fixed_recovery, fixed_recovery_metrics = _recovery_metrics(config, backlog, soc)
        fixed_joint = fixed_ok and fixed_recovery_metrics["recovery_feasible"]
        outcomes[method]["event"].append(fixed_ok)
        outcomes[method]["joint"].append(fixed_joint)
        fixed_sample = {
            **fixed_physical,
            "event_success": fixed_ok,
            "joint_success": fixed_joint,
            "event_status": fixed.get("status"),
            "event_failure_category": "delivery_shortfall" if not fixed_ok else None,
            "deadline_miss": fixed_recovery_metrics["deadline_miss"],
            "soc_target_miss": fixed_recovery_metrics["soc_target_miss"],
            "recovery_feasible": fixed_recovery_metrics["recovery_feasible"],
            "recovery_status": fixed_recovery.get("status"),
            "rebound_peak_mw": fixed_recovery_metrics["rebound_peak_mw"],
            "final_soc": soc,
            "final_backlog_mwh": backlog,
            "solver_runtime_seconds": None,
            "schedule_setup_solver_runtime_seconds": fixed_runtime,
            "recovery_runtime_seconds": fixed_recovery_metrics["recovery_runtime_seconds"],
            "solver_failure": fixed_recovery.get("status") == "solver_error",
        }
        controller_samples[method].append(fixed_sample)
        for key, value in fixed_sample.items():
            scenario_row[f"{method}_{key}"] = value
        rows_out.append(scenario_row)

    def summarize(method: str) -> dict:
        samples = controller_samples[method]
        event_count = sum(outcomes[method]["event"])
        joint_count = sum(outcomes[method]["joint"])
        def avg(key: str) -> float | None:
            vals = [float(row[key]) for row in samples if row.get(key) is not None]
            return sum(vals) / len(vals) if vals else None
        return {
            "controller": method,
            "commitment_mw": commitments.get(method, commitments["rolling_rafc_v"]),
            "heldout_count": test_scenarios,
            "event_successes": event_count,
            "event_success_probability": event_count / test_scenarios,
            "event_wilson_interval": wilson_interval(event_count, test_scenarios, confidence=confidence),
            "event_and_recovery_successes": joint_count,
            "event_and_recovery_success_probability": joint_count / test_scenarios,
            "joint_wilson_interval": wilson_interval(joint_count, test_scenarios, confidence=confidence),
            "mean_delivered_mw": avg("delivered_mean_mw"),
            "delivered_observation_count": sum(row["delivered_mean_mw"] is not None for row in samples),
            "mean_minimum_delivered_mw": avg("delivered_min_mw"),
            "mean_max_shortfall_mw": avg("shortfall_max_mw"),
            "mean_shortfall_energy_mwh": avg("shortfall_energy_mwh"),
            "scenarios_with_shortfall": sum(row["shortfall_steps"] > 0 for row in samples),
            "battery_reserve_violation_scenarios": sum(row["reserve_violation_steps"] > 0 for row in samples),
            "battery_reserve_violation_steps": sum(row["reserve_violation_steps"] for row in samples),
            "workload_deadline_miss_scenarios": sum(bool(row["deadline_miss"]) for row in samples),
            "workload_deadline_evaluation_unknown_scenarios": sum(row["deadline_miss"] is None for row in samples),
            "recovery_successes": sum(bool(row["recovery_feasible"]) for row in samples),
            "recovery_feasibility_probability": sum(bool(row["recovery_feasible"]) for row in samples) / test_scenarios,
            "mean_rebound_peak_mw": avg("rebound_peak_mw"),
            "rebound_peak_case_count": sum(row["rebound_peak_mw"] is not None for row in samples),
            "max_rebound_peak_mw": max((float(row["rebound_peak_mw"]) for row in samples if row["rebound_peak_mw"] is not None), default=None),
            "mean_event_solver_runtime_seconds": avg("solver_runtime_seconds"),
            "event_solver_runtime_case_count": sum(row["solver_runtime_seconds"] is not None for row in samples),
            "schedule_setup_solver_runtime_seconds": (fixed_runtime if method == "fixed_horizon" else None),
            "mean_recovery_solver_runtime_seconds": avg("recovery_runtime_seconds"),
            "solver_failure_scenarios": sum(bool(row["solver_failure"]) for row in samples),
            "failure_categories": _failure_counts(samples),
        }

    summaries = [summarize(method) for method in METHODS]
    pairwise = {}
    for i, first in enumerate(METHODS):
        for second in METHODS[i + 1:]:
            key = f"{first}_vs_{second}"
            pairwise[key] = {
                "event_mcnemar": exact_mcnemar(outcomes[first]["event"], outcomes[second]["event"]),
                "event_recovery_mcnemar": exact_mcnemar(outcomes[first]["joint"], outcomes[second]["joint"]),
                "paired_mean_difference_ci_first_minus_second": {},
            }
            for metric in ("delivered_mean_mw", "shortfall_energy_mwh", "rebound_peak_mw"):
                left = [float(row[metric]) if row.get(metric) is not None else float("nan") for row in controller_samples[first]]
                right = [float(row[metric]) if row.get(metric) is not None else float("nan") for row in controller_samples[second]]
                pairwise[key]["paired_mean_difference_ci_first_minus_second"][metric] = _paired_mean_difference_ci(
                    left, right, seed=test_seed + i * 100 + METHODS.index(second), confidence=confidence
                )
    _holm_adjust_pairwise(pairwise)

    output = {
        "schema_version": "1.0.0",
        "experiment_id": f"{config['scenario_id']}-closed-loop-controller-comparison",
        "scenario_id": config["scenario_id"],
        "calibration_seed_start": calibration_seed,
        "calibration_sample_count": calibration_scenarios,
        "heldout_seed_start": test_seed,
        "heldout_sample_count": test_scenarios,
        "confidence_level": confidence,
        "paired_disturbances": True,
        "dispatch_policy": dispatch_policy,
        "artifact_type": "experiment_result",
        "assumptions": {key: getattr(a, key) for key in a.__dataclass_fields__},
        "commitment_calibration": {
            "rolling_rafc_v": rafc_cal,
            "rolling_risk_aware_mpc": risk_cal,
            "heldout_data_used": False,
            "same_calibration_seed_set": True,
        },
        "controller_comparison": {
            "fixed_horizon": "RAFC commitment; meter-margin protected nominal schedule; then held-out disturbances",
            "rolling_risk_aware_mpc": "event-reliability calibration; rolling Pyomo/HiGHS dispatch; RecoveryGuard verification",
            "rolling_rafc_v": "event and recovery reliability calibration; same rolling dispatch and RecoveryGuard",
        },
        "results": summaries,
        "paired_tests": pairwise,
        "runtime_seconds": perf_counter() - experiment_started,
        "calibration_runtime_seconds": calibration_runtime,
        "scenarios": rows_out,
        "limitations": [
            "Disturbance distributions are modeled assumptions, not measured facility data.",
            "Each held-out disturbance is constant within one event; it becomes observable to rolling controllers only at its interval.",
            "Critical-power deviation is common-mode to baseline-relative reduction and is not a critical-service failure model.",
            "Fixed-horizon schedule is optimized for the same RAFC commitment and 99% meter margin, but does not re-optimize under disturbance observations.",
            "RecoveryGuard uses the explicit 17 MW modeled recovery base and checks the shared grid ceiling.",
            "Fixed-horizon optimizer setup time is one pre-test schedule solve; rolling event solver time is per held-out scenario, so these runtime values are not directly paired.",
        ],
    }
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "closed_loop_comparison.json").write_text(
            json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        with (directory / "closed_loop_scenarios.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows_out[0]))
            writer.writeheader()
            writer.writerows(rows_out)
    return output


def _event_failure_category(dispatch: dict, physical: dict, event_ok: bool) -> str | None:
    if event_ok:
        return None
    if dispatch.get("status") == "solver_error":
        return "event_solver_error"
    if physical["reserve_violation_steps"]:
        return "battery_reserve_violation"
    if physical["shortfall_steps"]:
        return "delivery_shortfall"
    if dispatch.get("status") == "infeasible":
        return "event_infeasible"
    return "incomplete_event_telemetry"


def _failure_counts(samples: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in samples:
        category = row.get("event_failure_category")
        if category:
            counts[category] = counts.get(category, 0) + 1
        if row.get("deadline_miss"):
            counts["workload_deadline_miss"] = counts.get("workload_deadline_miss", 0) + 1
        if row.get("soc_target_miss"):
            counts["battery_recovery_target_miss"] = counts.get("battery_recovery_target_miss", 0) + 1
        if row.get("solver_failure"):
            counts["solver_failure"] = counts.get("solver_failure", 0) + 1
    return counts


def _holm_adjust_pairwise(pairwise: dict) -> None:
    """Add family-wise adjusted p-values across the three controller pairs."""
    for field in ("event_mcnemar", "event_recovery_mcnemar"):
        ordered = sorted(
            ((key, float(row[field]["p_value"])) for key, row in pairwise.items()),
            key=lambda item: item[1],
        )
        running = 0.0
        count = len(ordered)
        for rank, (key, pvalue) in enumerate(ordered):
            running = max(running, min(1.0, (count - rank) * pvalue))
            pairwise[key][field]["holm_adjusted_p_value"] = running
