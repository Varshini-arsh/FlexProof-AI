import pandas as pd
import pytest
import yaml
from pathlib import Path

from optimization.commitment import evaluate_commitment
from realdata.grid_events import extract_events
from realdata.scenarios import PowerMapping, build_event_case, critical_power_mw, drift_samples, split_days
from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario

ROOT = Path(__file__).resolve().parents[1]
TZ = "America/Los_Angeles"


def _config():
    with (ROOT / "configs" / "fp001.yaml").open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _prices(values, start="2024-08-01 17:00"):
    index = pd.date_range(start, periods=len(values), freq="15min", tz=TZ)
    return pd.Series(values, index=index, dtype=float)


def _utilization(days=4, ramp_hour=17):
    # Flat 0.3 utilization, stepping to 0.8 at ramp_hour every day.
    index = pd.date_range("2024-05-10", periods=days * 288, freq="5min", tz=TZ)
    return pd.Series([0.8 if stamp.hour >= ramp_hour else 0.3 for stamp in index], index=index)


def test_drift_disabled_reproduces_original_disturbances():
    plain = generate_uncertainty_scenario(123)
    explicit = generate_uncertainty_scenario(123, UncertaintyAssumptions())
    assert plain == explicit
    assert plain.baseline_drift_mw == 0.0
    assert plain.measured_offset_mw == plain.meter_noise_mw


def test_drift_is_drawn_from_samples_without_changing_other_draws():
    plain = generate_uncertainty_scenario(7)
    drifted = generate_uncertainty_scenario(7, UncertaintyAssumptions(baseline_drift_samples_mw=(0.5, 0.7)))
    assert drifted.baseline_drift_mw in (0.5, 0.7)
    assert drifted.meter_noise_mw == plain.meter_noise_mw
    assert drifted.urgent_reclaim == plain.urgent_reclaim


def test_positive_drift_lowers_reliability():
    config = _config()
    clean = evaluate_commitment(config, 4.0, n_scenarios=200, meter_margin_mw=0.0, observed_noise=True)
    drifted = evaluate_commitment(config, 4.0, n_scenarios=200, meter_margin_mw=0.0, observed_noise=True,
                                  assumptions=UncertaintyAssumptions(baseline_drift_samples_mw=(2.0,)))
    assert drifted["successes"] < clean["successes"]


def test_events_merge_single_interval_dips_and_skip_cold_periods():
    prices = _prices([50, 250, 260, 100, 300, 40, 40, 40, 400])
    events = extract_events(prices, threshold_usd_mwh=200)
    assert [event.duration_minutes for event in events] == [60, 15]
    assert events[0].max_price_usd_mwh == 300


def test_event_duration_is_capped_at_deferral_limit():
    events = extract_events(_prices([500] * 30), threshold_usd_mwh=200)
    assert events[0].duration_minutes == 300


def test_drift_is_positive_when_load_ramps_during_event():
    mapping = PowerMapping(start_jitter_minutes=0)
    power = critical_power_mw(_utilization(), mapping)
    days = sorted({stamp.date() for stamp in power.index})[1:3]
    samples = drift_samples(power, days, 17 * 60, 60, mapping)
    expected = mapping.rated_critical_mw * (1 - mapping.idle_fraction) * 0.5
    assert samples and all(value == pytest.approx(expected) for value in samples)


def test_event_case_uses_separate_drift_for_calibration_and_test():
    utilization = _utilization(days=5)
    calibration_days, test_days = split_days(utilization)
    assert set(calibration_days).isdisjoint(test_days)
    case = build_event_case(_config(), UncertaintyAssumptions(),
                            event_start_local=pd.Timestamp("2024-08-01 18:30", tz=TZ), duration_minutes=45,
                            utilization=utilization, calibration_days=calibration_days[1:], test_days=test_days[:-1])
    config = case["config"]
    assert config["grid_event"]["duration_minutes"] == 45
    assert config["recovery"]["target_minute"] == 45 + 240
    assert config["recovery"]["nominal_base_demand_mw"] > float(config["facility"]["fixed_auxiliary_mw"])
    assert case["calibration_assumptions"].baseline_drift_samples_mw
    assert case["test_assumptions"].baseline_drift_samples_mw
