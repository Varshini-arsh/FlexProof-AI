from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
REQUEST = dict(scenario_id="FP001-RECOVERY", requested_reduction_mw=5, duration_minutes=60,
               reliability_target=0.95, battery_soc_percent=35)


def test_nominal_api_includes_joint_recoveryguard_schedule():
    response = client.post("/api/scenarios/run", json=REQUEST)
    assert response.status_code == 200, response.text
    body = response.json()
    recovery = body["result"]["recovery"]
    rows = recovery["telemetry"]["recovery_time_series"]
    assert recovery["status"] == "completed"
    assert len(rows) == 48
    assert rows[0]["start_minute"] == 60 and rows[-1]["end_minute"] == 300
    for row in rows:
        assert abs(row["grid_import_mw"] - (17 + row["battery_charge_mw"] + row["workload_recovery_mw"])) < 1e-6
        assert row["grid_import_mw"] <= 20 + 1e-6
    assert rows[-1]["battery_soc_end"] >= 0.35 - 1e-6
    assert rows[-1]["workload_backlog_end_mwh"] <= 1e-6


def test_event_success_does_not_hide_infeasible_recovery():
    response = client.post("/api/scenarios/run", json={**REQUEST, "recovery_grid_ceiling_mw": 17})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["complete_event_success"] is True
    assert result["recovery"]["status"] == "infeasible"
    assert not result["recovery"]["telemetry"]["recovery_time_series"]
    assert result["recovery"]["infeasibility_reason"]
    assert result["recovery"]["violations"]
