from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
REQUEST = dict(scenario_id="FP001-RISK", requested_reduction_mw=5, duration_minutes=60,
               reliability_target=0.95, battery_soc_percent=35, random_seed=900,
               controller="rafc_v", calibration_scenarios=1000, commitment_step_mw=1.0)


def test_rafc_api_preserves_calibration_and_recovery_evidence():
    response = client.post("/api/scenarios/run", json=REQUEST)
    assert response.status_code == 200, response.text
    body = response.json()
    result = body["result"]
    assert result["controller"] == "rafc_v"
    assert result["controller_version"]
    assert 0 < result["accepted_commitment_mw"] <= 5
    assert result["reliability"]["evidence_split"] == "calibration"
    assert result["reliability"]["confidence_lower_bound"] >= 0.95
    assert result["recovery"]["status"] == "completed"
    assert len(result["telemetry"]["event_time_series"]) == 12
    assert body["reliability_certified"] is False


def test_assessment_distinguishes_candidate_screen_from_heldout_validation():
    response = client.post("/api/commitments/evaluate", json=REQUEST)
    assert response.status_code == 200
    evidence = response.json()
    assert evidence["calibration"]["evidence_split"] == "calibration"
    assert evidence["calibration"]["simultaneous_lower_bound"] >= 0.95
    assert evidence["held_out_validation"]["status"] == "unavailable"
    assert evidence["calibration"]["wilson_interval"][0] <= evidence["calibration"]["estimate"] <= evidence["calibration"]["wilson_interval"][1]
    assert evidence["candidate_evidence"]


def test_small_calibration_cannot_claim_high_confidence_reliability():
    response = client.post("/api/commitments/evaluate", json={**REQUEST, "reliability_target": 0.99, "calibration_scenarios": 100})
    assert response.status_code == 200
    assert response.json()["feasibility_status"] == "unconfirmed"
    assert response.json()["recommended_commitment_mw"] == 0
    assert response.json()["calibration"]["estimate"] is None


def test_short_event_keeps_four_hour_recovery_inside_declared_horizon():
    response = client.post("/api/scenarios/run", json={**REQUEST, "duration_minutes": 15})
    assert response.status_code == 200, response.text
    config = response.json()["scenario"]
    assert config["recovery"]["target_minute"] == 255
    assert config["recovery"]["clear_deferred_work_by_minute"] == 255
    assert len(response.json()["result"]["telemetry"]["event_time_series"]) == 3


def test_unsupported_controller_is_rejected():
    assert client.post("/api/scenarios/run", json={**REQUEST, "controller": "invented"}).status_code == 422
