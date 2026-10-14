"""Transparent event controller: flexible compute first, then battery."""
from __future__ import annotations
from typing import Any
from simulator.battery import Battery
from simulator.engine import _models, run_nominal_event
from simulator.facility import Facility

def allocate_reduction(facility: Facility, battery: Battery, requested_mw: float, duration_minutes: int) -> dict:
    if duration_minutes <= 0 or requested_mw < 0:
        raise ValueError("invalid request")
    compute_reduction = min(requested_mw, facility.deferrable_compute_mw)
    residual = max(0.0, requested_mw - compute_reduction)
    energy_limited = battery.usable_ac_energy_mwh() / (duration_minutes / 60.0)
    discharge = min(residual, battery.max_discharge_mw, energy_limited)
    return {
        "flexible_compute_mw": facility.deferrable_compute_mw - compute_reduction,
        "compute_reduction_mw": compute_reduction,
        "battery_discharge_mw": discharge,
        "nominal_deliverable_mw": compute_reduction + discharge,
        "shortfall_mw": max(0.0, requested_mw - compute_reduction - discharge),
    }

def run_rule_based(config: dict[str, Any], accepted_commitment_mw: float | None = None) -> dict:
    event_cfg = config["grid_event"]
    commitment = event_cfg["requested_reduction_mw"] if accepted_commitment_mw is None else accepted_commitment_mw
    facility, battery, _ = _models(config, commitment)
    plan = allocate_reduction(facility, battery, commitment, event_cfg["duration_minutes"])
    result = run_nominal_event(config, accepted_commitment_mw=commitment,
        flexible_compute_mw=plan["flexible_compute_mw"], battery_discharge_mw=plan["battery_discharge_mw"])
    result["controller"] = "rule_based"
    result["controller_version"] = "rule-based-0.1.0"
    result["dispatch_plan"] = plan
    return result
