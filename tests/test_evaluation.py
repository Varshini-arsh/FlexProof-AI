from pathlib import Path
import json
import pytest
import yaml

from evaluation.compare import compare_controllers
from evaluation.closed_loop import run_closed_loop_rafc_evaluation, _holm_adjust_pairwise, _recovery_metrics
from evaluation.recovery_sensitivity import run_recovery_sensitivity
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
    rolling=result["ablations"]["rolling_reoptimization_disabled"]
    assert rolling["status"]=="nominal_schedule_comparison_only"
    assert rolling["rolling"]["reoptimization_count"]==12
    assert rolling["heldout_effect"].startswith("not_estimated")
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


def test_closed_loop_rafc_evaluation_uses_disjoint_paired_scenarios_and_exports(tmp_path):
    result=run_closed_loop_rafc_evaluation(CONFIG,calibration_scenarios=80,
        calibration_seed=1000,test_scenarios=12,test_seed=3000,
        commitment_step_mw=1.0,output_dir=tmp_path)
    assert result["paired_disturbances"] is True
    assert result["heldout_sample_count"]==12
    assert result["commitment_calibration"]["heldout_data_used"] is False
    assert result["calibration_sample_count"]==80
    assert {row["controller"] for row in result["results"]}=={
        "fixed_horizon","rolling_risk_aware_mpc","rolling_rafc_v"}
    assert result["paired_tests"]["fixed_horizon_vs_rolling_rafc_v"]["event_mcnemar"]["sample_count"]==12
    assert len(result["scenarios"])==12
    by_controller={row["controller"]:row for row in result["results"]}
    assert by_controller["fixed_horizon"]["event_solver_runtime_case_count"]==0
    assert by_controller["rolling_rafc_v"]["event_solver_runtime_case_count"]==12
    assert "solver_runtime_seconds" not in result["paired_tests"][
        "fixed_horizon_vs_rolling_rafc_v"]["paired_mean_difference_ci_first_minus_second"]
    assert (tmp_path/"closed_loop_scenarios.csv").exists()
    assert json.loads((tmp_path/"closed_loop_comparison.json").read_text(encoding="utf-8"))["heldout_sample_count"]==12


def test_closed_loop_rafc_refuses_overlapping_seed_ranges():
    with pytest.raises(ValueError,match="must be disjoint"):
        run_closed_loop_rafc_evaluation(CONFIG,calibration_scenarios=20,
            calibration_seed=100,test_scenarios=20,test_seed=110)


def test_closed_loop_holm_adjustment_is_monotone_and_familywise():
    pairs={}
    for name,pvalue in (("a",0.01),("b",0.03),("c",0.2)):
        pairs[name]={"event_mcnemar":{"p_value":pvalue},
                     "event_recovery_mcnemar":{"p_value":pvalue}}
    _holm_adjust_pairwise(pairs)
    values=[pairs[name]["event_mcnemar"]["holm_adjusted_p_value"] for name in ("a","b","c")]
    assert values==pytest.approx([0.03,0.06,0.2])


def test_recovery_sensitivity_exports_feasibility_case(tmp_path):
    result=run_recovery_sensitivity(CONFIG,backlog_mwh_values=(0.0,),
        current_soc_values=(0.35,),grid_ceiling_mw_values=(20.0,),output_dir=tmp_path)
    assert result["case_count"]==1
    assert result["cases"][0]["recovery_feasible"] is True
    assert (tmp_path/"recovery_sensitivity.csv").exists()
    assert json.loads((tmp_path/"recovery_sensitivity.json").read_text(encoding="utf-8"))["case_count"]==1


def test_infeasible_shared_recovery_is_not_mislabeled_as_individual_deadline_miss():
    constrained={**CONFIG,"recovery":{**CONFIG["recovery"],"grid_import_ceiling_mw":18.0}}
    result,metrics=_recovery_metrics(constrained,backlog=4.0,soc=0.30)
    assert result["status"]=="infeasible"
    assert metrics["recovery_feasible"] is False
    assert metrics["deadline_miss"] is False
    assert metrics["soc_target_miss"] is False
