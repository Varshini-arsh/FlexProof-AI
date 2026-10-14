from pathlib import Path
import pytest
import yaml

from optimization.dispatch import solve_rolling_event_dispatch

ROOT=Path(__file__).parents[1]
CONFIG=yaml.safe_load((ROOT/"configs"/"fp001.yaml").read_text(encoding="utf-8"))


def test_rolling_dispatch_reoptimizes_every_interval_and_preserves_recovery():
    result=solve_rolling_event_dispatch(CONFIG,accepted_commitment_mw=4.0,
                                        delivery_margin_mw=0.05)
    assert result["status"]=="completed"
    assert result["complete_event_success"]
    rows=result["telemetry"]["event_time_series"]
    assert len(rows)==12
    assert result["telemetry"]["reoptimization_count"]==12
    assert result["telemetry"]["optimizer_calls"]==12
    assert result["telemetry"]["final_battery_soc"]>=CONFIG["battery"]["min_soc"]
    assert result["telemetry"]["final_workload_backlog_mwh"]>=0


def test_rolling_dispatch_uses_new_capacity_and_derating_observations():
    observations=[{} for _ in range(12)]
    observations[0]={"initial_soc_error":0.005}
    observations[3]={"available_flexible_compute_mw":2.0,
        "battery_discharge_scale":0.8,"meter_noise_mw":0.01,
        "critical_power_delta_mw":0.1}
    result=solve_rolling_event_dispatch(CONFIG,accepted_commitment_mw=4.0,
                                        observations=observations,delivery_margin_mw=0.05)
    assert result["status"]=="completed"
    row=result["telemetry"]["event_time_series"][3]
    assert row["observed_flexible_capacity_mw"]==pytest.approx(2.0)
    assert row["flexible_compute_curtailment_mw"]<=2.0+1e-7
    assert row["battery_discharge_mw"]<=2.4+1e-7
    assert row["meter_noise_mw"]==pytest.approx(0.01)
    assert row["success"]
    assert result["telemetry"]["observations_used"]==2
    assert result["telemetry"]["event_time_series"][0]["battery_soc_start"]==pytest.approx(0.355)


def test_rolling_dispatch_validates_observation_horizon():
    with pytest.raises(ValueError,match="one mapping per event interval"):
        solve_rolling_event_dispatch(CONFIG,accepted_commitment_mw=4.0,observations=[{}])


def test_rolling_dispatch_rejects_observed_soc_below_protected_reserve():
    observations=[{} for _ in range(12)]
    observations[0]={"initial_soc_error":-0.2}
    result=solve_rolling_event_dispatch(CONFIG,accepted_commitment_mw=4.0,
                                        observations=observations)
    assert result["status"]=="infeasible"
    assert result["telemetry"]["event_time_series"]==[]


def test_rolling_dispatch_does_not_use_future_observations_for_current_action():
    nominal=[{} for _ in range(12)]
    future_disturbance=[{} for _ in range(12)]
    future_disturbance[8]={"available_flexible_compute_mw":0.0,
        "battery_discharge_scale":0.0,"meter_noise_mw":0.2}
    first=solve_rolling_event_dispatch(CONFIG,accepted_commitment_mw=4.0,
        observations=nominal,delivery_margin_mw=0.05)
    second=solve_rolling_event_dispatch(CONFIG,accepted_commitment_mw=4.0,
        observations=future_disturbance,delivery_margin_mw=0.05)
    first_row=first["telemetry"]["event_time_series"][0]
    second_row=second["telemetry"]["event_time_series"][0]
    assert first_row["flexible_compute_curtailment_mw"]==pytest.approx(
        second_row["flexible_compute_curtailment_mw"])
    assert first_row["battery_discharge_mw"]==pytest.approx(second_row["battery_discharge_mw"])
