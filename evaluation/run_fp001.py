"""Run the four-controller FP-001 benchmark from a source checkout."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from evaluation.compare import compare_controllers
from evaluation.plots import plot_controller_comparison


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=ROOT/"configs"/"fp001.yaml")
    parser.add_argument("--calibration-scenarios",type=int,default=1000)
    parser.add_argument("--calibration-seed",type=int,default=100_000)
    parser.add_argument("--test-scenarios",type=int,default=5000)
    parser.add_argument("--test-seed",type=int,default=200_000)
    parser.add_argument("--commitment-step-mw",type=float,default=0.1)
    parser.add_argument("--output-dir",type=Path,default=ROOT/"results"/"fp001")
    args=parser.parse_args()
    with args.config.open("r",encoding="utf-8") as stream:
        config=yaml.safe_load(stream)
    result=compare_controllers(config,calibration_scenarios=args.calibration_scenarios,
        calibration_seed=args.calibration_seed,test_scenarios=args.test_scenarios,
        test_seed=args.test_seed,commitment_step_mw=args.commitment_step_mw,
        output_dir=args.output_dir)
    plot_controller_comparison(result,args.output_dir/"controller_comparison.png")
    print(f"Saved {len(result['results'])} controller results to {args.output_dir}")
    for row in result["results"]:
        print(row["controller"],"commitment MW:",row["accepted_commitment_mw"],
              "held-out event success:",row["complete_event_success_probability"],
              "event + recovery:",row["event_and_recovery_success_probability"])


if __name__=="__main__":
    main()
