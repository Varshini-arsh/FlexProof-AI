from pathlib import Path
import json
import pytest
import yaml

from evaluation.compare import compare_controllers
from evaluation.metrics import wilson_interval
from evaluation.statistical_tests import exact_mcnemar
from evaluation.plots import plot_controller_comparison

ROOT=Path(__file__).parents[1]
CONFIG=yaml.safe_load((ROOT/"configs"/"fp001.yaml").read_text(encoding="utf-8"))


def test_wilson_interval_contains_observed_rate():
    low,high=wilson_interval(95,100)
    assert low<0.95<high


def test_exact_mcnemar_counts_paired_disagreements():
    result=exact_mcnemar([True,True,False,False],[True,False,True,False])
    assert result["first_only_successes"]==1
    assert result["second_only_successes"]==1
    assert result["p_value"]==1.0


def test_comparison_uses_shared_disjoint_heldout_set_and_exports(tmp_path):
    result=compare_controllers(CONFIG,calibration_scenarios=60,calibration_seed=1000,
        test_scenarios=80,test_seed=2000,commitment_step_mw=1.0,output_dir=tmp_path)
    assert result["shared_test_scenarios"] is True
    assert result["calibration_seed_start"]==1000
    assert result["heldout_seed_start"]==2000
    assert result["computational_failure_rate"]==0
    assert result["evidence_complete"] is True
    assert result["ablations"]["rolling_reoptimization_disabled"]["status"]=="not_implemented"
    assert {row["controller"] for row in result["results"]}=={
        "rule_based","deterministic_mpc","risk_aware_mpc","rafc_v"}
    assert all(row["evidence_split"]=="heldout_test" for row in result["results"])
    assert "event_and_recovery" in result["paired_tests"]
    assert (tmp_path/"four_controller_comparison.csv").exists()
    assert json.loads((tmp_path/"four_controller_comparison.json").read_text(encoding="utf-8"))["heldout_sample_count"]==80
    assert all(row["nominal_recovery_status"] in ("completed","infeasible") for row in result["results"])
    assert all(row["battery_reserve_violation_scenarios"]>=0 for row in result["results"])
    assert plot_controller_comparison(result,tmp_path/"comparison.png").exists()


def test_comparison_refuses_overlapping_calibration_and_test_seed_ranges():
    with pytest.raises(ValueError,match="must be disjoint"):
        compare_controllers(CONFIG,calibration_scenarios=20,calibration_seed=100,
            test_scenarios=20,test_seed=110)
