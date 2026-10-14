from pathlib import Path
import pytest
import yaml
from optimization.commitment import calibrate_commitment, evaluate_commitment, wilson_lower

ROOT=Path(__file__).parents[1]
CONFIG=yaml.safe_load((ROOT/"configs"/"fp001.yaml").read_text(encoding="utf-8"))

def test_wilson_lower_is_below_observed_rate():
    assert 0 < wilson_lower(95,100) < 0.95

def test_commitment_calibration_uses_complete_event_scenarios_and_confidence_bound():
    result=calibrate_commitment(CONFIG,n_scenarios=1000,seed=900,step_mw=1.0)
    assert 0 < result["accepted_commitment_mw"] < 5.0
    assert result["selected_evidence"]["simultaneous_lower_bound"] >= 0.95
    assert result["selected_evidence"]["sample_count"] == 1000
    assert result["status"] == "confirmed"

def test_single_commitment_evaluation_is_reproducible():
    one=evaluate_commitment(CONFIG,3.5,n_scenarios=50,seed=700)
    two=evaluate_commitment(CONFIG,3.5,n_scenarios=50,seed=700)
    assert one == two
    assert one["lower_confidence_bound"] <= one["estimate"]

def test_risk_aware_mpc_records_calibration_as_not_holdout():
    from baselines.risk_aware_mpc import run_risk_aware_mpc
    result=run_risk_aware_mpc(CONFIG,calibration_scenarios=1000,calibration_seed=900,commitment_step_mw=1.0)
    assert result["controller"] == "risk_aware_mpc"
    assert 0 < result["accepted_commitment_mw"] < 5.0
    assert result["reliability"]["evidence_split"] == "calibration"
    assert result["reliability"]["confidence_lower_bound"] >= 0.95