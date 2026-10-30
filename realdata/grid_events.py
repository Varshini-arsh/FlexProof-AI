"""Extract grid stress events from CAISO 2024 real-time prices.

An event is a run of consecutive 15-minute intervals where the SP15 hub
real-time price is at or above a threshold. Runs separated by at most one
interval are merged, so a single dip does not split an event. Durations are
capped at the 300-minute workload deferral limit used by FP-001.

High real-time prices are a proxy for grid stress, not a record of actual
demand-response dispatch instructions. The price during each event is used
only to put an indicative energy value on each committed MW.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CAISO = ROOT / "data" / "raw" / "caiso"
LOCAL_TZ = "America/Los_Angeles"
MAX_DURATION_MINUTES = 300


@dataclass(frozen=True, slots=True)
class GridEvent:
    event_id: str
    start_local: str
    duration_minutes: int
    mean_price_usd_mwh: float
    max_price_usd_mwh: float
    peak_system_load_mw: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def load_prices(year: int = 2024, directory: Path = CAISO) -> pd.Series:
    frame = pd.read_csv(directory / f"caiso_rt15_lmp_sp15_{year}.csv.gz")
    index = pd.to_datetime(frame["Interval Start"], utc=True).dt.tz_convert(LOCAL_TZ)
    return pd.Series(frame["LMP"].to_numpy(), index=index, name="lmp").sort_index()


def load_system_demand(year: int = 2024, directory: Path = CAISO) -> pd.Series | None:
    path = directory / f"caiso_load_5min_{year}.csv.gz"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    index = pd.to_datetime(frame["Interval Start"], utc=True).dt.tz_convert(LOCAL_TZ)
    return pd.Series(frame["Load"].to_numpy(), index=index, name="load").sort_index()


def extract_events(prices: pd.Series, *, threshold_usd_mwh: float,
                   demand: pd.Series | None = None, min_duration_minutes: int = 15) -> list[GridEvent]:
    """Return price-spike events, longest gaps merged, in chronological order."""
    step = pd.Timedelta(minutes=15)
    prices = prices[~prices.index.duplicated()].sort_index()
    hot = prices.index[prices >= threshold_usd_mwh]
    runs: list[list[pd.Timestamp]] = []
    for stamp in hot:
        if runs and stamp - runs[-1][-1] <= 2 * step:
            runs[-1].append(stamp)
        else:
            runs.append([stamp])
    events = []
    for run in runs:
        start, end = run[0], run[-1] + step
        duration = int((end - start) / pd.Timedelta(minutes=1))
        if duration < min_duration_minutes:
            continue
        duration = min(duration, MAX_DURATION_MINUTES)
        window = prices[(prices.index >= start) & (prices.index < start + pd.Timedelta(minutes=duration))]
        peak_load = None
        if demand is not None:
            loads = demand[(demand.index >= start) & (demand.index < start + pd.Timedelta(minutes=duration))]
            peak_load = float(loads.max()) if len(loads) else None
        events.append(GridEvent(
            event_id=f"CAISO-{start.strftime('%Y%m%d-%H%M')}",
            start_local=start.isoformat(),
            duration_minutes=duration,
            mean_price_usd_mwh=float(window.mean()),
            max_price_usd_mwh=float(window.max()),
            peak_system_load_mw=peak_load,
        ))
    return events
