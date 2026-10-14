import pytest
from simulator.battery import Battery

@pytest.fixture
def battery(): return Battery(10,0.35,0.20,1.0,3,2,0.95,0.95)

def test_fp001_reserve_energy(battery):
    assert battery.usable_dc_energy_mwh() == pytest.approx(1.5)
    assert battery.usable_ac_energy_mwh() == pytest.approx(1.425)

def test_discharge_soc_and_energy_balance(battery):
    soc=battery.step(0.35,discharge_mw=1.4,timestep_hours=1)
    assert soc == pytest.approx(0.35-(1.4/0.95)/10)

def test_charge_soc_and_efficiency(battery):
    assert battery.step(0.35,charge_mw=2,timestep_hours=0.5) == pytest.approx(0.445)

def test_reserve_boundary_rejects_excess_discharge(battery):
    with pytest.raises(ValueError): battery.step(0.20,discharge_mw=0.01,timestep_hours=1/12)

def test_empty_or_reserve_soc_has_no_usable_energy(battery):
    assert battery.usable_dc_energy_mwh(0.20) == pytest.approx(0)

def test_full_battery_rejects_charge(battery):
    with pytest.raises(ValueError): battery.step(1,charge_mw=0.1,timestep_hours=1/12)

def test_limits_and_exclusivity(battery):
    with pytest.raises(ValueError): battery.step(0.5,discharge_mw=3.1,timestep_hours=1/12)
    with pytest.raises(ValueError): battery.step(0.5,charge_mw=1,discharge_mw=1,timestep_hours=1/12)

def test_nonfinite_capacity_rejected():
    with pytest.raises(ValueError): Battery(float('inf'),0.35,0.2,1,3,2,0.95,0.95)

def test_invalid_efficiency():
    with pytest.raises(ValueError): Battery(10,0.35,0.2,1,3,2,1.1,0.95)

def test_repeated_intervals_respect_reserve(battery):
    soc=0.35
    for _ in range(12):
        soc=battery.step(soc,discharge_mw=1.425,timestep_hours=5/60)
    assert soc == pytest.approx(0.20)
