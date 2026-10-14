"""Scenario-based commitment calibration with simultaneous Wilson lower bounds."""
from __future__ import annotations
from math import ceil, isfinite, sqrt
from statistics import NormalDist
from typing import Any

from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario


def wilson_lower(successes: int, trials: int, *, alpha: float = 0.05) -> float:
    if trials <= 0 or not 0 <= successes <= trials or not 0 < alpha < 1:
        raise ValueError("invalid binomial inputs")
    p=successes/trials
    z=NormalDist().inv_cdf(1-alpha)
    z2=z*z
    den=1+z2/trials
    return max(0.0,(p+z2/(2*trials)-z*sqrt(p*(1-p)/trials+z2/(4*trials*trials)))/den)


def _scenario_passes(config: dict[str, Any], commitment_mw: float, disturbance,
                     assumptions: UncertaintyAssumptions) -> bool:
    facility=config["facility"]
    battery=config["battery"]
    event=config["grid_event"]
    cap=float(facility["deferrable_compute_mw"])
    duration_h=float(event["duration_minutes"])/60.0
    usable_soc=float(battery["initial_soc"])+disturbance.initial_soc_error
    if usable_soc < float(battery["min_soc"]):
        return False
    flexible_capacity=max(0.0,cap-disturbance.urgent_reclaim_mw)
    # Reserve a one-sided 99% Gaussian meter-noise margin in the dispatch.
    meter_margin=NormalDist().inv_cdf(0.99)*assumptions.meter_noise_std_mw
    planned_reduction=commitment_mw+meter_margin
    compute_reduction=min(planned_reduction,flexible_capacity)
    residual=max(0.0,planned_reduction-compute_reduction)
    energy_mwh=max(0.0,(usable_soc-float(battery["min_soc"]))*float(battery["capacity_mwh"])
                   *float(battery["discharge_efficiency"]))
    discharge=min(residual,float(battery["max_discharge_mw"])*disturbance.battery_discharge_scale,
                  energy_mwh/duration_h)
    delivered=compute_reduction+discharge-disturbance.meter_noise_mw
    if commitment_mw <= 1e-12:
        return True
    # Static schedule repeats at each event step; complete-event reliability is the
    # probability every interval delivers the commitment and preserves reserve.
    if delivered+1e-9 < commitment_mw:
        return False
    dc_used=discharge/duration_h/float(battery["discharge_efficiency"])*duration_h
    final_soc=usable_soc-dc_used/float(battery["capacity_mwh"])
    if final_soc < float(battery["min_soc"])-1e-9:
        return False
    # The max-deferral boundary must not be exceeded by the event.
    max_deferral=int(config.get("workloads",{}).get("max_deferral_minutes",300))
    return int(event["duration_minutes"]) <= max_deferral


def evaluate_commitment(config: dict[str, Any], commitment_mw: float, *,
                        n_scenarios: int = 1000, seed: int = 100_000,
                        assumptions: UncertaintyAssumptions | None = None,
                        confidence: float = 0.95) -> dict:
    if n_scenarios <= 0:
        raise ValueError("n_scenarios must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0,1)")
    requested=float(config["grid_event"]["requested_reduction_mw"])
    if not 0 <= commitment_mw <= requested:
        raise ValueError("commitment must be between zero and the grid request")
    a=assumptions or UncertaintyAssumptions()
    passed=sum(_scenario_passes(config,commitment_mw,generate_uncertainty_scenario(seed+i,a),a)
               for i in range(n_scenarios))
    alpha=1-confidence
    estimate=passed/n_scenarios
    lower=wilson_lower(passed,n_scenarios,alpha=alpha)
    z=NormalDist().inv_cdf(1-alpha/2)
    z2=z*z
    den=1+z2/n_scenarios
    upper=min(1.0,(estimate+z2/(2*n_scenarios)+z*sqrt(estimate*(1-estimate)/n_scenarios+z2/(4*n_scenarios*n_scenarios)))/den)
    return {"commitment_mw":commitment_mw,"successes":passed,"sample_count":n_scenarios,
            "estimate":estimate,"confidence_level":confidence,
            "wilson_interval":[lower,upper],"lower_confidence_bound":lower,
            "seed_start":seed,"evidence_split":"calibration_or_heldout_as_caller_declares"}


def calibrate_commitment(config: dict[str, Any], *, n_scenarios: int = 1000,
                         seed: int = 100_000, step_mw: float = 0.1,
                         target_reliability: float | None = None,
                         assumptions: UncertaintyAssumptions | None = None,
                         confidence: float = 0.95) -> dict:
    if n_scenarios <= 0:
        raise ValueError("n_scenarios must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0,1)")
    if not isfinite(step_mw) or step_mw <= 0:
        raise ValueError("step_mw must be finite and positive")
    requested=float(config["grid_event"]["requested_reduction_mw"])
    target=(float(config["grid_event"].get("target_complete_event_success_probability",0.95))
            if target_reliability is None else target_reliability)
    count=ceil(requested/step_mw)
    if not 0 <= target <= 1:
        raise ValueError("target_reliability must be in [0,1]")
    candidates=[max(0.0,requested-i*step_mw) for i in range(count+1)]
    # Bonferroni-adjusted one-sided Wilson bounds protect the search over candidates.
    alpha=(1-confidence)/len(candidates)
    a=assumptions or UncertaintyAssumptions()
    trials=[generate_uncertainty_scenario(seed+i,a) for i in range(n_scenarios)]
    evidence=[]
    for candidate in candidates:
        passed=sum(_scenario_passes(config,candidate,s,a) for s in trials)
        lower=wilson_lower(passed,n_scenarios,alpha=alpha)
        evidence.append({"commitment_mw":candidate,"successes":passed,"sample_count":n_scenarios,
                         "estimated_reliability":passed/n_scenarios,
                         "simultaneous_lower_bound":lower})
    accepted=next((row for row in evidence if row["simultaneous_lower_bound"]>=target),None)
    return {"status":"confirmed" if accepted else "unconfirmed",
            "accepted_commitment_mw":accepted["commitment_mw"] if accepted else 0.0,
            "target_reliability":target,"confidence_level":confidence,
            "calibration_sample_count":n_scenarios,"seed_start":seed,
            "selected_evidence":accepted,"candidate_evidence":evidence,
            "method":"scenario simulation with Bonferroni-adjusted one-sided Wilson lower bounds",
            "limitations":["No recovery feasibility in this Phase C calibration.",
                           "Disturbance probabilities are assumed, not empirically measured.",
                           "Critical-power variation is common-mode to baseline-relative event reduction.",
                           "Use separate seeds for calibration and held-out evaluation."]}
