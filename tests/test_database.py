from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
REQUEST = {"scenario_id": "PERSIST-001", "requested_reduction_mw": 5, "duration_minutes": 60,
           "reliability_target": 0.95, "battery_soc_percent": 35}


def test_run_is_persisted_and_reconstructed_from_normalized_tables():
    response = client.post("/api/scenarios/run", json=REQUEST)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["storage_status"] == "persisted"
    run_id = body["result"]["run_id"]
    history = client.get("/api/runs")
    assert history.status_code == 200
    assert any(item["run_id"] == run_id for item in history.json()["runs"])
    record = client.get(f"/api/runs/{run_id}")
    assert record.status_code == 200
    loaded = record.json()
    assert loaded["scenario"]["scenario_id"] == REQUEST["scenario_id"]
    assert len(loaded["result"]["telemetry"]["event_time_series"]) == 12
    assert len(loaded["result"]["recovery"]["telemetry"]["recovery_time_series"]) == 48
    assert loaded["independent_verification"]["status"] == "pass"


def test_run_not_found_is_reported_as_404():
    response = client.get("/api/runs/no-such-run")
    assert response.status_code == 404


def test_export_records_metadata_for_persisted_run():
    body = client.post("/api/scenarios/run", json={**REQUEST, "scenario_id": "PERSIST-REPORT"}).json()
    export = client.post("/api/evidence/export", json={"scenario": body["scenario"], "result": body["result"]})
    assert export.status_code == 200
    assert export.json()["report_metadata_recorded"] is True

def test_identical_requests_create_distinct_history_records():
    first = client.post("/api/scenarios/run", json=REQUEST).json()
    second = client.post("/api/scenarios/run", json=REQUEST).json()
    assert first["result"]["run_id"] != second["result"]["run_id"]
    assert first["engine_run_id"] == second["engine_run_id"]
    runs = client.get("/api/runs").json()["runs"]
    ids = {row["run_id"] for row in runs}
    assert first["result"]["run_id"] in ids
    assert second["result"]["run_id"] in ids
