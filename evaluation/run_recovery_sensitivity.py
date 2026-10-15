"""Run a deterministic grid of RecoveryGuard sensitivity cases."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from evaluation.recovery_sensitivity import run_recovery_sensitivity


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "fp001.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "recovery-sensitivity")
    args = parser.parse_args()
    with args.config.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    result = run_recovery_sensitivity(config, output_dir=args.output_dir)
    feasible = sum(row["recovery_feasible"] for row in result["cases"])
    print(f"RecoveryGuard feasible in {feasible}/{result['case_count']} sensitivity cases")
    print(f"Saved outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
