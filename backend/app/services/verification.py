"""Independent arithmetic checks over engine telemetry (not a certification)."""
from __future__ import annotations

from math import isfinite
from typing import Any


TOL = 1e-6


def verify_result(config: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    event = result.get("telemetry", {}).get("event_time_series", [])
    if not event:
        checks.append({"name": "event_telemetry_present", "passed": False,
                       "detail": "No event time-series telemetry is available."})
    else:
        checks.append({"name": "event_telemetry_present", "passed": True,
                       "detail": f"Checked {len(event)} event intervals."})
    facility = config["facility"]
    battery = config["battery"]
    expected_baseline = (float(facility["critical_inference_mw"])
                         + float(facility["fixed_auxiliary_mw"])
                         + float(facility["deferrable_compute_mw"]))
    interval_hours = float(config["grid_event"]["interval_minutes"]) / 60.0
    expected_steps = int(config["grid_event"]["duration_minutes"]) // int(config["grid_event"]["interval_minutes"])
    previous_soc = float(battery["initial_soc"])
    for index, row in enumerate(event):
        label = f"event_step_{index}"
        try:
            baseline = float(row["baseline_grid_import_mw"])
            grid = float(row["grid_import_mw"])
            discharge = float(row.get("battery_discharge_mw", 0.0))
            charge = float(row.get("battery_charge_mw", 0.0))
            if "flexible_compute_mw" in row:
                flexible = float(row["flexible_compute_mw"])
            else:
                curtailment = float(row.get("flexible_compute_curtailment_mw", 0.0))
                flexible = float(facility["deferrable_compute_mw"]) - curtailment
            expected_grid = (float(facility["critical_inference_mw"])
                             + float(facility["fixed_auxiliary_mw"])
                             + flexible + charge - discharge)
            grid_ok = (all(isfinite(x) for x in (baseline, grid, expected_grid, flexible, charge, discharge))
                       and abs(baseline - expected_baseline) <= TOL
                       and abs(grid - expected_grid) <= TOL
                       and grid >= -TOL
                       and -TOL <= flexible <= float(facility["deferrable_compute_mw"]) + TOL
                       and charge >= -TOL and discharge >= -TOL)
            checks.append({"name": f"{label}_power_balance", "passed": grid_ok,
                           "detail": f"reported={grid:.6f} MW, recomputed={expected_grid:.6f} MW"})
            if "delivered_reduction_mw" in row:
                delivered = float(row["delivered_reduction_mw"])
                delivered_ok = abs(delivered - (baseline - grid)) <= TOL
                checks.append({"name": f"{label}_delivered_reduction", "passed": delivered_ok,
                               "detail": f"reported={delivered:.6f} MW, recomputed={baseline-grid:.6f} MW"})
            soc_start = row.get("battery_soc_start")
            soc_end = row.get("battery_soc_end")
            if soc_start is not None and soc_end is not None:
                soc_start = float(soc_start)
                soc_end = float(soc_end)
                expected_soc = float(soc_start) + (
                    charge * float(battery["charge_efficiency"])
                    - discharge / float(battery["discharge_efficiency"])
                ) * interval_hours / float(battery["capacity_mwh"])
                soc_ok = (abs(soc_end - expected_soc) <= TOL
                          and abs(soc_start - previous_soc) <= TOL
                          and float(battery["min_soc"]) - TOL <= soc_start <= float(battery["max_soc"]) + TOL
                          and float(battery["min_soc"]) - TOL <= float(soc_end) <= float(battery["max_soc"]) + TOL
                          and charge <= float(battery["max_charge_mw"]) + TOL
                          and discharge <= float(battery["max_discharge_mw"]) + TOL
                          and not (charge > TOL and discharge > TOL))
                checks.append({"name": f"{label}_battery_energy", "passed": soc_ok,
                               "detail": f"reported SoC={soc_end:.8f}, recomputed={expected_soc:.8f}"})
                previous_soc = soc_end
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            checks.append({"name": f"{label}_telemetry_parse", "passed": False, "detail": str(exc)})
    checks.append({"name": "event_interval_count", "passed": len(event) == expected_steps,
                   "detail": f"observed={len(event)}, expected={expected_steps}"})
    accepted = result.get("accepted_commitment_mw")
    complete_flag = result.get("complete_event_success")
    if accepted is not None and complete_flag is not None:
        recomputed_complete = (len(event) == expected_steps and all(
            float(row.get("delivered_reduction_mw", float("-inf"))) >= float(accepted) - TOL
            for row in event
        ))
        checks.append({"name": "complete_event_flag", "passed": bool(complete_flag) == recomputed_complete,
                       "detail": f"reported={bool(complete_flag)}, recomputed={recomputed_complete}"})

    recovery = result.get("recovery") or {}
    recovery_rows = recovery.get("telemetry", {}).get("recovery_time_series", [])
    if recovery_rows:
        ceiling = float(config["recovery"]["grid_import_ceiling_mw"])
        recovery_hours = float(config["recovery"]["interval_minutes"]) / 60.0
        expected_recovery_soc = float(recovery["telemetry"]["initial_battery_soc"])
        expected_backlog = float(recovery["telemetry"]["initial_backlog_mwh"])
        recovery_grid_ok = True
        recovery_energy_ok = True
        for row in recovery_rows:
            base = float(row["base_demand_mw"])
            work = float(row["workload_recovery_mw"])
            charge = float(row["battery_charge_mw"])
            grid = float(row["grid_import_mw"])
            soc_start = float(row["battery_soc_start"])
            soc_end = float(row["battery_soc_end"])
            backlog_start = float(row["workload_backlog_start_mwh"])
            backlog_end = float(row["workload_backlog_end_mwh"])
            recovery_grid_ok &= (grid <= ceiling + TOL
                                 and abs(grid - (base + work + charge)) <= TOL
                                 and abs(base - float(config["recovery"]["nominal_base_demand_mw"])) <= TOL
                                 and work >= -TOL
                                 and work <= float(facility["deferrable_compute_mw"]) + TOL
                                 and charge >= -TOL)
            expected_soc = soc_start + charge * float(battery["charge_efficiency"]) * recovery_hours / float(battery["capacity_mwh"])
            expected_backlog_end = max(0.0, backlog_start - work * recovery_hours)
            recovery_energy_ok &= (
                abs(soc_start - expected_recovery_soc) <= TOL
                and abs(soc_end - expected_soc) <= TOL
                and float(battery["min_soc"]) - TOL <= soc_end <= float(battery["max_soc"]) + TOL
                and charge <= float(battery["max_charge_mw"]) + TOL
                and abs(backlog_start - expected_backlog) <= TOL
                and abs(backlog_end - expected_backlog_end) <= TOL
            )
            expected_recovery_soc = soc_end
            expected_backlog = backlog_end
        checks.append({"name": "recovery_shared_grid_capacity", "passed": recovery_grid_ok,
                       "detail": f"checked {len(recovery_rows)} intervals against the shared grid ceiling"})
        checks.append({"name": "recovery_energy_and_backlog", "passed": recovery_energy_ok,
                       "detail": "recomputed battery charging and deferred-work clearance for each recovery interval"})
        if recovery.get("status") == "completed":
            targets_ok = (recovery["telemetry"].get("backlog_cleared") is True
                          and recovery["telemetry"].get("soc_target_met") is True
                          and expected_backlog <= TOL
                          and expected_recovery_soc + TOL >= float(config["recovery"]["target_soc"]))
            checks.append({"name": "recovery_targets", "passed": targets_ok,
                           "detail": "recomputed final backlog and SoC against configured recovery targets"})
    elif recovery:
        checks.append({"name": "recovery_plan_status", "passed": recovery.get("status") == "infeasible" or recovery.get("status") == "solver_error",
                       "detail": f"recovery status is {recovery.get('status')}; no feasible schedule was returned"})
    else:
        checks.append({"name": "recovery_telemetry_present", "passed": False,
                       "detail": "No recovery result is available."})

    failed = [check["name"] for check in checks if not check["passed"]]
    status = "passed" if not failed else "failed"
    return {"status": status, "independent_check": True, "certification": False,
            "check_count": len(checks), "failed_check_count": len(failed),
            "failed_checks": failed, "checks": checks,
            "method": "Recompute power balance, AC-side delivery, battery power and SoC transitions, event interval count, recovery backlog and SoC transitions, shared-import ceiling, and final recovery targets from returned telemetry."}

\n