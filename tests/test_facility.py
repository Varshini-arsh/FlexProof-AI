import pytest
from simulator.facility import Facility

@pytest.fixture
def facility(): return Facility(12.0, 4.0, 4.0)

def test_baseline_and_exact_power_balance(facility):
    assert facility.baseline_grid_import_mw == pytest.approx(20.0)
    assert facility.grid_import_mw(flexible_compute_mw=0.4, battery_discharge_mw=1.4) == pytest.approx(15.0)

def test_zero_battery_dispatch(facility):
    assert facility.grid_import_mw(flexible_compute_mw=4.0) == pytest.approx(20.0)

def test_maximum_facility_demand(facility):
    assert facility.grid_import_mw(flexible_compute_mw=4.0, battery_charge_mw=2.0) == pytest.approx(22.0)

def test_nonfinite_load_rejected():
    with pytest.raises(ValueError): Facility(float('nan'),0,0)
    with pytest.raises(ValueError): Facility(0,float('inf'),0)

def test_negative_load_rejected():
    with pytest.raises(ValueError): Facility(-1,0,0)

def test_out_of_range_flexible_load(facility):
    with pytest.raises(ValueError): facility.grid_import_mw(flexible_compute_mw=4.1)

def test_simultaneous_charge_discharge_rejected(facility):
    with pytest.raises(ValueError): facility.grid_import_mw(flexible_compute_mw=0,battery_charge_mw=1,battery_discharge_mw=1)
