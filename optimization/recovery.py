"""RecoveryGuard: joint workload and battery restoration under one import ceiling."""
from __future__ import annotations
from hashlib import sha256
from math import ceil, isfinite
from time import perf_counter
from typing import Any
import json
import pyomo.environ as pyo


def plan_recovery(config: dict[str, Any], *, backlog_mwh: float, current_soc: float,
                  start_minute: int | None = None, solver_time_limit_seconds: float = 30.0) -> dict:
    rcfg=config["recovery"]
    bcfg=config["battery"]
    fcfg=config["facility"]
    interval=int(rcfg["interval_minutes"])
    horizon=int(rcfg["horizon_minutes"])
    base=float(rcfg["nominal_base_demand_mw"])
    ceiling=float(rcfg["grid_import_ceiling_mw"])
    t_start=(int(config["grid_event"]["start_minute"])+int(config["grid_event"]["duration_minutes"])
             if start_minute is None else int(start_minute))
    target_minute=int(rcfg.get("target_minute",t_start+horizon))
    clear_minute=int(rcfg.get("clear_deferred_work_by_minute",target_minute))
    target_soc=float(rcfg["target_soc"])
    scenario=config["scenario_id"]
    tol=1e-9
    if not isfinite(backlog_mwh) or backlog_mwh < 0:
        raise ValueError("backlog_mwh must be finite and nonnegative")
    if not isfinite(current_soc) or not float(bcfg["min_soc"]) <= current_soc <= float(bcfg["max_soc"]):
        raise ValueError("current_soc outside battery limits")
    if interval <= 0 or horizon <= 0 or horizon % interval:
        raise ValueError("recovery horizon must be a positive multiple of its interval")
    if not all(isfinite(x) for x in (base,ceiling,target_soc,solver_time_limit_seconds)):
        raise ValueError("recovery settings must be finite")
    if ceiling < base or target_soc < float(bcfg["min_soc"]) or target_soc > float(bcfg["max_soc"]):
        raise ValueError("invalid recovery grid ceiling or target SoC")
    if solver_time_limit_seconds <= 0:
        raise ValueError("solver_time_limit_seconds must be positive")
    n=horizon//interval
    end_minute=t_start+horizon
    if target_minute > end_minute or clear_minute > end_minute:
        return _infeasible(config,backlog_mwh,current_soc,"Recovery targets fall beyond the configured horizon.")
    dt=interval/60.0
    target_index=max(0,min(n,ceil((target_minute-t_start)/interval)))
    clear_index=max(0,min(n,ceil((clear_minute-t_start)/interval)))
    headroom=ceiling-base
    work_cap=float(fcfg["deferrable_compute_mw"])
    model=pyo.ConcreteModel()
    model.T=pyo.RangeSet(0,n-1)
    model.S=pyo.RangeSet(0,n)
    model.work=pyo.Var(model.T,bounds=(0.0,work_cap))
    model.charge=pyo.Var(model.T,bounds=(0.0,float(bcfg["max_charge_mw"])))
    model.backlog=pyo.Var(model.S,bounds=(0.0,backlog_mwh))
    model.soc=pyo.Var(model.S,bounds=(float(bcfg["min_soc"]),float(bcfg["max_soc"])))
    model.import_power=pyo.Var(model.T,bounds=(base,ceiling))
    model.peak=pyo.Var(bounds=(base,ceiling))
    model.ramp=pyo.Var(model.T,domain=pyo.NonNegativeReals)
    model.initial_backlog=pyo.Constraint(expr=model.backlog[0]==backlog_mwh)
    model.initial_soc=pyo.Constraint(expr=model.soc[0]==current_soc)
    model.backlog_balance=pyo.Constraint(model.T,
        rule=lambda m,t:m.backlog[t+1]==m.backlog[t]-m.work[t]*dt)
    model.soc_balance=pyo.Constraint(model.T,
        rule=lambda m,t:m.soc[t+1]==m.soc[t]+m.charge[t]*float(bcfg["charge_efficiency"])*dt/float(bcfg["capacity_mwh"]))
    # Both restored compute and charge consume the same headroom.
    model.shared_capacity=pyo.Constraint(model.T,rule=lambda m,t:m.work[t]+m.charge[t]<=headroom)
    model.import_balance=pyo.Constraint(model.T,rule=lambda m,t:m.import_power[t]==base+m.work[t]+m.charge[t])
    model.peak_limit=pyo.Constraint(model.T,rule=lambda m,t:m.peak>=m.import_power[t])
    model.deadline_clear=pyo.Constraint(expr=model.backlog[clear_index]<=tol)
    model.soc_target=pyo.Constraint(expr=model.soc[target_index]>=target_soc)
    model.final_clear=pyo.Constraint(expr=model.backlog[n]<=tol)
    model.ramp_up=pyo.Constraint(model.T,rule=lambda m,t:m.ramp[t]>=m.import_power[t]-(base if t==0 else m.import_power[t-1]))
    model.ramp_down=pyo.Constraint(model.T,rule=lambda m,t:m.ramp[t]>=(base if t==0 else m.import_power[t-1])-m.import_power[t])
    model.objective=pyo.Objective(expr=1000*model.peak+sum(model.ramp[t] for t in model.T),sense=pyo.minimize)
    solver=pyo.SolverFactory("appsi_highs")
    solver.options["time_limit"]=solver_time_limit_seconds
    started=perf_counter()
    try:
        # Request the termination condition before loading a solution. Pyomo's
        # default solution loading raises for infeasible models, which would
        # otherwise mislabel a genuine planning infeasibility as solver_error.
        result=solver.solve(model, load_solutions=False)
    except Exception as exc:
        return _solver_error(config,backlog_mwh,current_soc,str(exc),perf_counter()-started)
    runtime=perf_counter()-started
    termination=str(result.solver.termination_condition)
    if termination=="infeasible":
        return _infeasible(config,backlog_mwh,current_soc,
                           "No schedule clears backlog and restores SoC within the shared grid ceiling.",
                           runtime=runtime,termination=termination)
    if result.solver.status not in (pyo.SolverStatus.ok,pyo.SolverStatus.warning) or termination!="optimal":
        return _solver_error(config,backlog_mwh,current_soc,f"HiGHS termination: {termination}",
                             runtime=runtime,termination=termination)
    try:
        model.solutions.load_from(result)
    except Exception as exc:
        return _solver_error(config,backlog_mwh,current_soc,
                             f"Unable to load optimal HiGHS solution: {exc}",
                             runtime=runtime,termination=termination)
    rows=[]
    for t in range(n):
        rows.append({"step":t,"start_minute":t_start+t*interval,"end_minute":t_start+(t+1)*interval,
            "base_demand_mw":base,"workload_recovery_mw":pyo.value(model.work[t]),
            "battery_charge_mw":pyo.value(model.charge[t]),"grid_import_mw":pyo.value(model.import_power[t]),
            "battery_soc_start":pyo.value(model.soc[t]),"battery_soc_end":pyo.value(model.soc[t+1]),
            "workload_backlog_start_mwh":pyo.value(model.backlog[t]),
            "workload_backlog_end_mwh":pyo.value(model.backlog[t+1])})
    final_soc=pyo.value(model.soc[n])
    final_backlog=pyo.value(model.backlog[n])
    max_import=max(row["grid_import_mw"] for row in rows)
    signature=json.dumps({"scenario":scenario,"backlog":backlog_mwh,"soc":current_soc},sort_keys=True)
    return {"schema_version":"1.0.0","scenario_id":scenario,
        "run_id":f"{scenario}-recovery-{sha256(signature.encode()).hexdigest()[:10]}",
        "controller":"recovery_guard","controller_version":"recovery-guard-0.1.0",
        "status":"completed","execution_status":"recovery_complete",
        "accepted_commitment_mw":None,"infeasibility_reason":None,
        "reliability":None,"complete_event_success":None,
        "telemetry":{"recovery_time_series":rows,"initial_backlog_mwh":backlog_mwh,
            "final_workload_backlog_mwh":final_backlog,"initial_battery_soc":current_soc,
            "final_battery_soc":final_soc,"max_grid_import_mw":max_import,
            "grid_import_ceiling_mw":ceiling,"shared_headroom_mw":headroom,
            "backlog_cleared":final_backlog<=tol,"soc_target_met":final_soc+tol>=target_soc},
        "violations":[],"solver_metadata":{"solver":"HiGHS","termination":termination,
            "runtime_seconds":runtime,"objective":pyo.value(model.objective)},
        "random_seed":config.get("random_seed",0),
        "assumptions":rcfg.get("assumptions",[])}


def _infeasible(config,backlog,soc,reason,runtime=0.0,termination="infeasible"):
    return {"schema_version":"1.0.0","scenario_id":config.get("scenario_id","unknown"),
        "run_id":f"{config.get('scenario_id','unknown')}-recovery-infeasible",
        "controller":"recovery_guard","controller_version":"recovery-guard-0.1.0",
        "status":"infeasible","execution_status":"infeasible",
        "accepted_commitment_mw":None,"infeasibility_reason":reason,"reliability":None,
        "telemetry":{"recovery_time_series":[],"initial_backlog_mwh":backlog,
            "final_workload_backlog_mwh":backlog,"initial_battery_soc":soc},
        "violations":[{"type":"recovery_infeasible","reason":reason}],
        "solver_metadata":{"solver":"HiGHS","termination":termination,"runtime_seconds":runtime},
        "random_seed":config.get("random_seed",0)}


def _solver_error(config,backlog,soc,reason,runtime=0.0,termination=None):
    result=_infeasible(config,backlog,soc,reason,runtime,termination or "solver_error")
    result["status"]="solver_error"
    result["execution_status"]="solver_error"
    result["violations"]=[{"type":"solver_error","reason":reason}]
    return result
