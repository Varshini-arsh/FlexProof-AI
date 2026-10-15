"""Apply API inputs to the existing Member 1 nominal simulator."""
from pathlib import Path
from typing import Any

from simulator.engine import load_config, run_nominal_event

CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "fp001.yaml"


def run_fp001_nominal(*, scenario_id: str, requested_reduction_mw: float,
                      duration_minutes: int, battery_soc_percent: float,
                      reliability_target: float, random_seed: int) -> dict[str, Any]:
    config = load_config(CONFIG_PATH)
    config["scenario_id"] = scenario_id
    config["random_seed"] = random_seed
    config["grid_event"]["requested_reduction_mw"] = requested_reduction_mw
    config["grid_event"]["duration_minutes"] = duration_minutes
    config["grid_event"]["target_complete_event_success_probability"] = reliability_target
    config["battery"]["initial_soc"] = battery_soc_percent / 100.0
    return run_nominal_event(config)
