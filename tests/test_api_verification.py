from copy import deepcopy

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
REQUEST = {"scenario_id": "VERIFY-API", "requested_reduction_mw": 5, "duration_minutes": 60,
           "reliability_target": 0.95, "battery_soc_percent": 35}


def test_run_endpoint_returns_independently_recomputed_verification():
    body = client.post("/api/scenarios/run", json=REQUEST).json()
    verification = body["independent_verification"]
    assert verification["status"] == "pass", verification["failed_checks"]
    assert verification["independent_check"] is True
    assert verification["certification"] is False


def test_verification_endpoint_fails_tampered_telemetry_despite_success_flags():
    body = client.post("/api/scenarios/run", json=REQUEST).json()
    result = deepcopy(body["result"])
    result["complete_event_success"] = True
    result["telemetry"]["event_time_series"][0]["battery_soc_end"] = 0.1
    response = client.post("/api/evidence/verify", json={"scenario": body["scenario"], "result": result})
    assert response.status_code == 200
    assert response.json()["status"] == "fail"


def test_verification_endpoint_reports_incomplete_record():
    body = client.post("/api/scenarios/run", json=REQUEST).json()
    result = deepcopy(body["result"])
    result["telemetry"]["event_time_series"].pop()
    response = client.post("/api/evidence/verify", json={"scenario": body["scenario"], "result": result})
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_evidence"


def test_verification_endpoint_checks_recorded_hashes():
    body = client.post("/api/scenarios/run", json=REQUEST).json()
    verification = body["independent_verification"]
    response = client.post("/api/evidence/verify", json={"scenario": body["scenario"], "result": body["result"],
        "expected_input_hash": verification["metrics"]["input_hash"],
        "expected_evidence_hash": "0" * 64})
    assert response.json()["status"] == "fail"
    assert "evidence_hash" in response.json()["failed_checks"]
