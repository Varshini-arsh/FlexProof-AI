import csv
import json
from io import StringIO

from fastapi.testclient import TestClient
from jsonschema import validate
from pathlib import Path

from backend.app.main import app

client = TestClient(app)
REQUEST = {"scenario_id": "EXPORT-API", "requested_reduction_mw": 5, "duration_minutes": 60,
           "reliability_target": 0.95, "battery_soc_percent": 35}


def evidence():
    response = client.post("/api/scenarios/run", json=REQUEST)
    assert response.status_code == 200
    body = response.json()
    return {"scenario": body["scenario"], "result": body["result"]}


def test_machine_readable_export_has_identifiers_hashes_and_verification():
    response = client.post("/api/evidence/export", json=evidence())
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "1.0.0"
    assert body["scenario_id"] == "EXPORT-API"
    assert body["run_id"]
    assert len(body["input_hash_sha256"]) == len(body["evidence_hash_sha256"]) == 64
    assert body["independent_verification"]["status"] == "pass"
    assert body["certification"] is False
    schema = Path(__file__).parents[1] / "contracts" / "evidence.schema.json"
    validate(body, json.loads(schema.read_text(encoding="utf-8")))


def test_csv_export_contains_all_event_and_recovery_intervals():
    response = client.post("/api/evidence/telemetry.csv", json=evidence())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(StringIO(response.text)))
    assert sum(row["phase"] == "event" for row in rows) == 12
    assert sum(row["phase"] == "recovery" for row in rows) == 48
    assert all(row["delivered_reduction_mw"] for row in rows if row["phase"] == "event")


def test_pdf_report_is_a_valid_pdf_download():
    response = client.post("/api/evidence/report.pdf", json=evidence())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
