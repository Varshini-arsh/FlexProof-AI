"""Operational evidence arithmetic, independent of controller code and flags.

Scope: the FP-001 electrical and aggregate-work model, using supplied recorded
measurements. This does not verify inference quality or sensor authenticity.
"""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from typing import Any

VERSION = "operational-verifier-1.0.0"
TOL = 1e-6


class MissingEvidence(ValueError):
    pass


def canonical_hash(value: Any) -> str:
    def normalize(item: Any) -> Any:
        # JSON clients commonly round-trip 20.0 as 20 and -0.0 as 0.
        # Normalize numerically equivalent values so hashes survive that wire conversion.
        if isinstance(item, float) and (item == 0 or item.is_integer()):
            return int(item)
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        return item

    return sha256(json.dumps(normalize(value), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def evidence_hash(config: dict, result: dict) -> str:
    # Verification and export metadata are stored separately from the core result.
    core = {k: v for k, v in result.items() if k not in {"independent_verification", "input_hash", "evidence_hash"}}
    return canonical_hash({"config": config, "result": core})


def _number(data: dict, key: str) -> float:
    if not isinstance(data, dict):
        raise ValueError(f"Expected an object containing {key}")
    if key not in data or data[key] is None:
        raise MissingEvidence(f"Missing numeric field: {key}")
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"Invalid finite numeric field: {key}")
    return float(value)


def verify_result(config: dict[str, Any], result: dict[str, Any], *,
                  expected_input_hash: str | None = None,
                  expected_evidence_hash: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}

    def add(name: str, condition: bool | None, detail: str) -> None:
        checks.append({"name": name, "status": "insufficient_evidence" if condition is None else "pass" if condition else "fail", "detail": detail})

    def finish() -> dict[str, Any]:
        failed = [c["name"] for c in checks if c["status"] == "fail"]
        missing = [c["name"] for c in checks if c["status"] == "insufficient_evidence"]
        return {"status": "fail" if failed else "insufficient_evidence" if missing else "pass",
                "verifier_version": VERSION, "certification": False, "independent_check": True,
                "check_count": len(checks), "failed_check_count": len(failed),
                "insufficient_check_count": len(missing), "failed_checks": failed,
                "insufficient_checks": missing, "checks": checks, "metrics": metrics,
                "scope": "Recorded electrical demand, battery energy and aggregate flexible-work accounting under the supplied FP-001 assumptions.",
                "limitations": ["Inputs and measurements are supplied simulation evidence; no independent sensor or service-quality data are available.",
                    "Critical-load protection means electrical power is accounted for; inference latency and service quality are not modeled.",
                    "Work deadlines use the aggregate workload cohort and configured clearance deadline, not production GPU job traces.",
                    "SHA-256 hashes provide traceable byte-content comparison; they are not signatures or proof of sensor authenticity.",
                    "Operational verification does not establish calibration or held-out reliability."]}

    try:
        ih = canonical_hash(config)
        eh = evidence_hash(config, result)
        metrics.update(input_hash=ih, evidence_hash=eh)
        if expected_input_hash is not None:
            add("input_hash", ih == expected_input_hash, "Canonical input hash compared with the supplied recorded hash.")
        if expected_evidence_hash is not None:
            add("evidence_hash", eh == expected_evidence_hash, "Canonical evidence hash compared with the supplied recorded hash.")
    except (ValueError, TypeError) as exc:
        add("json_integrity", False, str(exc))
        return finish()
    if config.get("schema_version") != "1.0.0" or result.get("schema_version") != "1.0.0":
        add("schema_version", None, "Supported scenario and result schema version 1.0.0 is required.")
        return finish()
    identities_present = bool(config.get("scenario_id")) and bool(result.get("scenario_id"))
    add("scenario_identity", config.get("scenario_id") == result.get("scenario_id") if identities_present else None, "Scenario identifiers must be present and agree.")
    try:
        facility, battery, event_cfg, recovery_cfg = (config[k] for k in ("facility", "battery", "grid_event", "recovery"))
        critical = _number(facility, "critical_inference_mw")
        fixed = _number(facility, "fixed_auxiliary_mw")
        cap = _number(facility, "deferrable_compute_mw")
        capacity = _number(battery, "capacity_mwh")
        eff_c, eff_d = _number(battery, "charge_efficiency"), _number(battery, "discharge_efficiency")
        minimum, maximum = _number(battery, "min_soc"), _number(battery, "max_soc")
        charge_cap, discharge_cap = _number(battery, "max_charge_mw"), _number(battery, "max_discharge_mw")
        soc = _number(battery, "initial_soc")
        start = _number(event_cfg, "start_minute")
        interval = _number(event_cfg, "interval_minutes")
        duration = _number(event_cfg, "duration_minutes")
        accepted = _number(result, "accepted_commitment_mw")
        requested = _number(event_cfg, "requested_reduction_mw")
        if not (capacity > 0 and 0 < eff_c <= 1 and 0 < eff_d <= 1 and interval > 0 and duration > 0 and duration % interval == 0):
            raise ValueError("Invalid battery efficiencies/capacity or event duration/interval")
        expected_steps = int(duration / interval)
        telemetry = result.get("telemetry")
        if not isinstance(telemetry, dict):
            raise MissingEvidence("Missing telemetry object")
        rows = telemetry.get("event_time_series")
        if not isinstance(rows, list):
            raise MissingEvidence("Missing event_time_series array")
    except (KeyError, MissingEvidence) as exc:
        add("required_configuration", None, str(exc)); return finish()
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        add("required_configuration", False, str(exc)); return finish()

    add("accepted_commitment_range", 0 <= accepted <= requested + TOL, "Commitment must be nonnegative and no larger than the request.")
    metrics.update(accepted_commitment_mw=accepted, requested_reduction_mw=requested)
    add("event_interval_count", True if len(rows) == expected_steps else None if len(rows) < expected_steps else False,
        f"Recorded {len(rows)} intervals; expected {expected_steps}.")
    if len(rows) != expected_steps:
        return finish()
    incomplete = False
    for index, row in enumerate(rows):
        try:
            if not isinstance(row, dict):
                raise ValueError("Interval must be an object")
            for key in ("start_minute", "end_minute", "baseline_grid_import_mw", "grid_import_mw", "battery_charge_mw", "battery_discharge_mw", "flexible_compute_mw", "battery_soc_start", "battery_soc_end"):
                _number(row, key)
            if not any(key in row for key in ("work_served_mwh", "work_deferred_mwh", "workload_backlog_mwh")):
                raise MissingEvidence("No recorded workload ledger is available")
        except MissingEvidence as exc:
            add(f"event_{index}_required_evidence", None, str(exc)); incomplete = True
        except (TypeError, ValueError) as exc:
            add(f"event_{index}_malformed_evidence", False, str(exc)); incomplete = True
    if incomplete:
        return finish()
    cohort = bool(rows and "work_served_mwh" in rows[0])
    backlog = cap * duration / 60 if cohort else 0.0
    state_history = [(start, backlog, soc)]
    delivered_values: list[float] = []
    for index, row in enumerate(rows):
        name = f"event_{index}"
        try:
            t0, t1 = _number(row, "start_minute"), _number(row, "end_minute")
            baseline, grid = _number(row, "baseline_grid_import_mw"), _number(row, "grid_import_mw")
            charge, discharge = _number(row, "battery_charge_mw"), _number(row, "battery_discharge_mw")
            flex = _number(row, "flexible_compute_mw")
            s0, s1 = _number(row, "battery_soc_start"), _number(row, "battery_soc_end")
            noise = _number(row, "meter_noise_mw") if "meter_noise_mw" in row else 0.0
            dt = (t1 - t0) / 60
            add(name + "_timing", abs(t0 - (start + index * interval)) <= TOL and abs(t1 - t0 - interval) <= TOL,
                f"Interval {t0:g}–{t1:g} minutes; expected consecutive {interval:g}-minute steps.")
            expected_grid = critical + fixed + flex + charge - discharge + noise
            add(name + "_power_balance", abs(grid - expected_grid) <= TOL and abs(baseline - (critical + fixed + cap)) <= TOL and grid >= -TOL,
                f"Import={grid:.8g}; recomputed={expected_grid:.8g} MW; baseline={baseline:.8g} MW.")
            implied_critical = grid - noise - fixed - flex - charge + discharge
            add(name + "_critical_electrical_load", abs(implied_critical - critical) <= TOL,
                f"Implied critical electrical demand={implied_critical:.8g}; configured={critical:.8g} MW. Service quality is outside this model.")
            add(name + "_resource_limits", -TOL <= flex <= cap + TOL and -TOL <= charge <= charge_cap + TOL and -TOL <= discharge <= discharge_cap + TOL and not (charge > TOL and discharge > TOL),
                "Flexible computing and inverter limits, nonnegative powers, and charge/discharge exclusivity checked.")
            expected_soc = s0 + (charge * eff_c - discharge / eff_d) * dt / capacity
            add(name + "_battery_energy", abs(s0 - soc) <= TOL and abs(s1 - expected_soc) <= TOL and minimum - TOL <= s0 <= maximum + TOL and minimum - TOL <= s1 <= maximum + TOL,
                f"Start={s0:.8g}; prior={soc:.8g}; end={s1:.8g}; recomputed end={expected_soc:.8g}.")
            delivery = baseline - grid
            delivered_values.append(delivery)
            add(name + "_commitment", delivery >= accepted - TOL, f"Delivered={delivery:.8g}; commitment={accepted:.8g} MW.")
            if "delivered_reduction_mw" in row:
                add(name + "_delivery_record", abs(_number(row, "delivered_reduction_mw") - delivery) <= TOL, "Reported reduction compared with baseline minus grid import.")
            expected_backlog = backlog - flex * dt if cohort else backlog + (cap - flex) * dt
            work = flex * dt if cohort else (cap - flex) * dt
            work_key = "work_served_mwh" if cohort else "work_deferred_mwh"
            if work_key not in row and "workload_backlog_mwh" not in row:
                raise MissingEvidence("Missing workload ledger evidence")
            work_ok = work_key not in row or abs(_number(row, work_key) - work) <= TOL
            observed_backlog = _number(row, "workload_backlog_mwh") if "workload_backlog_mwh" in row else expected_backlog
            add(name + "_work_accounting", work_ok and expected_backlog >= -TOL and abs(observed_backlog - expected_backlog) <= TOL,
                f"Remaining/accumulated work={observed_backlog:.8g}; ledger={expected_backlog:.8g} MWh; mode={'released cohort' if cohort else 'accumulated deferral'}.")
            backlog, soc = observed_backlog, s1
            state_history.append((t1, backlog, soc))
        except MissingEvidence as exc:
            add(name + "_required_evidence", None, str(exc))
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            add(name + "_malformed_evidence", False, str(exc))

    metrics["event_min_delivered_mw"] = min(delivered_values) if delivered_values else None
    metrics["event_mean_delivered_mw"] = sum(delivered_values) / len(delivered_values) if delivered_values else None
    metrics["event_shortfall_mwh"] = sum(max(0, accepted - power) * interval / 60 for power in delivered_values)
    metrics["event_complete_evidence"] = len(delivered_values) == expected_steps
    telemetry = result.get("telemetry", {})
    for key, value in (("final_battery_soc", soc), ("final_workload_backlog_mwh", backlog)):
        try:
            add("event_" + key, abs(_number(telemetry, key) - value) <= TOL, "Summary compared with independently replayed event ledger.")
        except MissingEvidence as exc:
            add("event_" + key, None, str(exc))
        except (TypeError, ValueError) as exc:
            add("event_" + key, False, str(exc))

    recovery = result.get("recovery")
    if not isinstance(recovery, dict):
        add("recovery_evidence", None, "No RecoveryGuard evidence supplied."); return finish()
    r_telemetry = recovery.get("telemetry")
    if not isinstance(r_telemetry, dict):
        add("recovery_evidence", None, "No recovery telemetry object supplied."); return finish()
    recovery_rows = r_telemetry.get("recovery_time_series")
    if not isinstance(recovery_rows, list) or not recovery_rows:
        if recovery.get("status") in {"infeasible", "solver_error"}:
            add("recovery_execution", False, f"Recovery targets were not achieved: {recovery.get('infeasibility_reason', recovery.get('status'))}")
        else:
            add("recovery_evidence", None, "Recovery interval evidence is absent.")
        return finish()
    try:
        r_interval = _number(recovery_cfg, "interval_minutes")
        r_horizon = _number(recovery_cfg, "horizon_minutes")
        ceiling, base = _number(recovery_cfg, "grid_import_ceiling_mw"), _number(recovery_cfg, "nominal_base_demand_mw")
        target_soc = _number(recovery_cfg, "target_soc")
        soc_deadline, work_deadline = _number(recovery_cfg, "target_minute"), _number(recovery_cfg, "clear_deferred_work_by_minute")
        if r_interval <= 0 or r_horizon <= 0 or r_horizon % r_interval:
            raise ValueError("Invalid recovery interval/horizon")
        expected_r_steps = int(r_horizon / r_interval)
        add("recovery_interval_count", True if len(recovery_rows) == expected_r_steps else None if len(recovery_rows) < expected_r_steps else False,
            f"Recorded {len(recovery_rows)} intervals; expected {expected_r_steps}.")
        if len(recovery_rows) != expected_r_steps:
            return finish()
        r_header = r_telemetry
        add("event_recovery_boundary", abs(_number(r_header, "initial_battery_soc") - soc) <= TOL and abs(_number(r_header, "initial_backlog_mwh") - backlog) <= TOL,
            "Recovery initial energy/work state compared with independently replayed event final state.")
    except (KeyError, MissingEvidence) as exc:
        add("recovery_configuration", None, str(exc)); return finish()
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        add("recovery_configuration", False, str(exc)); return finish()

    incomplete = False
    for index, row in enumerate(recovery_rows):
        try:
            if not isinstance(row, dict):
                raise ValueError("Recovery interval must be an object")
            for key in ("start_minute", "end_minute", "battery_charge_mw", "workload_recovery_mw", "grid_import_mw", "base_demand_mw", "battery_soc_start", "battery_soc_end", "workload_backlog_start_mwh", "workload_backlog_end_mwh"):
                _number(row, key)
        except MissingEvidence as exc:
            add(f"recovery_{index}_required_evidence", None, str(exc)); incomplete = True
        except (TypeError, ValueError) as exc:
            add(f"recovery_{index}_malformed_evidence", False, str(exc)); incomplete = True
    if incomplete:
        return finish()

    imports: list[float] = []
    for index, row in enumerate(recovery_rows):
        name = f"recovery_{index}"
        try:
            t0, t1 = _number(row, "start_minute"), _number(row, "end_minute")
            charge, work = _number(row, "battery_charge_mw"), _number(row, "workload_recovery_mw")
            grid, reported_base = _number(row, "grid_import_mw"), _number(row, "base_demand_mw")
            s0, s1 = _number(row, "battery_soc_start"), _number(row, "battery_soc_end")
            b0, b1 = _number(row, "workload_backlog_start_mwh"), _number(row, "workload_backlog_end_mwh")
            dt = (t1 - t0) / 60
            add(name + "_timing", abs(t0 - (start + duration + index * r_interval)) <= TOL and abs(t1 - t0 - r_interval) <= TOL, "Consecutive recovery interval timing checked.")
            add(name + "_shared_import", abs(reported_base - base) <= TOL and abs(grid - (base + work + charge)) <= TOL and -TOL <= grid <= ceiling + TOL and -TOL <= work <= cap + TOL and -TOL <= charge <= charge_cap + TOL,
                f"Import={grid:.8g}; shared ceiling={ceiling:.8g}; base+work+charge={base+work+charge:.8g} MW.")
            expected_soc, expected_backlog = s0 + charge * eff_c * dt / capacity, b0 - work * dt
            add(name + "_battery_energy", abs(s0 - soc) <= TOL and abs(s1 - expected_soc) <= TOL and minimum - TOL <= s0 <= maximum + TOL and minimum - TOL <= s1 <= maximum + TOL,
                f"SoC={s1:.8g}; recomputed={expected_soc:.8g}.")
            add(name + "_work_accounting", abs(b0 - backlog) <= TOL and expected_backlog >= -TOL and b1 >= -TOL and abs(b1 - expected_backlog) <= TOL,
                f"Backlog={b1:.8g}; recomputed={expected_backlog:.8g} MWh.")
            soc, backlog = s1, b1
            imports.append(grid)
            state_history.append((t1, backlog, soc))
        except MissingEvidence as exc:
            add(name + "_required_evidence", None, str(exc))
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            add(name + "_malformed_evidence", False, str(exc))

    def at_deadline(deadline: float):
        return next((state for state in state_history if abs(state[0] - deadline) <= TOL), None)

    soc_state, work_state = at_deadline(soc_deadline), at_deadline(work_deadline)
    add("battery_restoration_deadline", None if soc_state is None else soc_state[2] + TOL >= target_soc,
        f"Required SoC {target_soc:g} by minute {soc_deadline:g}; state={soc_state}.")
    add("aggregate_work_deadline", None if work_state is None else work_state[1] <= TOL,
        f"Backlog must be zero by minute {work_deadline:g}; state={work_state}.")
    try:
        workloads = config.get("workloads", {})
        if not isinstance(workloads, dict):
            raise ValueError("workloads must be an object")
        workload_deadline = start + (_number(workloads, "max_deferral_minutes") if "max_deferral_minutes" in workloads else work_deadline - start)
    except (TypeError, ValueError) as exc:
        add("configured_workload_deadline", False, str(exc)); return finish()
    if workload_deadline < work_deadline:
        state = at_deadline(workload_deadline)
        add("earlier_workload_deadline", None if state is None else state[1] <= TOL, f"Configured workload deadline={workload_deadline:g}; state={state}.")
    metrics.update(recovery_max_grid_import_mw=max(imports) if imports else None,
                   final_battery_soc=soc, final_workload_backlog_mwh=backlog)
    return finish()
