"""Reproducible nominal event simulator; this is not a reliability certification."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import yaml

from simulator.battery import Battery
from simulator.facility import Facility
from simulator.grid import GridEvent
from simulator.workloads import Job, WorkloadQueue

SCHEMA_VERSION = "1.0.0"
CONTROLLER_VERSION = "nominal-illustration-0.1.0"
TOL = 1e-9


def load_config(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return json.loads(json.dumps(source))
    with Path(source).open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("scenario configuration must be a YAML/JSON object")
    return config


def _models(config: dict[str, Any], accepted_commitment_mw: float):
    facility_cfg = config["facility"]
    battery_cfg = config["battery"]
    event_cfg = config["grid_event"]
    facility = Facility(facility_cfg["critical_inference_mw"],
                        facility_cfg["fixed_auxiliary_mw"],
                        facility_cfg["deferrable_compute_mw"])
    battery = Battery(**battery_cfg)
    event = GridEvent(event_cfg["start_minute"], event_cfg["requested_reduction_mw"],
                      event_cfg["duration_minutes"], event_cfg["interval_minutes"],
                      accepted_commitment_mw)
    return facility, battery, event


def run_nominal_event(config_source: str | Path | dict[str, Any], *,
                      accepted_commitment_mw: float | None = None,
                      flexible_compute_mw: float | None = None,
                      battery_discharge_mw: float | None = None) -> dict[str, Any]:
    """Execute a constant nominal dispatch and return JSON-compatible telemetry.

    The default 0.4 MW flexible load plus 1.4 MW battery discharge is an
    illustrative 5 MW reduction against the 20 MW baseline. It carries no
    statistical reliability claim.
    """
    config = load_config(config_source)
    event_cfg = config["grid_event"]
    requested = event_cfg["requested_reduction_mw"]
    commitment = requested if accepted_commitment_mw is None else accepted_commitment_mw
    facility, battery, event = _models(config, commitment)
    flex_cap = facility.deferrable_compute_mw
    battery_discharge_mw = min(1.4, commitment, battery.max_discharge_mw) if battery_discharge_mw is None else battery_discharge_mw
    flex_power = flex_cap - max(0.0, commitment - battery_discharge_mw) if flexible_compute_mw is None else flexible_compute_mw
    if not 0 <= flex_power <= flex_cap + TOL:
        raise ValueError("flexible_compute_mw must be within facility capability")
    if battery_discharge_mw < 0:
        raise ValueError("battery_discharge_mw must be nonnegative")

    interval = event.interval_minutes
    total_job_work = flex_cap * event.duration_minutes / 60.0
    queue = WorkloadQueue([Job(
        job_id="fp001-flexible-cohort",
        arrival_minute=event.start_minute,
        remaining_work_mwh=total_job_work,
        max_power_mw=flex_cap,
        deadline_minute=event.start_minute + int(config.get("workloads", {}).get("max_deferral_minutes", 300)),
        max_deferral_minutes=int(config.get("workloads", {}).get("max_deferral_minutes", 300)),
    )])
    soc = battery.initial_soc
    series = []
    violations = []
    baseline = facility.baseline_grid_import_mw
    for index in range(event.steps):
        start = event.start_minute + index * interval
        end = start + interval
        work = queue.dispatch(available_power_mw=flex_power, start_minute=start,
                              interval_minutes=interval)
        try:
            soc_next = battery.step(soc, discharge_mw=battery_discharge_mw,
                                    timestep_hours=interval / 60.0)
        except ValueError as exc:
            violations.append({"type": "battery_constraint", "minute": start, "reason": str(exc)})
            break
        grid_import = facility.grid_import_mw(
            flexible_compute_mw=work["power_mw"],
            battery_discharge_mw=battery_discharge_mw)
        delivery = event.assess_delivery(baseline_mw=baseline, grid_import_mw=grid_import)
        if not delivery["success"]:
            violations.append({"type": "event_shortfall", "minute": start,
                               "shortfall_mw": delivery["shortfall_mw"]})
        series.append({
            "step": index, "start_minute": start, "end_minute": end,
            "baseline_grid_import_mw": baseline, "grid_import_mw": grid_import,
            "accepted_commitment_mw": commitment,
            **delivery,
            "flexible_compute_mw": work["power_mw"],
            "battery_charge_mw": 0.0, "battery_discharge_mw": battery_discharge_mw,
            "battery_soc_start": soc, "battery_soc_end": soc_next,
            "work_served_mwh": work["work_mwh"], "workload_backlog_mwh": work["backlog_mwh"],
            "jobs": work["jobs"],
        })
        soc = soc_next

    complete = (len(series) == event.steps and all(row["success"] for row in series)
                and not violations and not queue.violations)
    signature = {"config": config, "commitment": commitment, "flexible_compute_mw": flex_power,
                 "battery_discharge_mw": battery_discharge_mw}
    run_id = f"{config['scenario_id']}-{sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:12]}"
    reason = None if complete else "One or more event delivery or physical constraints failed."
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": config["scenario_id"],
        "run_id": run_id,
        "controller": "nominal_illustration",
        "controller_version": CONTROLLER_VERSION,
        "status": "completed" if len(series) == event.steps else "infeasible",
        "execution_status": "nominal_success" if complete else "constraint_violation",
        "accepted_commitment_mw": commitment,
        "commitment_basis": "single deterministic nominal dispatch; not reliability-certified",
        "infeasibility_reason": reason,
        "reliability": {"status": "not_evaluated", "estimate": None,
                        "target": event_cfg.get("target_complete_event_success_probability"),
                        "sample_count": 0, "confidence_lower_bound": None},
        "complete_event_success": complete,
        "telemetry": {
            "baseline_grid_import_mw": baseline,
            "event_time_series": series,
            "final_battery_soc": soc,
            "final_workload_backlog_mwh": queue.backlog_mwh,
            "workloads": queue.snapshot(),
            "workload_violations": queue.violations,
        },
        "violations": violations,
        "solver_metadata": {"solver": None, "optimization_used": False},
        "random_seed": config.get("random_seed", 0),
        "assumptions": config.get("recovery", {}).get("assumptions", []),
    }
