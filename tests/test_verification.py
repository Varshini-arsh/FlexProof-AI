from copy import deepcopy
import pytest

from backend.app.main import ScenarioRequest
from backend.app.services.simulation import build_config
from backend.app.services.verification import canonical_hash, evidence_hash, verify_result
from flexproof.engine import run_scenario


@pytest.fixture(scope="module")
def nominal_evidence():
    config = build_config(ScenarioRequest(scenario_id="VERIFY", requested_reduction_mw=5,
                         duration_minutes=60, reliability_target=0.95, battery_soc_percent=35).model_dump())
    return config, run_scenario(config, controller="nominal")


def test_full_nominal_and_recovery_evidence_passes(nominal_evidence):
    config, result = nominal_evidence
    verification = verify_result(config, result)
    assert verification["status"] == "pass", verification["failed_checks"]
    assert verification["certification"] is False
    assert verification["metrics"]["event_shortfall_mwh"] == pytest.approx(0)
    assert verification["metrics"]["final_workload_backlog_mwh"] <= 1e-6


@pytest.mark.parametrize("field,value", [("grid_import_mw", 17), ("battery_soc_end", 0.1),
    ("battery_discharge_mw", 3.5), ("workload_backlog_mwh", -1), ("end_minute", 7)])
def test_physical_tampering_fails_even_when_engine_flags_claim_success(nominal_evidence, field, value):
    config, original = nominal_evidence
    result = deepcopy(original)
    result["telemetry"]["event_time_series"][0][field] = value
    result["complete_event_success"] = True
    assert verify_result(config, result)["status"] == "fail"


def test_simultaneous_charging_and_discharging_is_rejected(nominal_evidence):
    config, result = deepcopy(nominal_evidence)
    result["telemetry"]["event_time_series"][0]["battery_charge_mw"] = 1
    verification = verify_result(config, result)
    assert "event_0_resource_limits" in verification["failed_checks"]


@pytest.mark.parametrize("damage", ["event_field", "event_interval", "recovery_field", "recovery_interval", "no_recovery", "configuration"])
def test_incomplete_evidence_is_explicit(nominal_evidence, damage):
    config, result = deepcopy(nominal_evidence)
    if damage == "event_field": del result["telemetry"]["event_time_series"][0]["battery_soc_start"]
    elif damage == "event_interval": result["telemetry"]["event_time_series"].pop()
    elif damage == "recovery_field": del result["recovery"]["telemetry"]["recovery_time_series"][0]["grid_import_mw"]
    elif damage == "recovery_interval": result["recovery"]["telemetry"]["recovery_time_series"].pop()
    elif damage == "no_recovery": del result["recovery"]
    else: del config["grid_event"]["requested_reduction_mw"]
    assert verify_result(config, result)["status"] == "insufficient_evidence"


def test_recovery_infeasible_is_operational_failure(nominal_evidence):
    config, result = deepcopy(nominal_evidence)
    result["recovery"] = {"status": "infeasible", "infeasibility_reason": "No shared headroom", "telemetry": {"recovery_time_series": []}}
    assert verify_result(config, result)["status"] == "fail"


def test_recovery_boundary_and_ceiling_tampering_fail(nominal_evidence):
    config, result = deepcopy(nominal_evidence)
    result["recovery"]["telemetry"]["initial_backlog_mwh"] += 0.5
    config["recovery"]["grid_import_ceiling_mw"] = 17
    verification = verify_result(config, result)
    assert "event_recovery_boundary" in verification["failed_checks"]
    assert "recovery_0_shared_import" in verification["failed_checks"]


def test_earlier_workload_deadline_is_independently_checked(nominal_evidence):
    config, result = deepcopy(nominal_evidence)
    config["workloads"]["max_deferral_minutes"] = 60
    assert "earlier_workload_deadline" in verify_result(config, result)["failed_checks"]


def test_hash_comparison_detects_changed_record(nominal_evidence):
    config, original = nominal_evidence
    ih, eh = canonical_hash(config), evidence_hash(config, original)
    assert verify_result(config, original, expected_input_hash=ih, expected_evidence_hash=eh)["status"] == "pass"
    changed = deepcopy(original)
    changed["run_id"] += "-changed"
    assert "evidence_hash" in verify_result(config, changed, expected_evidence_hash=eh)["failed_checks"]


def test_hash_canonicalization_survives_json_numeric_round_trip():
    assert canonical_hash({"integral_float": 20.0, "negative_zero": -0.0}) == canonical_hash({"integral_float": 20, "negative_zero": 0})


@pytest.mark.parametrize("damage", ["nan", "non_object_telemetry", "unsupported_schema"])
def test_malformed_evidence_does_not_crash(nominal_evidence, damage):
    config, result = deepcopy(nominal_evidence)
    if damage == "nan": result["telemetry"]["final_battery_soc"] = float("nan")
    elif damage == "non_object_telemetry": result["telemetry"] = []
    else: result["schema_version"] = "999"
    assert verify_result(config, result)["status"] in {"fail", "insufficient_evidence"}


@pytest.mark.parametrize("controller", ["deterministic_mpc", "rule_based", "rafc_v", "risk_aware_mpc"])
def test_supported_controller_telemetry_can_be_replayed(nominal_evidence, controller):
    config, _ = nominal_evidence
    result = run_scenario(config, controller=controller, calibration_scenarios=1000, commitment_step_mw=1, calibration_seed=900)
    verification = verify_result(config, result)
    assert verification["status"] == "pass", (verification["failed_checks"], verification["insufficient_checks"])
