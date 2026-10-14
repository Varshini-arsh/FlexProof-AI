from pathlib import Path
import jsonschema
import pytest
from simulator.engine import run_nominal_event

ROOT=Path(__file__).parents[1]
CONFIG=ROOT/"configs"/"fp001.yaml"

def test_fp001_nominal_event_runs_twelve_intervals():
    result=run_nominal_event(CONFIG)
    rows=result["telemetry"]["event_time_series"]
    assert result["status"] == "completed"
    assert result["complete_event_success"]
    assert len(rows) == 12
    assert all(row["grid_import_mw"] == pytest.approx(15) for row in rows)
    assert all(row["delivered_reduction_mw"] == pytest.approx(5) for row in rows)
    assert result["telemetry"]["final_battery_soc"] == pytest.approx(0.35-(1.4/0.95)/10)
    assert result["telemetry"]["final_workload_backlog_mwh"] == pytest.approx(3.6)

def test_nominal_dispatch_is_not_reliability_certification():
    result=run_nominal_event(CONFIG)
    assert result["reliability"]["status"] == "not_evaluated"
    assert result["reliability"]["estimate"] is None
    assert "not reliability-certified" in result["commitment_basis"]

def test_identical_config_has_reproducible_output():
    first=run_nominal_event(CONFIG)
    second=run_nominal_event(CONFIG)
    assert first == second

def test_inadequate_dispatch_reports_event_shortfall():
    result=run_nominal_event(CONFIG,flexible_compute_mw=0.8,battery_discharge_mw=1.4)
    assert not result["complete_event_success"]
    assert any(item["type"] == "event_shortfall" for item in result["violations"])
    assert result["telemetry"]["final_workload_backlog_mwh"] >= 0

def test_result_is_json_compatible_and_matches_schema():
    result=run_nominal_event(CONFIG)
    jsonschema.validate(result,jsonschema.Draft202012Validator(
        __import__("json").loads((ROOT/"contracts"/"result.schema.json").read_text(encoding="utf-8"))
    ).schema)
    assert result["schema_version"] == "1.0.0"

def test_smaller_accepted_commitment_gets_consistent_nominal_schedule():
    result=run_nominal_event(CONFIG,accepted_commitment_mw=2.0)
    assert result["complete_event_success"]
    assert all(row["delivered_reduction_mw"] == pytest.approx(2.0) for row in result["telemetry"]["event_time_series"])
