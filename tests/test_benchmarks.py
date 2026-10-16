import hashlib
import json

from backend.app.services.benchmarks import load_closed_loop_benchmark


def _artifact(tmp_path):
    raw = tmp_path / "closed-loop-fp001-reproduced"
    raw.mkdir()
    paths = {"json": raw / "closed_loop_comparison.json", "csv": raw / "closed_loop_scenarios.csv"}
    paths["json"].write_text("raw json", encoding="utf-8")
    paths["csv"].write_text("raw csv", encoding="utf-8")
    provenance = {"raw_json_sha256": hashlib.sha256(paths["json"].read_bytes()).hexdigest(),
                  "raw_csv_sha256": hashlib.sha256(paths["csv"].read_bytes()).hexdigest()}
    summary = tmp_path / "benchmark_summary.json"
    summary.write_text(json.dumps({"schema_version": "1.0.0", "results": [{}, {}, {}], "provenance": provenance}), encoding="utf-8")
    return summary, paths


def test_benchmark_reports_valid_local_raw_artifact_hashes(tmp_path):
    summary, _ = _artifact(tmp_path)
    assert load_closed_loop_benchmark(summary)["status"] == "raw_files_verified"


def test_benchmark_detects_raw_artifact_tampering(tmp_path):
    summary, raw_paths = _artifact(tmp_path)
    raw_paths["csv"].write_text("modified", encoding="utf-8")
    assert load_closed_loop_benchmark(summary)["status"] == "integrity_mismatch"


def test_benchmark_summary_is_available_when_raw_files_are_not(tmp_path):
    summary, raw_paths = _artifact(tmp_path)
    raw_paths["csv"].unlink()
    assert load_closed_loop_benchmark(summary)["status"] == "summary_only_raw_files_unavailable"


def test_missing_benchmark_is_reported_as_unavailable(tmp_path):
    assert load_closed_loop_benchmark(tmp_path / "missing.json")["status"] == "unavailable"
