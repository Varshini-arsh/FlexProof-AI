from pathlib import Path
import pytest
import yaml
from baselines.deterministic_mpc import solve_deterministic_dispatch
from baselines.rule_based import run_rule_based

ROOT=Path(__file__).parents[1]
CONFIG=yaml.safe_load((ROOT/"configs"/"fp001.yaml").read_text(encoding="utf-8"))

def test_rule_based_respects_energy_and_delivers_fp001():
    result=run_rule_based(CONFIG)
    assert result["complete_event_success"]
    assert result["dispatch_plan"]["battery_discharge_mw"] == pytest.approx(1.0)
    assert result["telemetry"]["final_workload_backlog_mwh"] == pytest.approx(4.0)
    assert result["telemetry"]["final_battery_soc"] >= CONFIG["battery"]["min_soc"]

def test_deterministic_mpc_solves_with_highs_and_reports_complete_trace():
    result=solve_deterministic_dispatch(CONFIG)
    assert result["status"] == "completed"
    assert result["solver_metadata"]["solver"] == "HiGHS"
    assert result["solver_metadata"]["termination"] == "optimal"
    assert len(result["telemetry"]["event_time_series"]) == 12
    assert all(row["success"] for row in result["telemetry"]["event_time_series"])

def test_deterministic_mpc_exposes_unachievable_commitment():
    cfg={**CONFIG,"grid_event":{**CONFIG["grid_event"],"requested_reduction_mw":6.0}}
    result=solve_deterministic_dispatch(cfg)
    assert result["status"] == "infeasible"
    assert not result["complete_event_success"]
    assert any(v["type"] == "event_shortfall" for v in result["violations"])
    assert any(row["shortfall_mw"] > 0 for row in result["telemetry"]["event_time_series"])
def test_deterministic_result_matches_result_schema():
    import json
    import jsonschema
    schema=json.loads((ROOT/"contracts"/"result.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(solve_deterministic_dispatch(CONFIG),schema)

def test_solver_failure_returns_contract_shaped_error(monkeypatch):
    import json
    import jsonschema
    import baselines.deterministic_mpc as module
    class FailedSolver:
        options={}
        def solve(self,model):
            raise RuntimeError("simulated solver failure")
    monkeypatch.setattr(module.pyo,"SolverFactory",lambda name: FailedSolver())
    result=module.solve_deterministic_dispatch(CONFIG)
    schema=json.loads((ROOT/"contracts"/"result.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(result,schema)
    assert result["status"] == "solver_error"
    assert "simulated solver failure" in result["infeasibility_reason"]
