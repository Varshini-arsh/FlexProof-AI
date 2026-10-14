"""Risk-calibrated deterministic dispatch without recovery-aware commitment."""
from baselines.deterministic_mpc import solve_deterministic_dispatch
from optimization.commitment import calibrate_commitment


def run_risk_aware_mpc(config: dict, *, calibration_scenarios: int = 1000,
                       calibration_seed: int = 100_000, commitment_step_mw: float = 0.1) -> dict:
    calibration=calibrate_commitment(config,n_scenarios=calibration_scenarios,
        seed=calibration_seed,step_mw=commitment_step_mw)
    accepted=calibration["accepted_commitment_mw"]
    result=solve_deterministic_dispatch(config,accepted_commitment_mw=accepted)
    result["controller"]="risk_aware_mpc"
    result["controller_version"]="risk-aware-mpc-0.1.0"
    result["reliability"]={"status":calibration["status"],
        "estimate":calibration["selected_evidence"]["estimated_reliability"] if calibration["selected_evidence"] else None,
        "confidence_lower_bound":calibration["selected_evidence"]["simultaneous_lower_bound"] if calibration["selected_evidence"] else None,
        "confidence_level":calibration["confidence_level"],
        "sample_count":calibration["calibration_sample_count"],
        "evidence_split":"calibration",
        "target":calibration["target_reliability"]}
    result["commitment_calibration"]=calibration
    result["commitment_basis"]="calibrated event reliability; no recovery-aware planning"
    return result
