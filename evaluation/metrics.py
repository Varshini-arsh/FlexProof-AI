"""Statistical summaries for held-out scenario outcomes."""
from __future__ import annotations
from math import sqrt
from statistics import NormalDist


def wilson_interval(successes: int, trials: int, *, confidence: float = 0.95) -> list[float]:
    if trials<=0 or not 0<=successes<=trials or not 0<confidence<1:
        raise ValueError("invalid binomial inputs")
    z=NormalDist().inv_cdf(0.5+confidence/2)
    p=successes/trials
    z2=z*z
    denominator=1+z2/trials
    center=(p+z2/(2*trials))/denominator
    radius=z*sqrt(p*(1-p)/trials+z2/(4*trials*trials))/denominator
    return [max(0.0,center-radius),min(1.0,center+radius)]
