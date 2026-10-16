"""Load only the preserved experimental summary and check its raw artifact hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SUMMARY_PATH = ROOT / "results" / "benchmark_summary.json"


def load_closed_loop_benchmark(summary_path: str | Path = SUMMARY_PATH) -> dict[str, Any]:
    path = Path(summary_path)
    if not path.is_file():
        return {"status": "unavailable", "reason": "No verified benchmark summary is installed."}
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("schema_version") != "1.0.0" or len(summary.get("results", [])) != 3:
            raise ValueError("Unsupported or incomplete benchmark summary")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {"status": "invalid_artifact", "reason": str(exc)}

    provenance = summary.get("provenance", {})
    raw_dir = path.parent / "closed-loop-fp001-reproduced"
    raw_files = {
        "json": (raw_dir / "closed_loop_comparison.json", provenance.get("raw_json_sha256")),
        "csv": (raw_dir / "closed_loop_scenarios.csv", provenance.get("raw_csv_sha256")),
    }
    found = 0
    mismatched = []
    for label, (raw_path, expected_hash) in raw_files.items():
        if not raw_path.is_file():
            continue
        found += 1
        actual_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if not expected_hash or actual_hash != expected_hash:
            mismatched.append(label)
    if mismatched:
        status = "integrity_mismatch"
        reason = f"Raw held-out artifact checksum mismatch: {', '.join(mismatched)}."
    elif found == len(raw_files):
        status = "raw_files_verified"
        reason = "Both locally available raw held-out files match the recorded SHA-256 checksums."
    else:
        status = "summary_only_raw_files_unavailable"
        reason = "Summary is available, but one or more full raw held-out artifacts are not present locally."
    return {"status": status, "reason": reason, "summary": summary}
