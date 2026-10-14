from pathlib import Path
import json
import jsonschema
import yaml

from optimization.rafc_v import run_rafc_v

ROOT=Path(__file__).parents[1]
CONFIG=yaml.safe_load((ROOT/"configs"/"fp001.yaml").read_text(encoding="utf-8"))


def test_rafc_v_integrates_calibrated_commitment_event_and_recovery():
    result=run_rafc_v(CONFIG,calibration_scenarios=1000,calibration_seed=900,
                      commitment_step_mw=1.0)
    assert result["controller"]=="rafc_v"
    assert result["status"]=="completed"
    assert 0 < result["accepted_commitment_mw"] < CONFIG["grid_event"]["requested_reduction_mw"]
    assert result["reliability"]["recovery_aware"] is True
    assert result["reliability"]["evidence_split"]=="calibration"
    assert result["reliability"]["confidence_lower_bound"]>=result["reliability"]["target"]
    recovery=result["recovery"]
    assert recovery["status"]=="completed"
    assert recovery["telemetry"]["final_battery_soc"]>=CONFIG["recovery"]["target_soc"]-1e-7
    assert recovery["telemetry"]["final_workload_backlog_mwh"]<=1e-7
    assert recovery["telemetry"]["max_grid_import_mw"]<=CONFIG["recovery"]["grid_import_ceiling_mw"]+1e-7
    schema=json.loads((ROOT/"contracts"/"result.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(result,schema)


def test_rafc_v_does_not_claim_reliability_with_inadequate_evidence():
    result=run_rafc_v(CONFIG,calibration_scenarios=20,calibration_seed=1200,
                      commitment_step_mw=1.0)
    assert result["reliability"]["status"]=="unconfirmed"
    assert result["reliability"]["confidence_lower_bound"] is None
    assert result["accepted_commitment_mw"]==0


def test_rafc_v_preserves_solver_failure_without_fallback(monkeypatch):
    import optimization.rafc_v as module
    failure={"status":"solver_error","controller":"deterministic_mpc",
             "accepted_commitment_mw":3.0,"telemetry":{"event_time_series":[]},
             "violations":[]}
    monkeypatch.setattr(module,"solve_deterministic_dispatch",lambda *args,**kwargs:dict(failure))
    result=module.run_rafc_v(CONFIG,calibration_scenarios=20,calibration_seed=1200,
                             commitment_step_mw=1.0)
    assert result["status"]=="solver_error"
    assert result["accepted_commitment_mw"]==0
    assert result["rafc_v"]["fallback_schedule_used"] is False
