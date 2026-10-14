import pytest
from simulator.workloads import Job, WorkloadQueue

def test_backlog_tracks_service_and_completion():
    q=WorkloadQueue([Job("j1",0,1.0,2.0,60,30)])
    first=q.dispatch(available_power_mw=0.5,start_minute=0,interval_minutes=30)
    assert first["work_mwh"] == pytest.approx(0.25)
    assert q.backlog_mwh == pytest.approx(0.75)
    second=q.dispatch(available_power_mw=2,start_minute=30,interval_minutes=30)
    assert second["work_mwh"] == pytest.approx(0.75)
    assert q.backlog_mwh == 0
    assert q.jobs[0].completed_minute == 60

def test_arrival_time_is_respected():
    q=WorkloadQueue([Job("late",10,1,1,60,30)])
    row=q.dispatch(available_power_mw=1,start_minute=0,interval_minutes=5)
    assert row["power_mw"] == 0
    assert q.backlog_mwh == 1

def test_deadline_miss_is_recorded_without_dropping_work():
    q=WorkloadQueue([Job("late",0,1,1,10,10)])
    q.dispatch(available_power_mw=0,start_minute=5,interval_minutes=5)
    assert q.jobs[0].deadline_missed
    assert q.backlog_mwh == 1
    assert q.violations[0]["type"] == "deadline_missed"

def test_invalid_job_rejected():
    with pytest.raises(ValueError):
        Job("bad",0,-1,1,60,30)

def test_duplicate_job_rejected():
    j=Job("same",0,1,1,60,30)
    q=WorkloadQueue([j])
    with pytest.raises(ValueError):
        q.add(Job("same",0,1,1,60,30))

def test_arrival_inside_interval_is_not_served_early():
    q=WorkloadQueue([Job("arrives-midstep",6,1,1,60,30)])
    row=q.dispatch(available_power_mw=1,start_minute=5,interval_minutes=5)
    assert row["power_mw"] == 0
    assert q.backlog_mwh == 1
