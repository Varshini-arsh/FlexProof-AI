from pathlib import Path
from statistics import NormalDist

import pytest
import yaml

from optimization.commitment import calibrate_commitment
from optimization.dispatch import solve_rolling_event_dispatch
from optimization.rafc_v import run_rafc_v
from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario

ROOT = Path(__file__).parents[1]
CONFIG = yaml.safe_load((ROOT / "configs" / "fp001.yaml").read_text(encoding="utf-8"))
V2 = {"forecast": "persistence", "soft_margin": True}
MARGIN = NormalDist().inv_cdf(0.99) * UncertaintyAssumptions().meter_noise_std_mw


def _observations(seed):
    scenario = generate_uncertainty_scenario(seed, UncertaintyAssumptions())
    observed = {
        "available_flexible_compute_mw": 4.0 - scenario.urgent_reclaim_mw,
        "battery_discharge_scale": scenario.battery_discharge_scale,
        "critical_power_delta_mw": scenario.critical_power_delta_mw,
        "meter_noise_mw": scenario.meter_noise_mw,
    }
    observations = [dict(observed) for _ in range(12)]
    observations[0]["initial_soc_error"] = scenario.initial_soc_error
    return observations


def _shortfall_steps(result):
    return sum(row["shortfall_mw"] > 1e-7 for row in result["telemetry"]["event_time_series"])


def test_v2_rescues_scenario_that_v1_loses_to_early_margin_overdelivery():
    # Seed 400095: 0.4 MW urgent reclaim plus a negative SoC error. It is physically
    # feasible at 4.9 MW, but v1 spends battery energy on the 99% meter margin and
    # misses the last interval.
    observations = _observations(400095)
    v1 = solve_rolling_event_dispatch(CONFIG, 4.9, observations=observations,
                                      delivery_margin_mw=MARGIN)
    v2 = solve_rolling_event_dispatch(CONFIG, 4.9, observations=observations,
                                      delivery_margin_mw=MARGIN, **V2)
    assert _shortfall_steps(v1) == 1
    assert v2["status"] == "completed"
    assert _shortfall_steps(v2) == 0
    assert v2["telemetry"]["final_battery_soc"] >= CONFIG["battery"]["min_soc"] - 1e-7


def test_v2_still_delivers_margin_when_energy_is_plentiful():
    observations = _observations(400000)  # no urgent reclaim, ample battery energy
    result = solve_rolling_event_dispatch(CONFIG, 4.0, observations=observations,
                                          delivery_margin_mw=MARGIN, **V2)
    rows = result["telemetry"]["event_time_series"]
    assert result["status"] == "completed"
    assert all(row["delivered_reduction_mw"] >= 4.0 + MARGIN - 1e-6 for row in rows)


def test_v2_persistence_forecast_does_not_read_future_observations():
    nominal = [{} for _ in range(12)]
    future = [{} for _ in range(12)]
    future[8] = {"available_flexible_compute_mw": 0.0, "battery_discharge_scale": 0.0,
                 "meter_noise_mw": 0.2}
    first = solve_rolling_event_dispatch(CONFIG, 4.0, observations=nominal,
                                         delivery_margin_mw=0.05, **V2)
    second = solve_rolling_event_dispatch(CONFIG, 4.0, observations=future,
                                          delivery_margin_mw=0.05, **V2)
    a = first["telemetry"]["event_time_series"][0]
    b = second["telemetry"]["event_time_series"][0]
    assert a["flexible_compute_curtailment_mw"] == pytest.approx(b["flexible_compute_curtailment_mw"])
    assert a["battery_discharge_mw"] == pytest.approx(b["battery_discharge_mw"])


def test_default_dispatch_policy_is_unchanged():
    observations = _observations(400095)
    default = solve_rolling_event_dispatch(CONFIG, 4.9, observations=observations,
                                           delivery_margin_mw=MARGIN)
    explicit = solve_rolling_event_dispatch(CONFIG, 4.9, observations=observations,
                                            delivery_margin_mw=MARGIN,
                                            forecast="nominal", soft_margin=False)
    assert default["run_id"] == explicit["run_id"]
    assert _shortfall_steps(default) == _shortfall_steps(explicit)


def test_invalid_forecast_is_rejected():
    with pytest.raises(ValueError):
        solve_rolling_event_dispatch(CONFIG, 4.0, forecast="oracle")


def test_v2_calibration_commits_more_reliably_than_the_margin_screen():
    v2 = calibrate_commitment(CONFIG, n_scenarios=300, seed=100000, step_mw=0.1,
                              recovery_aware=True, meter_margin_mw=0.0, observed_noise=True)
    v1 = calibrate_commitment(CONFIG, n_scenarios=300, seed=100000, step_mw=0.1,
                              recovery_aware=True)
    assert v2["status"] == "confirmed"
    assert v2["accepted_commitment_mw"] >= v1["accepted_commitment_mw"]
    selected = v2["selected_evidence"]
    assert selected["simultaneous_lower_bound"] >= v2["target_reliability"]


def test_rafc_v_v2_runs_end_to_end_and_records_policy():
    result = run_rafc_v(CONFIG, calibration_scenarios=300, calibration_seed=900,
                        commitment_step_mw=0.5, dispatch_policy="v2")
    assert result["status"] == "completed"
    assert result["rafc_v"]["dispatch_policy"] == "v2"
    assert result["recovery"]["status"] == "completed"
    with pytest.raises(ValueError):
        run_rafc_v(CONFIG, calibration_scenarios=20, dispatch_policy="v3")
