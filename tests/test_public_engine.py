from pathlib import Path
import json
import jsonschema
import pytest
import yaml

from flexproof.engine import evaluate_commitment, load_scenario, run_scenario
from simulator.models import ScenarioConfig

ROOT=Path(__file__).parents[1]
CONFIG_PATH=ROOT/"configs"/"fp001.yaml"
SCHEMA=json.loads((ROOT/"contracts"/"result.schema.json").read_text(encoding="utf-8"))


def test_public_api_loads_yaml_and_returns_typed_scenario():
    config=load_scenario(CONFIG_PATH)
    assert isinstance(config,ScenarioConfig)
    assert config.scenario_id=="FP-001"
    assert config.reliability_target==pytest.approx(0.95)


def test_public_api_runs_baseline_and_joint_recovery_from_mapping():
    config=yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    result=run_scenario(config,controller="rule_based")
    jsonschema.validate(result,SCHEMA)
    assert result["controller"]=="rule_based"
    assert result["recovery"]["status"]=="completed"
    assert result["recovery"]["telemetry"]["final_workload_backlog_mwh"]<=1e-7


def test_public_api_unknown_controller_returns_contract_shaped_invalid_result():
    result=run_scenario(CONFIG_PATH,controller="made_up")
    jsonschema.validate(result,SCHEMA)
    assert result["status"]=="invalid_input"


def test_public_api_rejects_physically_invalid_recovery_target():
    config=yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["recovery"]["grid_import_ceiling_mw"]=16.0
    result=run_scenario(config,controller="nominal")
    jsonschema.validate(result,SCHEMA)
    assert result["status"]=="invalid_input"
    assert "grid ceiling" in result["infeasibility_reason"]


def test_public_commitment_api_is_seed_reproducible_and_marks_calibration():
    first=evaluate_commitment(CONFIG_PATH,n_scenarios=40,seed=812,step_mw=1.0)
    second=evaluate_commitment(CONFIG_PATH,n_scenarios=40,seed=812,step_mw=1.0)
    assert first==second
    assert first["recovery_aware"] is True
    assert first["seed_start"]==812


def test_checked_in_example_fixtures_match_both_json_schemas():
    scenario_schema=json.loads((ROOT/"contracts"/"scenario.schema.json").read_text(encoding="utf-8"))
    example_dir=ROOT/"contracts"/"examples"
    example=json.loads((example_dir/"fp001_scenario.json").read_text(encoding="utf-8"))
    result=json.loads((example_dir/"fp001_nominal_result.json").read_text(encoding="utf-8"))
    jsonschema.validate(example,scenario_schema)
    jsonschema.validate(result,SCHEMA)
    actual=run_scenario(example,controller="nominal")
    assert actual["run_id"]==result["run_id"]
    assert actual["accepted_commitment_mw"]==result["accepted_commitment_mw"]
    assert len(actual["telemetry"]["event_time_series"])==len(result["telemetry"]["event_time_series"])
    assert [row["grid_import_mw"] for row in actual["telemetry"]["event_time_series"]]==pytest.approx(
        [row["grid_import_mw"] for row in result["telemetry"]["event_time_series"]],abs=1e-9)
    assert actual["recovery"]["telemetry"]["final_battery_soc"]==pytest.approx(
        result["recovery"]["telemetry"]["final_battery_soc"],abs=1e-9)
