from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.models import ScenarioRequest
from backend.app.services.simulation import build_config
from backend.app.services.verification import verify_result
from flexproof.engine import run_scenario


def test_health_and_fp001_contract():
    client = TestClient(main.app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["simulation_connected"] is True
    scenario = client.get("/api/scenarios/fp001")
    assert scenario.status_code == 200
    assert scenario.json()["scenario"]["scenario_id"] == "FP-001"


def test_validation_rejects_non_interval_duration():
    client = TestClient(main.app)
    response = client.post("/api/scenarios/validate", json={"duration_minutes": 17})
    assert response.status_code == 422


def test_run_persists_result_verification_and_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("FLEXPROOF_DB_PATH", str(tmp_path / "runs.sqlite3"))
    client = TestClient(main.app)
    response = client.post("/api/scenarios/run", json={"controller": "nominal"})
    assert response.status_code == 200, response.text
    run_id = response.json()["result"]["run_id"]
    history = client.get("/api/runs")
    assert history.status_code == 200
    assert history.json()["runs"][0]["run_id"] == run_id
    detail = client.get(f"/api/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["verification"]["status"] == "passed"
    report = client.get(f"/api/runs/{run_id}/report.pdf")
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content.startswith(b"%PDF")


def test_rafc_v_request_uses_public_engine_and_keeps_evidence_unverified(tmp_path, monkeypatch):
    monkeypatch.setenv("FLEXPROOF_DB_PATH", str(tmp_path / "rafc-runs.sqlite3"))
    client = TestClient(main.app)
    response = client.post("/api/scenarios/run", json={
        "controller": "rafc_v", "calibration_scenarios": 1000,
        "random_seed": 900, "commitment_step_mw": 1.0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reliability_certified"] is False
    assert body["result"]["controller"] == "rafc_v"
    assert body["result"]["reliability"]["evidence_split"] == "calibration"
    assert body["result"]["accepted_commitment_mw"] > 0
    assert body["verification"]["status"] == "passed", body["verification"]["failed_checks"]
    assert body["result"]["independent_verification"]["certification"] is False


def test_independent_verifier_detects_tampered_grid_measurement():
    config = build_config(ScenarioRequest(controller="nominal"))
    result = run_scenario(config, controller="nominal")
    result["telemetry"]["event_time_series"][0]["grid_import_mw"] += 0.1
    verification = verify_result(config, result)
    assert verification["status"] == "failed"
    assert "event_step_0_power_balance" in verification["failed_checks"]

\n