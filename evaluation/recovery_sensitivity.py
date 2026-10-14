"""Deterministic RecoveryGuard sensitivity over backlog, SoC, and headroom."""
from __future__ import annotations

import csv
import json
from itertools import product
from pathlib import Path
from typing import Any, Iterable

from optimization.recovery import plan_recovery


def run_recovery_sensitivity(
    config: dict[str, Any], *, backlog_mwh_values: Iterable[float] = (0.0, 2.0, 4.0),
    current_soc_values: Iterable[float] = (0.22, 0.25, 0.30, 0.35),
    grid_ceiling_mw_values: Iterable[float] = (18.0, 19.0, 20.0, 21.0),
    output_dir: str | Path | None = None,
) -> dict:
    """Sweep deterministic recovery states; no held-out event outcomes used."""
    backlog_values = tuple(float(x) for x in backlog_mwh_values)
    soc_values = tuple(float(x) for x in current_soc_values)
    ceiling_values = tuple(float(x) for x in grid_ceiling_mw_values)
    if not backlog_values or not soc_values or not ceiling_values:
        raise ValueError("each sensitivity axis must contain at least one value")
    cases = []
    for backlog, soc, ceiling in product(backlog_values, soc_values, ceiling_values):
        case_config = {**config, "recovery": {**config["recovery"], "grid_import_ceiling_mw": ceiling}}
        recovery = plan_recovery(case_config, backlog_mwh=backlog, current_soc=soc)
        telemetry = recovery.get("telemetry", {})
        cases.append({
            "backlog_mwh": backlog,
            "current_soc": soc,
            "grid_import_ceiling_mw": ceiling,
            "status": recovery.get("status"),
            "recovery_feasible": recovery.get("status") == "completed",
            "deadline_cleared": telemetry.get("backlog_cleared"),
            "soc_target_met": telemetry.get("soc_target_met"),
            "rebound_peak_mw": telemetry.get("max_grid_import_mw"),
            "final_soc": telemetry.get("final_battery_soc"),
            "final_backlog_mwh": telemetry.get("final_workload_backlog_mwh"),
            "solver_runtime_seconds": (recovery.get("solver_metadata") or {}).get("runtime_seconds"),
            "failure_reason": recovery.get("infeasibility_reason"),
        })
    output = {
        "schema_version": "1.0.0",
        "artifact_type": "experiment_result",
        "experiment_id": f"{config['scenario_id']}-recovery-sensitivity",
        "scenario_id": config["scenario_id"],
        "sensitivity_axes": {
            "backlog_mwh": list(backlog_values),
            "post_event_soc": list(soc_values),
            "grid_import_ceiling_mw": list(ceiling_values),
        },
        "case_count": len(cases),
        "recovery_base_demand_mw": config["recovery"]["nominal_base_demand_mw"],
        "target_minute": config["recovery"].get("target_minute"),
        "clear_deferred_work_by_minute": config["recovery"].get("clear_deferred_work_by_minute"),
        "cases": cases,
        "limitations": [
            "Deterministic sensitivity cases; they are not empirical probability estimates.",
            "The nominal recovery base demand and workload-release assumptions remain those in the scenario configuration.",
        ],
    }
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "recovery_sensitivity.json").write_text(
            json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        with (directory / "recovery_sensitivity.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(cases[0]))
            writer.writeheader()
            writer.writerows(cases)
    return output
