"""Seeded modeled disturbances; parameters are assumptions, not measured data."""
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
import numpy as np
import yaml

@dataclass(frozen=True, slots=True)
class UncertaintyAssumptions:
    initial_soc_error_bound: float=0.015
    critical_power_std_mw: float=0.1
    critical_power_truncation_mw: float=0.3
    urgent_reclaim_probability: float=0.10
    urgent_reclaim_mw: float=0.4
    battery_derating_probability: float=0.05
    battery_derating_fraction: float=0.10
    meter_noise_std_mw: float=0.02

    def __post_init__(self):
        vals=(self.initial_soc_error_bound,self.critical_power_std_mw,self.critical_power_truncation_mw,
              self.urgent_reclaim_probability,self.urgent_reclaim_mw,self.battery_derating_probability,
              self.battery_derating_fraction,self.meter_noise_std_mw)
        if not all(isfinite(v) for v in vals): raise ValueError("uncertainty parameters must be finite")
        if not 0<=self.urgent_reclaim_probability<=1 or not 0<=self.battery_derating_probability<=1:
            raise ValueError("probabilities must be in [0,1]")
        if min(self.initial_soc_error_bound,self.critical_power_std_mw,self.critical_power_truncation_mw,
               self.urgent_reclaim_mw,self.battery_derating_fraction,self.meter_noise_std_mw)<0:
            raise ValueError("uncertainty scales must be nonnegative")
        if self.battery_derating_fraction>1: raise ValueError("derating fraction must not exceed one")

    @classmethod
    def from_mapping(cls, values: dict):
        return cls(
            initial_soc_error_bound=float(values.get("initial_soc_error_bound",0.015)),
            critical_power_std_mw=float(values.get("critical_power_std_mw",0.1)),
            critical_power_truncation_mw=float(values.get("critical_power_truncation_mw",0.3)),
            urgent_reclaim_probability=float(values.get("urgent_reclaim_probability",0.10)),
            urgent_reclaim_mw=float(values.get("urgent_reclaim_mw",0.4)),
            battery_derating_probability=float(values.get("battery_derating_probability",0.05)),
            battery_derating_fraction=float(values.get("battery_derating_fraction",0.10)),
            meter_noise_std_mw=float(values.get("grid_meter_noise_std_mw",values.get("meter_noise_std_mw",0.02))))

@dataclass(frozen=True, slots=True)
class UncertaintyScenario:
    seed: int
    initial_soc_error: float
    critical_power_delta_mw: float
    urgent_reclaim: bool
    urgent_reclaim_mw: float
    battery_derated: bool
    battery_discharge_scale: float
    meter_noise_mw: float
    def to_dict(self) -> dict: return asdict(self)

def generate_uncertainty_scenario(seed: int, assumptions: UncertaintyAssumptions | None=None) -> UncertaintyScenario:
    if not isinstance(seed,int): raise ValueError("seed must be an integer")
    a=assumptions or UncertaintyAssumptions()
    rng=np.random.default_rng(seed)
    soc=float(rng.uniform(-a.initial_soc_error_bound,a.initial_soc_error_bound))
    if a.critical_power_truncation_mw == 0 or a.critical_power_std_mw == 0:
        critical=0.0
    else:
        critical=float(rng.normal(0.0,a.critical_power_std_mw))
        while critical < -a.critical_power_truncation_mw or critical > a.critical_power_truncation_mw:
            critical=float(rng.normal(0.0,a.critical_power_std_mw))
    reclaim=bool(rng.random()<a.urgent_reclaim_probability)
    derated=bool(rng.random()<a.battery_derating_probability)
    return UncertaintyScenario(seed,soc,critical,reclaim,a.urgent_reclaim_mw if reclaim else 0.0,
        derated,1.0-a.battery_derating_fraction if derated else 1.0,
        float(rng.normal(0.0,a.meter_noise_std_mw)))

def load_uncertainty_assumptions(source: str | Path | dict) -> UncertaintyAssumptions:
    if isinstance(source,dict): values=source
    else:
        with Path(source).open("r",encoding="utf-8") as stream: values=yaml.safe_load(stream)
    if not isinstance(values,dict): raise ValueError("uncertainty config must be a mapping")
    return UncertaintyAssumptions.from_mapping(values)
