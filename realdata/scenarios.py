"""Build FP-001 scenario configs and empirical disturbances for real grid events.

Mapping from the Azure trace to facility power (explicit assumptions):
- Critical inference power = rated_critical_mw * (idle + (1 - idle) * u), where u
  is trace utilization (1.0 = 99th-percentile throughput). The idle floor
  reflects that GPU servers draw substantial power at low load.
- The trace timestamps are UTC; the facility is assumed to serve the same user
  base and is placed in the CAISO (Pacific) time zone.

Baseline drift: demand-response programs measure the cut against a baseline
set before the event. Here the baseline is the mean critical power over the
60 minutes before the event, and drift is the worst (maximum) critical power
during the event minus that baseline. Positive drift reduces the measured cut.
Samples come from every trace day in the split, for start times within
+/- 60 minutes of the real event's local start time.

Recovery base demand: fixed auxiliary + critical power + 1 MW of scheduled
non-deferred compute, taken as the maximum over the 4-hour recovery window and
then the 90th percentile across calibration days (a planning value).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from math import isfinite

import numpy as np
import pandas as pd

from simulator.uncertainty import UncertaintyAssumptions

LOCAL_TZ = "America/Los_Angeles"


@dataclass(frozen=True, slots=True)
class PowerMapping:
    rated_critical_mw: float = 12.0
    idle_fraction: float = 0.4
    scheduled_non_deferred_mw: float = 1.0
    baseline_window_minutes: int = 60
    start_jitter_minutes: int = 60
    recovery_horizon_minutes: int = 240


def critical_power_mw(utilization: pd.Series, mapping: PowerMapping) -> pd.Series:
    u = utilization.clip(lower=0.0)
    return mapping.rated_critical_mw * (mapping.idle_fraction + (1.0 - mapping.idle_fraction) * u)


def localize(profile: pd.DataFrame) -> pd.Series:
    """Critical-load utilization indexed in Pacific time, complete days only."""
    series = profile["utilization"].copy()
    series.index = series.index.tz_convert(LOCAL_TZ)
    return series


def split_days(utilization: pd.Series, calibration_fraction: float = 0.6) -> tuple[list, list]:
    days = sorted({stamp.date() for stamp in utilization.index})
    cut = max(1, round(len(days) * calibration_fraction))
    return days[:cut], days[cut:]


def _windows(power: pd.Series, days: list, start_minute_of_day: int, duration: int,
             mapping: PowerMapping):
    """Yield (baseline, event, recovery) windows for each day and jittered start."""
    jitter = range(-mapping.start_jitter_minutes, mapping.start_jitter_minutes + 1, 5)
    for day in days:
        midnight = pd.Timestamp(day).tz_localize(LOCAL_TZ)
        for offset in jitter:
            start = midnight + pd.Timedelta(minutes=start_minute_of_day + offset)
            pre = power[(power.index >= start - pd.Timedelta(minutes=mapping.baseline_window_minutes)) & (power.index < start)]
            during = power[(power.index >= start) & (power.index < start + pd.Timedelta(minutes=duration))]
            end = start + pd.Timedelta(minutes=duration)
            after = power[(power.index >= end) & (power.index < end + pd.Timedelta(minutes=mapping.recovery_horizon_minutes))]
            expected = (mapping.baseline_window_minutes // 5, duration // 5, mapping.recovery_horizon_minutes // 5)
            if (len(pre), len(during), len(after)) == expected:
                yield day, pre, during, after


def drift_samples(power: pd.Series, days: list, start_minute_of_day: int, duration: int,
                  mapping: PowerMapping) -> tuple[float, ...]:
    samples = [float(during.max() - pre.mean())
               for _, pre, during, _ in _windows(power, days, start_minute_of_day, duration, mapping)]
    return tuple(value for value in samples if isfinite(value))


def recovery_base_mw(power: pd.Series, days: list, start_minute_of_day: int, duration: int,
                     mapping: PowerMapping, fixed_auxiliary_mw: float) -> float:
    per_day: dict = {}
    for day, _, _, after in _windows(power, days, start_minute_of_day, duration, mapping):
        per_day.setdefault(day, []).append(float(after.max()))
    if not per_day:
        raise ValueError("no complete recovery windows in the trace for this event")
    day_peaks = [np.mean(values) for values in per_day.values()]
    return float(np.quantile(day_peaks, 0.9)) + fixed_auxiliary_mw + mapping.scheduled_non_deferred_mw


def build_event_case(base_config: dict, base_assumptions: UncertaintyAssumptions, *,
                     event_start_local: pd.Timestamp, duration_minutes: int,
                     utilization: pd.Series, calibration_days: list, test_days: list,
                     mapping: PowerMapping = PowerMapping()) -> dict:
    """Return the scenario config plus calibration and held-out assumptions for one event."""
    if duration_minutes % 5:
        raise ValueError("event duration must be a multiple of 5 minutes")
    power = critical_power_mw(utilization, mapping)
    minute_of_day = event_start_local.hour * 60 + event_start_local.minute
    config = copy.deepcopy(base_config)
    config["scenario_id"] = f"FP-001-{event_start_local.strftime('%Y%m%d-%H%M')}"
    config["grid_event"]["duration_minutes"] = int(duration_minutes)
    recovery = config["recovery"]
    recovery["horizon_minutes"] = mapping.recovery_horizon_minutes
    recovery["target_minute"] = int(duration_minutes) + mapping.recovery_horizon_minutes
    recovery["clear_deferred_work_by_minute"] = recovery["target_minute"]
    recovery["nominal_base_demand_mw"] = round(recovery_base_mw(
        power, calibration_days, minute_of_day, duration_minutes, mapping,
        float(config["facility"]["fixed_auxiliary_mw"])), 4)
    recovery["assumptions"] = [
        "Recovery base = fixed auxiliary + Azure-trace critical power + scheduled non-deferred compute.",
        "Planning value: 90th percentile across calibration days of the 4-hour window maximum.",
    ]
    calibration_drift = drift_samples(power, calibration_days, minute_of_day, duration_minutes, mapping)
    test_drift = drift_samples(power, test_days, minute_of_day, duration_minutes, mapping)
    if not calibration_drift or not test_drift:
        raise ValueError("not enough trace data to sample baseline drift for this event")
    return {
        "config": config,
        "calibration_assumptions": replace(base_assumptions, baseline_drift_samples_mw=calibration_drift),
        "test_assumptions": replace(base_assumptions, baseline_drift_samples_mw=test_drift),
    }
