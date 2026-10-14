"""Grid-event configuration and complete-event delivery checks."""
from dataclasses import dataclass
from math import isfinite

TOL = 1e-9

@dataclass(frozen=True, slots=True)
class GridEvent:
    start_minute: int
    requested_reduction_mw: float
    duration_minutes: int
    interval_minutes: int
    accepted_commitment_mw: float

    def __post_init__(self):
        if self.start_minute < 0 or self.duration_minutes <= 0 or self.interval_minutes <= 0:
            raise ValueError("event time values must be positive (start may be zero)")
        if self.duration_minutes % self.interval_minutes:
            raise ValueError("duration must be an integer multiple of interval")
        if not isfinite(self.requested_reduction_mw) or self.requested_reduction_mw < 0:
            raise ValueError("requested reduction must be finite and nonnegative")
        if not isfinite(self.accepted_commitment_mw) or not 0 <= self.accepted_commitment_mw <= self.requested_reduction_mw + TOL:
            raise ValueError("accepted commitment must be within the grid request")

    @property
    def steps(self) -> int:
        return self.duration_minutes // self.interval_minutes

    def assess_delivery(self, *, baseline_mw: float, grid_import_mw: float) -> dict:
        if not isfinite(baseline_mw) or not isfinite(grid_import_mw) or baseline_mw < 0 or grid_import_mw < 0:
            raise ValueError("grid measurements must be finite and nonnegative")
        delivered = baseline_mw - grid_import_mw
        shortfall = max(0.0, self.accepted_commitment_mw - delivered)
        return {"delivered_reduction_mw": delivered, "shortfall_mw": shortfall,
                "success": shortfall <= TOL}
