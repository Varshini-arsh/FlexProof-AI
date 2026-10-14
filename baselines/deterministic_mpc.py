"""Finite-horizon deterministic event dispatch using Pyomo and HiGHS."""
from __future__ import annotations
from math import isfinite
from time import perf_counter
from typing import Any
import pyomo.environ as pyo
from simulator.engine import _models

TOL = 1e-7

def _solver_failure(config: dict, commitment: float, reason: str, runtime: float, termination: str | None = None) -> dict:
    return {
        "schema_version": "1.0.0", "scenario_id": config["scenario_id"],
        "run_id": f"{config['scenario_id']}-deterministic-mpc-error",
        "controller": "deterministic_mpc", "controller_version": "pyomo-highs-0.1.0",
        "status": "solver_error", "execution_status": "solver_error",
        "accepted_commitment_mw": commitment, "infeasibility_reason": reason,
        "reliability": None, "telemetry": {"event_time_series": []},
        "violations": [{"type": "solver_error", "reason": reason}],
        "solver_metadata": {"solver": "HiGHS", "termination": termination, "runtime_seconds": runtime},
        "random_seed": config.get("random_seed", 0),
    }

def solve_deterministic_dispatch(config: dict[str, Any], accepted_commitment_mw: float | None = None,
                                 *, time_limit_seconds: float = 30.0) -> dict:
    """Optimize event dispatch; recovery and uncertainty are outside this MPC."""
    event_cfg = config["grid_event"]
    commitment = event_cfg["requested_reduction_mw"] if accepted_commitment_mw is None else accepted_commitment_mw
    facility, battery, event = _models(config, commitment)
    if not isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be finite and positive")
    n, dt = event.steps, event.interval_minutes / 60.0
    cap, baseline = facility.deferrable_compute_mw, facility.baseline_grid_import_mw
    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(0, n - 1)
    model.S = pyo.RangeSet(0, n)
    model.flexible_run = pyo.Var(model.T, bounds=(0.0, cap))
    model.discharge = pyo.Var(model.T, bounds=(0.0, battery.max_discharge_mw))
    model.soc = pyo.Var(model.S, bounds=(battery.min_soc, battery.max_soc))
    model.shortfall = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.initial_soc = pyo.Constraint(expr=model.soc[0] == battery.initial_soc)
    model.soc_balance = pyo.Constraint(
        model.T,
        rule=lambda m,t: m.soc[t+1] == m.soc[t] -
          m.discharge[t] / battery.discharge_efficiency * dt / battery.capacity_mwh)
    model.delivery = pyo.Constraint(
        model.T,
        rule=lambda m,t: m.shortfall[t] >= commitment - (cap - m.flexible_run[t] + m.discharge[t]))
    model.objective = pyo.Objective(
        expr=1_000_000 * sum(model.shortfall[t] * dt for t in model.T)
        + sum((cap-model.flexible_run[t]) * dt for t in model.T)
        + 10 * sum(model.discharge[t] * dt for t in model.T),
        sense=pyo.minimize)

    solver = pyo.SolverFactory("appsi_highs")
    solver.options["time_limit"] = time_limit_seconds
    started = perf_counter()
    try:
        result = solver.solve(model)
    except Exception as exc:
        return _solver_failure(config, commitment, str(exc), perf_counter()-started)
    runtime = perf_counter()-started
    termination = str(result.solver.termination_condition)
    if result.solver.status not in (pyo.SolverStatus.ok,pyo.SolverStatus.warning) or termination != "optimal":
        return _solver_failure(config, commitment, f"HiGHS termination: {termination}", runtime, termination)

    soc = battery.initial_soc
    rows,violations=[],[]
    for t in range(n):
        flex=pyo.value(model.flexible_run[t])
        discharge=pyo.value(model.discharge[t])
        next_soc=pyo.value(model.soc[t+1])
        delivered=cap-flex+discharge
        shortfall=max(0.0,commitment-delivered)
        if shortfall>TOL:
            violations.append({"type":"event_shortfall","step":t,"shortfall_mw":shortfall})
        grid=facility.grid_import_mw(flexible_compute_mw=flex,battery_discharge_mw=discharge)
        rows.append({"step":t,"start_minute":event.start_minute+t*event.interval_minutes,
            "end_minute":event.start_minute+(t+1)*event.interval_minutes,
            "baseline_grid_import_mw":baseline,"grid_import_mw":grid,
            "accepted_commitment_mw":commitment,"delivered_reduction_mw":baseline-grid,
            "shortfall_mw":shortfall,"success":shortfall<=TOL,"flexible_compute_mw":flex,
            "work_deferred_mwh":(cap-flex)*dt,"battery_charge_mw":0.0,
            "battery_discharge_mw":discharge,"battery_soc_start":soc,"battery_soc_end":next_soc})
        soc=next_soc
    complete=not violations and len(rows)==n
    return {"schema_version":"1.0.0","scenario_id":config["scenario_id"],
        "run_id":f"{config['scenario_id']}-deterministic-mpc","controller":"deterministic_mpc",
        "controller_version":"pyomo-highs-0.1.0","status":"completed" if complete else "infeasible",
        "execution_status":"nominal_success" if complete else "constraint_violation",
        "accepted_commitment_mw":commitment,
        "commitment_basis":"deterministic nominal optimization; not reliability-certified",
        "infeasibility_reason":None if complete else "Modeled resources cannot meet the commitment in every interval.",
        "reliability":{"status":"not_evaluated","estimate":None,"sample_count":0,
            "confidence_lower_bound":None,"target":event_cfg.get("target_complete_event_success_probability")},
        "complete_event_success":complete,
        "telemetry":{"baseline_grid_import_mw":baseline,"event_time_series":rows,
            "final_battery_soc":soc,"final_workload_backlog_mwh":sum(r["work_deferred_mwh"] for r in rows)},
        "violations":violations,
        "solver_metadata":{"solver":"HiGHS","termination":termination,"runtime_seconds":runtime,
            "objective":pyo.value(model.objective)},
        "random_seed":config.get("random_seed",0),
        "assumptions":config.get("recovery",{}).get("assumptions",[])}
