"""Evaluate FP-001 controllers on real CAISO 2024 stress events and Azure LLM load.

For each CAISO SP15 real-time price spike, build an FP-001 config with the
event's real duration and a recovery base taken from the Azure trace at that
time of day. Commitments are calibrated with baseline-drift samples from the
early trace days and tested on drift from the later, unseen days.

The "synthetic-only" column calibrates without drift samples (the original
modeled assumptions) and checks that commitment analytically against the
held-out real drift, showing what the purely modeled controller would promise.

Run: python -m evaluation.run_real_data --test-scenarios 200
"""
from __future__ import annotations

import os

# One BLAS thread per worker process; the default per-process thread pools
# exhaust memory when several workers start at once.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from evaluation.closed_loop import run_closed_loop_rafc_evaluation
from optimization.commitment import calibrate_commitment, evaluate_commitment
from realdata.azure_trace import build_profile
from realdata.grid_events import extract_events, load_prices, load_system_demand
from realdata.scenarios import PowerMapping, build_event_case, localize, split_days
from simulator.uncertainty import load_uncertainty_assumptions

ROOT = Path(__file__).resolve().parents[1]


def _evaluate_event(job: dict) -> dict:
    event, case, args = job["event"], job["case"], job["args"]
    config = case["config"]
    result = run_closed_loop_rafc_evaluation(
        config, calibration_scenarios=args["calibration_scenarios"],
        calibration_seed=args["calibration_seed"], test_scenarios=args["test_scenarios"],
        test_seed=args["test_seed"], commitment_step_mw=args["step"],
        assumptions=case["calibration_assumptions"], test_assumptions=case["test_assumptions"],
        dispatch_policy="v2",
    )
    by_controller = {row["controller"]: row for row in result["results"]}
    # The original modeled controller: calibrated without real drift samples.
    synthetic = calibrate_commitment(
        config, n_scenarios=args["calibration_scenarios"], seed=args["calibration_seed"],
        step_mw=args["step"], recovery_aware=True, assumptions=job["synthetic_assumptions"],
        meter_margin_mw=0.0, observed_noise=True,
    )["accepted_commitment_mw"]
    synthetic_check = evaluate_commitment(
        config, synthetic, n_scenarios=args["test_scenarios"], seed=args["test_seed"],
        assumptions=case["test_assumptions"], recovery_aware=True,
        meter_margin_mw=0.0, observed_noise=True,
    ) if synthetic > 0 else None
    hours = event["duration_minutes"] / 60.0
    cal_drift = np.asarray(case["calibration_assumptions"].baseline_drift_samples_mw)
    test_drift = np.asarray(case["test_assumptions"].baseline_drift_samples_mw)
    row = {
        **event,
        "recovery_base_mw": config["recovery"]["nominal_base_demand_mw"],
        "calibration_drift_p50_mw": float(np.quantile(cal_drift, 0.5)),
        "calibration_drift_p95_mw": float(np.quantile(cal_drift, 0.95)),
        "test_drift_p50_mw": float(np.quantile(test_drift, 0.5)),
        "test_drift_p95_mw": float(np.quantile(test_drift, 0.95)),
        "synthetic_only_commitment_mw": synthetic,
        "synthetic_only_heldout_success": synthetic_check["estimate"] if synthetic_check else None,
    }
    for name, label in (("rolling_rafc_v", "rafc_v"), ("rolling_risk_aware_mpc", "mpc"), ("fixed_horizon", "fixed")):
        summary = by_controller[name]
        row[f"{label}_commitment_mw"] = summary["commitment_mw"]
        row[f"{label}_success"] = summary["event_and_recovery_success_probability"]
        row[f"{label}_mean_delivered_mw"] = summary["mean_delivered_mw"]
    # Indicative energy value: committed MW x hours x mean real-time price.
    row["rafc_v_indicative_value_usd"] = row["rafc_v_commitment_mw"] * hours * event["mean_price_usd_mwh"]
    row["rafc_v_vs_mpc_mcnemar_p"] = result["paired_tests"]["rolling_risk_aware_mpc_vs_rolling_rafc_v"]["event_recovery_mcnemar"]["p_value"]
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "fp001.yaml")
    parser.add_argument("--uncertainty", type=Path, default=ROOT / "configs" / "uncertainty.yaml")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--price-threshold", type=float, default=200.0)
    parser.add_argument("--idle-fraction", type=float, default=0.4)
    parser.add_argument("--calibration-scenarios", type=int, default=1000)
    parser.add_argument("--calibration-seed", type=int, default=100_000)
    parser.add_argument("--test-scenarios", type=int, default=200)
    parser.add_argument("--test-seed", type=int, default=400_000)
    parser.add_argument("--step", type=float, default=0.1)
    parser.add_argument("--workers", type=int, default=min(6, max(1, (os.cpu_count() or 2) - 1)))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "real-data-caiso2024")
    args = parser.parse_args()

    with args.config.open("r", encoding="utf-8") as stream:
        base_config = yaml.safe_load(stream)
    synthetic_assumptions = load_uncertainty_assumptions(args.uncertainty)
    utilization = localize(build_profile())
    calibration_days, test_days = split_days(utilization)
    mapping = PowerMapping(idle_fraction=args.idle_fraction)
    events = extract_events(load_prices(args.year), threshold_usd_mwh=args.price_threshold,
                            demand=load_system_demand(args.year))
    jobs, skipped = [], []
    shared = {"calibration_scenarios": args.calibration_scenarios, "calibration_seed": args.calibration_seed,
              "test_scenarios": args.test_scenarios, "test_seed": args.test_seed, "step": args.step}
    for event in events:
        try:
            case = build_event_case(base_config, synthetic_assumptions,
                event_start_local=pd.Timestamp(event.start_local), duration_minutes=event.duration_minutes,
                utilization=utilization, calibration_days=calibration_days, test_days=test_days, mapping=mapping)
        except ValueError as error:
            skipped.append({"event_id": event.event_id, "reason": str(error)})
            continue
        jobs.append({"event": event.to_dict(), "case": case, "args": shared,
                     "synthetic_assumptions": synthetic_assumptions})
    print(f"{len(events)} events, {len(jobs)} evaluated, {len(skipped)} skipped; "
          f"calibration days {calibration_days[0]}..{calibration_days[-1]}, test days {test_days[0]}..{test_days[-1]}")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = []
        for row in pool.map(_evaluate_event, jobs):
            rows.append(row)
            print(row["event_id"], row["duration_minutes"], "min | RAFC-V", row["rafc_v_commitment_mw"], "MW",
                  f"{row['rafc_v_success']:.3f}", "| MPC", row["mpc_commitment_mw"], f"{row['mpc_success']:.3f}",
                  "| synthetic-only", row["synthetic_only_commitment_mw"], row["synthetic_only_heldout_success"], flush=True)

    frame = pd.DataFrame(rows)
    weights = frame["duration_minutes"]
    summary = {
        "schema_version": "1.0.0",
        "experiment_id": f"real-data-caiso{args.year}-azure-llm-2024",
        "data_sources": {
            "grid_events": f"CAISO OASIS real-time 15-min LMP, SP15 hub, {args.year}; events = runs >= ${args.price_threshold:g}/MWh",
            "ai_load": "Azure LLM inference trace 2024 (code + conversation), CC-BY 4.0, Stojkovic et al. HPCA 2025",
        },
        "calibration_days": [str(day) for day in calibration_days],
        "test_days": [str(day) for day in test_days],
        "power_mapping": {"rated_critical_mw": mapping.rated_critical_mw, "idle_fraction": mapping.idle_fraction,
                          "scheduled_non_deferred_mw": mapping.scheduled_non_deferred_mw,
                          "baseline_window_minutes": mapping.baseline_window_minutes},
        "events_found": len(events),
        "events_evaluated": len(rows),
        "events_skipped": skipped,
        "calibration_scenarios_per_event": args.calibration_scenarios,
        "test_scenarios_per_event": args.test_scenarios,
        "dispatch_policy": "v2",
        "mean_commitment_mw": {label: float(frame[f"{label}_commitment_mw"].mean()) for label in ("rafc_v", "mpc", "synthetic_only")},
        "mean_heldout_success": {label: float(frame[f"{label}_success"].mean()) for label in ("rafc_v", "mpc", "fixed")},
        "duration_weighted_heldout_success": {label: float(np.average(frame[f"{label}_success"], weights=weights)) for label in ("rafc_v", "mpc", "fixed")},
        "synthetic_only_mean_heldout_success": float(frame["synthetic_only_heldout_success"].dropna().mean()),
        "events_rafc_v_differs_from_mpc": int((frame["rafc_v_commitment_mw"] != frame["mpc_commitment_mw"]).sum()),
        "total_committed_mwh_rafc_v": float((frame["rafc_v_commitment_mw"] * frame["duration_minutes"] / 60).sum()),
        "total_indicative_value_usd_rafc_v": float(frame["rafc_v_indicative_value_usd"].sum()),
        "limitations": [
            "Price spikes are a proxy for grid stress, not actual demand-response dispatch instructions.",
            "The Azure trace covers about one week in May 2024; it is reused for events across 2024 by time of day.",
            "Token throughput is a proxy for GPU power; the utilization-to-MW mapping is an assumption.",
            "Battery, flexible-compute and other disturbances keep the modeled FP-001 assumptions.",
            "Indicative value is committed MWh times the mean real-time price, not a program payment.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output_dir / "real_data_events.csv", index=False)
    (args.output_dir / "real_data_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in summary if key not in ("limitations", "events_skipped")}, indent=2))


if __name__ == "__main__":
    main()
