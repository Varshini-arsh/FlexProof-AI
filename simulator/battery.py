"""Battery with AC-side power and DC-side stored energy."""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True, slots=True)
class Battery:
    capacity_mwh: float
    initial_soc: float
    min_soc: float
    max_soc: float
    max_discharge_mw: float
    max_charge_mw: float
    charge_efficiency: float
    discharge_efficiency: float

    def __post_init__(self):
        if not isfinite(self.capacity_mwh) or self.capacity_mwh <= 0: raise ValueError("capacity_mwh must be finite and positive")
        if not (0 <= self.min_soc <= self.initial_soc <= self.max_soc <= 1): raise ValueError("invalid SoC bounds")
        if not all(isfinite(v) for v in (self.max_discharge_mw,self.max_charge_mw)): raise ValueError("power limits must be finite")
        if self.max_discharge_mw < 0 or self.max_charge_mw < 0: raise ValueError("power limits must be nonnegative")
        if not (0 < self.charge_efficiency <= 1 and 0 < self.discharge_efficiency <= 1): raise ValueError("efficiencies must be in (0, 1]")

    def step(self, soc, *, charge_mw=0.0, discharge_mw=0.0, timestep_hours):
        tol=1e-9
        if not self.min_soc-tol <= soc <= self.max_soc+tol: raise ValueError("current SoC outside limits")
        if timestep_hours <= 0: raise ValueError("timestep_hours must be positive")
        if charge_mw < 0 or discharge_mw < 0: raise ValueError("powers must be nonnegative")
        if charge_mw > self.max_charge_mw+tol or discharge_mw > self.max_discharge_mw+tol: raise ValueError("power limit exceeded")
        if charge_mw > tol and discharge_mw > tol: raise ValueError("simultaneous charge/discharge forbidden")
        nxt=soc+(charge_mw*self.charge_efficiency-discharge_mw/self.discharge_efficiency)*timestep_hours/self.capacity_mwh
        if not self.min_soc-tol <= nxt <= self.max_soc+tol: raise ValueError("dispatch violates SoC limits")
        return min(self.max_soc,max(self.min_soc,nxt))

    def usable_dc_energy_mwh(self, soc=None):
        level=self.initial_soc if soc is None else soc
        if not self.min_soc <= level <= self.max_soc: raise ValueError("SoC outside limits")
        return (level-self.min_soc)*self.capacity_mwh

    def usable_ac_energy_mwh(self, soc=None): return self.usable_dc_energy_mwh(soc)*self.discharge_efficiency
