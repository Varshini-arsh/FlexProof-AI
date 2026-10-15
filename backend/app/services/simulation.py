"""Translate API requests into public engine calls and persist their evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from flexproof.engine import load_scenario, run_scenario
from simulator.engine import load_config

from backend.app.models import ScenarioRequest
from backend.app.services.storage import save_run
from backend.app.services.verification import verify_result


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "configs" / "fp001.yaml"


def build_config(request: ScenarioRequest) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    config["scenario_id"] = request.scenario_id
    config["random_seed"] = request.random_seed
    config["controller"] = request.controller
    config["reliability_target"] = request.reliability_target
    config["grid_event"]["requested_reduction_mw"] = request.requested_reduction_mw
    config["grid_event"]["duration_minutes"] = request.duration_minutes
    config["grid_event"]["target_complete_event_success_probability"] = request.reliability_target
    config["battery"]["initial_soc"] = request.battery_soc_percent / 100.0
    return load_scenario(config).to_dict()


def execute_scenario(request: ScenarioRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    config = build_config(request)
    result = run_scenario(config, controller=request.controller,
                          calibration_scenarios=request.calibration_scenarios,
                          calibration_seed=request.random_seed,
                          commitment_step_mw=request.commitment_step_mw)
    result["engine_run_id"] = result.get("run_id")
    result["run_id"] = f"{result.get('run_id', request.scenario_id)}-{uuid4().hex[:10]}"
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    verification = verify_result(config, result)
    result["independent_verification"] = verification
    save_run(request.model_dump(), config, result, verification)
    return result, verification

\n