import pytest
from simulator.grid import GridEvent

def test_fp001_has_twelve_five_minute_steps():
    e=GridEvent(0,5,60,5,5)
    assert e.steps == 12
    assert e.assess_delivery(baseline_mw=20,grid_import_mw=15)["success"]

def test_complete_event_failure_detected_per_interval():
    e=GridEvent(0,5,60,5,5)
    assert not e.assess_delivery(baseline_mw=20,grid_import_mw=15.01)["success"]

def test_nondivisible_duration_rejected():
    with pytest.raises(ValueError):
        GridEvent(0,5,61,5,5)

def test_commitment_cannot_exceed_request():
    with pytest.raises(ValueError):
        GridEvent(0,5,60,5,5.1)
