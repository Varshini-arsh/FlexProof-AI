"""Apply API inputs to the existing Member 1 nominal simulator."""
from pathlib import Path
from typing import Any
import jsonschema

from evaluation.metrics import wilson_interval
from flexproof.engine import evaluate_commitment, load_scenario, run_scenario

from simulator.engine import load_config

CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "fp001.yaml"
ENGINE_SOURCE_REVISION = "b5712c2d5af49d70627225ae9f1a5127fb84976a"


def build_config(request: dict[str, Any]) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    config["scenario_id"] = request["scenario_id"]
    config["random_seed"] = request["random_seed"]
    config["controller"] = request["controller"]
    config["reliability_target"] = request["reliability_target"]
    config["grid_event"]["requested_reduction_mw"] = request["requested_reduction_mw"]
    config["grid_event"]["duration_minutes"] = request["duration_minutes"]
    config["grid_event"]["target_complete_event_success_probability"] = request["reliability_target"]
    config["battery"]["initial_soc"] = request["battery_soc_percent"] / 100.0
    end = config["grid_event"]["start_minute"] + request["duration_minutes"] + config["recovery"]["horizon_minutes"]
    config["recovery"]["target_minute"] = end
    config["recovery"]["clear_deferred_work_by_minute"] = end
    config["recovery"]["grid_import_ceiling_mw"] = request["recovery_grid_ceiling_mw"]
    try:
        return load_scenario(config).to_dict()
    except jsonschema.ValidationError as exc:
        raise ValueError(exc.message) from exc


def execute_simulation(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    config = build_config(request)
    result = run_scenario(config, controller=request["controller"],
                          calibration_scenarios=request["calibration_scenarios"],
                          calibration_seed=request["random_seed"],
                          commitment_step_mw=request["commitment_step_mw"])
    if result["status"] == "invalid_input":
        raise ValueError(result["infeasibility_reason"])
    return config, result


def assess_commitment(request: dict[str, Any]) -> dict[str, Any]:
    config = build_config(request)
    assessment = evaluate_commitment(config, n_scenarios=request["calibration_scenarios"],
                                     seed=request["random_seed"], step_mw=request["commitment_step_mw"],
                                     recovery_aware=True)
    selected = assessment["selected_evidence"]
    return {
        "requested_reduction_mw": request["requested_reduction_mw"],
        "recommended_commitment_mw": assessment["accepted_commitment_mw"],
        "reliability_target": request["reliability_target"],
        "feasibility_status": "screen_passed" if selected and assessment["accepted_commitment_mw"] > 0 else "unconfirmed",
        "explanation": "Candidate passes calibration and shared recovery-capacity screening; event execution remains to be simulated." if selected else "Available calibration evidence cannot support a commitment at the selected threshold.",
        "controller_version": "rafc-v-0.1.0", "engine_source_revision": ENGINE_SOURCE_REVISION,
        "reliability_certified": False,
        "calibration": {"evidence_split": "calibration", "sample_count": assessment["calibration_sample_count"],
            "seed_start": request["random_seed"], "estimate": selected["estimated_reliability"] if selected else None,
            "wilson_interval": wilson_interval(selected["successes"], selected["sample_count"]) if selected else None,
            "simultaneous_lower_bound": selected["simultaneous_lower_bound"] if selected else None,
            "confidence_level": assessment["confidence_level"], "method": assessment["method"]},
        "held_out_validation": {"status": "unavailable", "reason": "No independently reproduced raw held-out artifact is attached to this assessment."},
        "candidate_evidence": assessment["candidate_evidence"], "limitations": assessment["limitations"],
    }
