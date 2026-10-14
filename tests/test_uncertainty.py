from pathlib import Path
import pytest
ROOT=Path(__file__).parents[1]
from simulator.uncertainty import generate_uncertainty_scenario

def test_seed_reproducibility():
    assert generate_uncertainty_scenario(42) == generate_uncertainty_scenario(42)

def test_different_seeds_generate_distinct_scenario_records():
    assert generate_uncertainty_scenario(42) != generate_uncertainty_scenario(43)

def test_disturbance_bounds_and_units():
    x=generate_uncertainty_scenario(2026)
    assert -0.015 <= x.initial_soc_error <= 0.015
    assert -0.3 <= x.critical_power_delta_mw <= 0.3
    assert x.urgent_reclaim_mw in (0.0,0.4)
    assert x.battery_discharge_scale in (0.9,1.0)
    assert isinstance(x.meter_noise_mw,float)

def test_seed_type_validation():
    with pytest.raises(ValueError):
        generate_uncertainty_scenario(4.2)

def test_uncertainty_yaml_is_loaded_as_configured():
    from simulator.uncertainty import load_uncertainty_assumptions
    cfg=load_uncertainty_assumptions(ROOT/"configs"/"uncertainty.yaml")
    assert cfg.initial_soc_error_bound == pytest.approx(0.015)
    assert cfg.meter_noise_std_mw == pytest.approx(0.02)

def test_invalid_probability_assumption_is_rejected():
    from simulator.uncertainty import UncertaintyAssumptions
    with pytest.raises(ValueError):
        UncertaintyAssumptions(urgent_reclaim_probability=1.5)
