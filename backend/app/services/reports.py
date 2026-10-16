"""Traceable JSON, CSV, and PDF evidence exports for recorded runs."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
from textwrap import wrap
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from backend.app.services.verification import canonical_hash, evidence_hash, verify_result


def build_evidence_bundle(config: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    verification = verify_result(config, result)
    return {
        "schema_version": "1.0.0",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario_id": result.get("scenario_id", config.get("scenario_id")),
        "run_id": result.get("run_id"),
        "controller": result.get("controller"),
        "controller_version": result.get("controller_version"),
        "input_hash_sha256": canonical_hash(config),
        "evidence_hash_sha256": evidence_hash(config, result),
        "certification": False,
        "scenario": config,
        "result": result,
        "independent_verification": verification,
        "limitations": verification["limitations"],
    }


def telemetry_csv(config: dict[str, Any], result: dict[str, Any]) -> str:
    fields = ("phase", "step", "start_minute", "end_minute", "baseline_grid_import_mw", "grid_import_mw",
              "delivered_reduction_mw", "battery_charge_mw", "battery_discharge_mw", "battery_soc_start",
              "battery_soc_end", "flexible_compute_mw", "work_deferred_mwh", "work_served_mwh",
              "workload_backlog_start_mwh", "workload_backlog_mwh", "grid_import_ceiling_mw")
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in result.get("telemetry", {}).get("event_time_series", []):
        writer.writerow({"phase": "event", **row,
                         "delivered_reduction_mw": float(row["baseline_grid_import_mw"]) - float(row["grid_import_mw"])})
    recovery = result.get("recovery", {})
    ceiling = config.get("recovery", {}).get("grid_import_ceiling_mw")
    for row in recovery.get("telemetry", {}).get("recovery_time_series", []):
        writer.writerow({"phase": "recovery", "grid_import_ceiling_mw": ceiling, **row})
    return stream.getvalue()


def verification_pdf(bundle: dict[str, Any]) -> bytes:
    config, result = bundle["scenario"], bundle["result"]
    verification = bundle["independent_verification"]
    output = BytesIO()
    with PdfPages(output) as pdf:
        lines = [
            "FlexProof AI — Operational Evidence Report",
            f"Scenario: {bundle['scenario_id']}    Run: {bundle['run_id']}",
            f"Controller: {bundle['controller']} / {bundle['controller_version']}",
            f"Exported UTC: {bundle['exported_at_utc']}",
            f"Independent verification: {verification['status']} ({verification['failed_check_count']} failed, {verification['insufficient_check_count']} incomplete)",
            f"Accepted commitment: {result.get('accepted_commitment_mw')} MW; event execution: {result.get('execution_status')}",
            f"Reliability certification: No. This report records one simulation and operational arithmetic checks.",
            f"Input SHA-256: {bundle['input_hash_sha256']}",
            f"Evidence SHA-256: {bundle['evidence_hash_sha256']}",
            "",
            "Model assumptions",
            f"Event request: {config.get('grid_event', {}).get('requested_reduction_mw')} MW for {config.get('grid_event', {}).get('duration_minutes')} minutes.",
            f"Recovery baseline: {config.get('recovery', {}).get('nominal_base_demand_mw')} MW; import ceiling: {config.get('recovery', {}).get('grid_import_ceiling_mw')} MW.",
            "Recovery base is a planning assumption. Workload recovery and battery charging share the same grid capacity.",
            "Verification checks",
        ]
        for check in verification["checks"]:
            lines.append(f"[{check['status'].upper()}] {check['name']}: {check['detail']}")
        lines.extend(["", "Limitations"] + [f"• {item}" for item in verification["limitations"]])
        wrapped_lines = [part for line in lines for part in (wrap(line, width=112, subsequent_indent="  ") or [""])]
        for page_index in range(0, len(wrapped_lines), 55):
            fig = plt.figure(figsize=(8.27, 11.69))
            page = wrapped_lines[page_index:page_index + 55]
            fig.text(0.065, 0.97, "\n".join(page), va="top", fontsize=7.4, family="monospace")
            pdf.savefig(fig)
            plt.close(fig)

        event = result.get("telemetry", {}).get("event_time_series", [])
        recovery = result.get("recovery", {}).get("telemetry", {}).get("recovery_time_series", [])
        fig, axes = plt.subplots(3, 1, figsize=(10, 8), constrained_layout=True)
        if event:
            x = [row["end_minute"] for row in event]
            axes[0].plot(x, [row["baseline_grid_import_mw"] for row in event], label="Baseline")
            axes[0].plot(x, [row["grid_import_mw"] for row in event], label="Grid import")
            axes[1].plot(x, [row["battery_soc_end"] * 100 for row in event], label="Event SoC")
            axes[0].set_title("Event grid import (MW)")
            axes[1].set_title("Battery state of charge (%)")
        if recovery:
            x = [row["end_minute"] for row in recovery]
            axes[0].plot(x, [row["grid_import_mw"] for row in recovery], label="Recovery import")
            axes[1].plot(x, [row["battery_soc_end"] * 100 for row in recovery], label="Recovery SoC")
            axes[2].plot(x, [row["workload_backlog_end_mwh"] for row in recovery], label="Remaining workload")
            axes[2].set_title("Recovery backlog (MWh)")
        for axis in axes:
            axis.set_xlabel("Minute")
            axis.grid(alpha=0.25)
            if axis.lines:
                axis.legend()
        pdf.savefig(fig)
        plt.close(fig)
    return output.getvalue()
