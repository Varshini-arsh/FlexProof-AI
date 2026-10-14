"""Facility AC-side power balance."""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True, slots=True)
class Facility:
    critical_mw: float
    fixed_auxiliary_mw: float
    deferrable_compute_mw: float

    def __post_init__(self):
        for name,value in (("critical_mw",self.critical_mw),("fixed_auxiliary_mw",self.fixed_auxiliary_mw),("deferrable_compute_mw",self.deferrable_compute_mw)):
            if not isfinite(value) or value < 0: raise ValueError(f"{name} must be finite and nonnegative")

    @property
    def baseline_grid_import_mw(self): return self.critical_mw+self.fixed_auxiliary_mw+self.deferrable_compute_mw

    def grid_import_mw(self, *, flexible_compute_mw, battery_charge_mw=0.0, battery_discharge_mw=0.0):
        tol=1e-9
        if not 0 <= flexible_compute_mw <= self.deferrable_compute_mw+tol: raise ValueError("flexible compute outside configured power")
        if battery_charge_mw < 0 or battery_discharge_mw < 0: raise ValueError("battery powers must be nonnegative")
        if battery_charge_mw > tol and battery_discharge_mw > tol: raise ValueError("simultaneous charge/discharge forbidden")
        grid=self.critical_mw+self.fixed_auxiliary_mw+flexible_compute_mw+battery_charge_mw-battery_discharge_mw
        if grid < -tol: raise ValueError("export is not supported by this model")
        return max(0.0,grid)
