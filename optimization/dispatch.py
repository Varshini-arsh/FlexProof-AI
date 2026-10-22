"""Receding-horizon event dispatch for RAFC-V."""
from __future__ import annotations
from hashlib import sha256
import json
from math import isfinite
from time import perf_counter
from typing import Any

import pyomo.environ as pyo

from simulator.battery import Battery
from simulator.facility import Facility
from simulator.grid import GridEvent

TOL=1e-7


def solve_rolling_event_dispatch(config: dict[str,Any], accepted_commitment_mw: float, *,
        observations: list[dict[str,float]] | None = None,
        delivery_margin_mw: float = 0.0, time_limit_seconds: float = 30.0) -> dict:
    """Re-optimize the remaining event horizon and apply only each first action.

    Observation keys: ``available_flexible_compute_mw`` (maximum curtailment),
    ``battery_discharge_scale`` (0..1), ``critical_power_delta_mw`` (common-mode
    baseline/load change), and ``meter_noise_mw``. Future observations are
    unknown to each solve; future capability forecasts use nominal limits.
    """
    fcfg=config["facility"]
    bcfg=config["battery"]
    ecfg=config["grid_event"]
    facility=Facility(fcfg["critical_inference_mw"],fcfg["fixed_auxiliary_mw"],fcfg["deferrable_compute_mw"])
    battery=Battery(**bcfg)
    event=GridEvent(ecfg["start_minute"],ecfg["requested_reduction_mw"],
        ecfg["duration_minutes"],ecfg["interval_minutes"],accepted_commitment_mw)
    if not isfinite(delivery_margin_mw) or delivery_margin_mw<0:
        raise ValueError("delivery_margin_mw must be finite and nonnegative")
    if not isfinite(time_limit_seconds) or time_limit_seconds<=0:
        raise ValueError("time_limit_seconds must be finite and positive")
    obs=observations or [{} for _ in range(event.steps)]
    if len(obs)!=event.steps or any(not isinstance(x,dict) for x in obs):
        raise ValueError("observations must contain one mapping per event interval")
    for index,item in enumerate(obs):
        available=float(item.get("available_flexible_compute_mw",facility.deferrable_compute_mw))
        scale=float(item.get("battery_discharge_scale",1.0))
        if not isfinite(available) or not 0<=available<=facility.deferrable_compute_mw:
            raise ValueError(f"observation {index}: available flexible compute is outside facility limits")
        if not isfinite(scale) or not 0<=scale<=1:
            raise ValueError(f"observation {index}: battery discharge scale must be in [0,1]")
        for key in ("critical_power_delta_mw","meter_noise_mw","initial_soc_error"):
            if key in item and not isfinite(float(item[key])):
                raise ValueError(f"observation {index}: {key} must be finite")

    recovery=config["recovery"]
    interval=int(event.interval_minutes)
    dt=interval/60.0
    n=event.steps
    base=facility.baseline_grid_import_mw
    backlog=0.0
    soc=battery.initial_soc+float(obs[0].get("initial_soc_error",0.0))
    if not battery.min_soc<=soc<=battery.max_soc:
        return _failure(config,accepted_commitment_mw,"infeasible",
            "Observed initial battery SoC is outside protected operating limits.",[],[],[],0.0)
    rows=[]
    violations=[]
    solver_times=[]
    objectives=[]
    terminations=[]
    recovery_headroom=float(recovery["grid_import_ceiling_mw"])-float(recovery["nominal_base_demand_mw"])
    event_end=event.start_minute+event.duration_minutes
    clear_minute=int(recovery.get("clear_deferred_work_by_minute",recovery.get("target_minute",event_end+int(recovery["horizon_minutes"]))))
    target_minute=int(recovery.get("target_minute",event_end+int(recovery["horizon_minutes"])))
    clear_hours=max(0.0,(clear_minute-event_end)/60.0)
    target_hours=max(0.0,(target_minute-event_end)/60.0)
    combined_hours=max(clear_hours,target_hours)
    target_soc=float(recovery["target_soc"])

    for current in range(n):
        remaining=n-current
        model=pyo.ConcreteModel()
        model.T=pyo.RangeSet(0,remaining-1)
        model.S=pyo.RangeSet(0,remaining)
        model.curtail=pyo.Var(model.T,domain=pyo.NonNegativeReals)
        model.discharge=pyo.Var(model.T,domain=pyo.NonNegativeReals)
        model.soc=pyo.Var(model.S,bounds=(battery.min_soc,battery.max_soc))
        model.backlog=pyo.Var(model.S,domain=pyo.NonNegativeReals)
        model.recovery_charge=pyo.Var(domain=pyo.NonNegativeReals)
        model.shortfall=pyo.Var(model.T,domain=pyo.NonNegativeReals)
        model.start_soc=pyo.Constraint(expr=model.soc[0]==soc)
        model.start_backlog=pyo.Constraint(expr=model.backlog[0]==backlog)
        caps=[]
        discharge_caps=[]
        floors=[]
        delivery_targets=[]
        for offset in range(remaining):
            if offset==0:
                observed=obs[current]
                caps.append(float(observed.get("available_flexible_compute_mw",facility.deferrable_compute_mw)))
                discharge_caps.append(battery.max_discharge_mw*float(observed.get("battery_discharge_scale",1.0)))
                critical_delta=float(observed.get("critical_power_delta_mw",0.0))
                floors.append(base+critical_delta)
                delivery_targets.append(accepted_commitment_mw+delivery_margin_mw
                    +float(observed.get("meter_noise_mw",0.0)))
            else:
                caps.append(facility.deferrable_compute_mw)
                discharge_caps.append(battery.max_discharge_mw)
                floors.append(base)
                delivery_targets.append(accepted_commitment_mw+delivery_margin_mw)
        model.curtail_cap=pyo.Constraint(model.T,rule=lambda m,t:m.curtail[t]<=caps[t])
        model.discharge_cap=pyo.Constraint(model.T,rule=lambda m,t:m.discharge[t]<=discharge_caps[t])
        model.soc_balance=pyo.Constraint(model.T,rule=lambda m,t:m.soc[t+1]==m.soc[t]
            -m.discharge[t]/battery.discharge_efficiency*dt/battery.capacity_mwh)
        model.backlog_balance=pyo.Constraint(model.T,rule=lambda m,t:m.backlog[t+1]==m.backlog[t]+m.curtail[t]*dt)
        model.delivery=pyo.Constraint(model.T,rule=lambda m,t:m.shortfall[t]>=
            delivery_targets[t]-m.curtail[t]-m.discharge[t])
        model.grid_floor=pyo.Constraint(model.T,rule=lambda m,t:
            m.curtail[t]+m.discharge[t]<=floors[t])
        # The ending event state must admit one joint RecoveryGuard schedule.
        work_limit=min(facility.deferrable_compute_mw,max(0.0,recovery_headroom))*clear_hours
        charge_power_limit=min(battery.max_charge_mw,max(0.0,recovery_headroom))*target_hours
        model.recovery_work_rate=pyo.Constraint(expr=model.backlog[remaining]<=work_limit)
        model.recovery_charge_rate=pyo.Constraint(expr=model.soc[remaining]>=target_soc
            -charge_power_limit*battery.charge_efficiency/battery.capacity_mwh)
        model.recovery_charge_required=pyo.Constraint(expr=model.recovery_charge>=
            (target_soc-model.soc[remaining])*battery.capacity_mwh/battery.charge_efficiency)
        model.recovery_charge_cap=pyo.Constraint(expr=model.recovery_charge<=charge_power_limit*target_hours)
        if recovery_headroom<0 or combined_hours<0:
            model.recovery_shared=pyo.Constraint(expr=model.backlog[remaining]<=-1.0)
        else:
            model.recovery_shared=pyo.Constraint(expr=model.backlog[remaining]+model.recovery_charge
                <=recovery_headroom*combined_hours)
        model.objective=pyo.Objective(expr=1_000_000*sum(model.shortfall[t]*dt for t in model.T)
            +sum(model.curtail[t]*dt for t in model.T)
            +10*sum(model.discharge[t]*dt for t in model.T)
            +0.001*model.recovery_charge,sense=pyo.minimize)
        solver=pyo.SolverFactory("appsi_highs")
        solver.options["time_limit"]=time_limit_seconds
        started=perf_counter()
        try:
            result=solver.solve(model,load_solutions=False)
        except Exception as exc:
            return _error(config,accepted_commitment_mw,str(exc),rows,violations,solver_times,perf_counter()-started)
        solve_time=perf_counter()-started
        termination=str(result.solver.termination_condition)
        terminations.append(termination)
        solver_times.append(solve_time)
        if termination=="infeasible":
            return _infeasible(config,accepted_commitment_mw,rows,violations,solver_times,
                               f"Rolling dispatch infeasible at event step {current}.",termination)
        if result.solver.status not in (pyo.SolverStatus.ok,pyo.SolverStatus.warning) or termination!="optimal":
            return _error(config,accepted_commitment_mw,f"HiGHS termination: {termination}",
                          rows,violations,solver_times,solve_time,termination)
        try:
            model.solutions.load_from(result)
        except Exception as exc:
            return _error(config,accepted_commitment_mw,f"Unable to load solution: {exc}",
                          rows,violations,solver_times,solve_time,termination)
        objectives.append(float(pyo.value(model.objective)))
        curtail=float(pyo.value(model.curtail[0]))
        discharge=float(pyo.value(model.discharge[0]))
        soc_next=float(pyo.value(model.soc[1]))
        item=obs[current]
        critical_delta=float(item.get("critical_power_delta_mw",0.0))
        meter_noise=float(item.get("meter_noise_mw",0.0))
        baseline=base+critical_delta
        grid=baseline-curtail-discharge
        if grid < -TOL:
            return _error(config,accepted_commitment_mw,"dispatch would export power",rows,violations,
                          solver_times,solve_time,termination)
        delivered=curtail+discharge-meter_noise
        shortfall=max(0.0,accepted_commitment_mw-delivered)
        if shortfall>TOL:
            violations.append({"type":"event_shortfall","step":current,"shortfall_mw":shortfall})
        backlog_next=backlog+curtail*dt
        rows.append({"step":current,"start_minute":event.start_minute+current*interval,
            "end_minute":event.start_minute+(current+1)*interval,
            "baseline_grid_import_mw":baseline,"grid_import_mw":max(0.0,grid),
            "accepted_commitment_mw":accepted_commitment_mw,
            "delivered_reduction_mw":delivered,"shortfall_mw":shortfall,"success":shortfall<=TOL,
            "flexible_compute_mw":facility.deferrable_compute_mw-curtail,
            "flexible_compute_curtailment_mw":curtail,"work_deferred_mwh":curtail*dt,
            "workload_backlog_mwh":backlog_next,"battery_charge_mw":0.0,
            "battery_discharge_mw":discharge,"battery_soc_start":soc,"battery_soc_end":soc_next,
            "observed_flexible_capacity_mw":caps[0],"observed_battery_discharge_limit_mw":discharge_caps[0],
            "meter_noise_mw":meter_noise})
        soc=soc_next
        backlog=backlog_next

    complete=len(rows)==n and not violations
    signature={"scenario":config["scenario_id"],"commitment":accepted_commitment_mw,
               "observations":obs,"delivery_margin_mw":delivery_margin_mw}
    run_id=f"{config['scenario_id']}-rolling-{sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()[:12]}"
    return {"schema_version":"1.0.0","scenario_id":config["scenario_id"],"run_id":run_id,
        "controller":"rolling_mpc","controller_version":"rolling-mpc-0.1.0",
        "status":"completed" if complete else "infeasible",
        "execution_status":"nominal_success" if complete else "constraint_violation",
        "accepted_commitment_mw":accepted_commitment_mw,
        "commitment_basis":"rolling Pyomo/HiGHS dispatch; re-optimized each event interval",
        "infeasibility_reason":None if complete else "At least one interval missed the accepted commitment.",
        "reliability":{"status":"not_evaluated","estimate":None,"sample_count":0,
            "confidence_lower_bound":None,"target":ecfg.get("target_complete_event_success_probability")},
        "complete_event_success":complete,
        "telemetry":{"baseline_grid_import_mw":base,"event_time_series":rows,
            "final_battery_soc":soc,"final_workload_backlog_mwh":backlog,
            "reoptimization_count":len(rows),"optimizer_calls":len(solver_times),
            "observations_used":sum(bool(item) for item in obs)},
        "violations":violations,
        "solver_metadata":{"solver":"HiGHS","termination":terminations[-1] if terminations else None,
            "termination_by_step":terminations,"runtime_seconds":sum(solver_times),
            "runtime_by_step_seconds":solver_times,"objective_by_step":objectives,
            "optimization_used":True},"random_seed":config.get("random_seed",0),
        "assumptions":recovery.get("assumptions",[])}


def _error(config,commitment,reason,rows,violations,times,runtime,termination=None):
    return _failure(config,commitment,"solver_error",reason,rows,violations,times,runtime,termination)


def _infeasible(config,commitment,rows,violations,times,reason,termination):
    return _failure(config,commitment,"infeasible",reason,rows,violations,times,sum(times),termination)


def _failure(config,commitment,status,reason,rows,violations,times,runtime,termination=None):
    return {"schema_version":"1.0.0","scenario_id":config["scenario_id"],
        "run_id":f"{config['scenario_id']}-rolling-{status}","controller":"rolling_mpc",
        "controller_version":"rolling-mpc-0.1.0","status":status,"execution_status":status,
        "accepted_commitment_mw":commitment,"infeasibility_reason":reason,
        "reliability":None,"complete_event_success":False,
        "telemetry":{"event_time_series":rows,"reoptimization_count":len(rows),
            "optimizer_calls":len(times)},"violations":[*violations,{"type":status,"reason":reason}],
        "solver_metadata":{"solver":"HiGHS","termination":termination,
            "runtime_seconds":runtime,"runtime_by_step_seconds":times},
        "random_seed":config.get("random_seed",0)}
