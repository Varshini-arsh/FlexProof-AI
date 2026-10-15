import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
REQUEST = dict(scenario_id="FP001-API-TEST", requested_reduction_mw=5,
               duration_minutes=60, reliability_target=0.95, battery_soc_percent=35)


def test_nominal_api_power_and_energy_and_identity():
    response = client.post("/api/scenarios/run", json=REQUEST)
    assert response.status_code == 200, response.text
    body = response.json()
    result = body["result"]
    assert body["simulation_type"] == "nominal"
    assert body["reliability_certified"] is False
    assert result["scenario_id"] == REQUEST["scenario_id"]
    assert result["reliability"]["status"] == "not_evaluated"
    rows = result["telemetry"]["event_time_series"]
    assert len(rows) == 12
    assert all(row["grid_import_mw"] == pytest.approx(15) for row in rows)
    assert result["telemetry"]["final_battery_soc"] == pytest.approx(0.35 - 1.4 / 0.95 / 10)
    assert result["telemetry"]["final_workload_backlog_mwh"] == pytest.approx(3.6)
    assert result["complete_event_success"] is True


def test_inputs_propagate_and_nominal_execution_is_deterministic():
    request = {**REQUEST, "reliability_target": 0.99, "random_seed": 9182, "scenario_id": "CUSTOM"}
    first = client.post("/api/scenarios/run", json=request).json()["result"]
    second = client.post("/api/scenarios/run", json=request).json()["result"]
    assert first["run_id"] == second["run_id"]
    assert first["telemetry"] == second["telemetry"]
    assert first["recovery"]["telemetry"] == second["recovery"]["telemetry"]
    assert first["reliability"]["target"] == 0.99
    assert first["random_seed"] == 9182
    assert first["scenario_id"] == "CUSTOM"


@pytest.mark.parametrize("change", [dict(duration_minutes=17), dict(battery_soc_percent=19),
                                    dict(reliability_target=1), dict(requested_reduction_mw=-1),
                                    dict(scenario_id="../bad"), dict(unknown_field=1)])
def test_invalid_inputs_rejected(change):
    assert client.post("/api/scenarios/run", json={**REQUEST, **change}).status_code == 422


def test_unachievable_request_has_explanation():
    response = client.post("/api/scenarios/run", json={**REQUEST, "requested_reduction_mw": 20})
    assert response.status_code == 422
    assert "capability" in response.json()["detail"]


def test_reserve_soc_does_not_report_nominal_success():
    response = client.post("/api/scenarios/run", json={**REQUEST, "battery_soc_percent": 20})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "infeasible"
    assert result["complete_event_success"] is False
    assert result["violations"]
    assert result["infeasibility_reason"]


def test_health_reports_imported_engine():
    assert client.get("/api/health").json()["simulation_connected"] is True
