from pathlib import Path
import json
import jsonschema
import pytest
import yaml
from optimization.recovery import plan_recovery
from simulator.engine import run_nominal_event

ROOT=Path(__file__).parents[1]
CONFIG=yaml.safe_load((ROOT/"configs"/"fp001.yaml").read_text(encoding="utf-8"))

def test_recovery_jointly_restores_backlog_and_battery():
    event=run_nominal_event(CONFIG)
    result=plan_recovery(CONFIG,
        backlog_mwh=event["telemetry"]["final_workload_backlog_mwh"],
        current_soc=event["telemetry"]["final_battery_soc"])
    assert result["status"]=="completed"
    assert result["telemetry"]["final_workload_backlog_mwh"]==pytest.approx(0,abs=1e-7)
    assert result["telemetry"]["final_battery_soc"]>=CONFIG["recovery"]["target_soc"]-1e-7
    rows=result["telemetry"]["recovery_time_series"]
    assert len(rows)==48
    assert max(row["grid_import_mw"] for row in rows)<=20+1e-7
    assert all(row["workload_recovery_mw"]+row["battery_charge_mw"]<=3+1e-7 for row in rows)

def test_recovery_result_matches_schema():
    event=run_nominal_event(CONFIG)
    result=plan_recovery(CONFIG,backlog_mwh=event["telemetry"]["final_workload_backlog_mwh"],
                         current_soc=event["telemetry"]["final_battery_soc"])
    schema=json.loads((ROOT/"contracts"/"result.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(result,schema)

def test_infeasible_recovery_is_reported_without_fallback():
    cfg={**CONFIG,"recovery":{**CONFIG["recovery"],"horizon_minutes":5,
        "target_minute":65,"clear_deferred_work_by_minute":65}}
    result=plan_recovery(cfg,backlog_mwh=3.6,current_soc=0.2026)
    assert result["status"]=="infeasible"
    assert result["telemetry"]["recovery_time_series"]==[]
    assert result["infeasibility_reason"]

def test_shared_capacity_prevents_double_counting():
    event=run_nominal_event(CONFIG)
    result=plan_recovery(CONFIG,backlog_mwh=event["telemetry"]["final_workload_backlog_mwh"],
                         current_soc=event["telemetry"]["final_battery_soc"])
    for row in result["telemetry"]["recovery_time_series"]:
        assert row["workload_recovery_mw"]+row["battery_charge_mw"]<=3+1e-7
