"""Run paired held-out closed-loop evaluation of RAFC-V event dispatch."""
from __future__ import annotations

import argparse
from pathlib import Path
import yaml

from evaluation.closed_loop import run_closed_loop_rafc_evaluation


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "fp001.yaml")
    parser.add_argument("--calibration-scenarios", type=int, default=1000)
    parser.add_argument("--calibration-seed", type=int, default=100_000)
    parser.add_argument("--test-scenarios", type=int, default=100)
    parser.add_argument("--test-seed", type=int, default=400_000)
    parser.add_argument("--commitment-step-mw", type=float, default=0.1)
    parser.add_argument("--dispatch-policy", choices=("v1", "v2"), default="v1",
                        help="v2 = persistence forecast with soft meter margin (applies to both rolling arms)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "closed-loop-fp001")
    args = parser.parse_args()
    with args.config.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    result = run_closed_loop_rafc_evaluation(
        config, calibration_scenarios=args.calibration_scenarios,
        calibration_seed=args.calibration_seed, test_scenarios=args.test_scenarios,
        test_seed=args.test_seed, commitment_step_mw=args.commitment_step_mw,
        output_dir=args.output_dir, dispatch_policy=args.dispatch_policy,
    )
    calibration = result["commitment_calibration"]
    print("Commitment MW: RAFC-V", calibration["rolling_rafc_v"]["accepted_commitment_mw"],
          "risk-aware MPC", calibration["rolling_risk_aware_mpc"]["accepted_commitment_mw"])
    print(f"Saved {result['heldout_sample_count']} paired scenarios to {args.output_dir}")
    for row in result["results"]:
        print(row["controller"], "event:", row["event_success_probability"],
              "event + recovery:", row["event_and_recovery_success_probability"])


if __name__ == "__main__":
    main()
