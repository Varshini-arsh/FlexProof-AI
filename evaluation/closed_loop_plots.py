"""Plots for the paired held-out closed-loop benchmark summary."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_closed_loop_comparison(summary: dict[str, Any], output_path: str | Path) -> Path:
    rows = summary.get("results", [])
    if len(rows) != 3 or summary.get("protocol", {}).get("heldout_sample_count", 0) <= 0:
        raise ValueError("expected three controller results and a nonempty held-out sample")
    labels = [row["controller"].replace("_", "\n") for row in rows]
    colors = ["#9b7048", "#347c8a", "#366e59"]
    n = summary["protocol"]["heldout_sample_count"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for axis, metric, interval, title, target in (
        (axes[0, 0], "event_success_probability", "event_wilson_interval", "Complete-event success", 0.95),
        (axes[0, 1], "event_and_recovery_success_probability", "joint_wilson_interval", "Event and recovery success", None),
    ):
        values = [row[metric] for row in rows]
        bounds = [row[interval] for row in rows]
        errors = [[max(0.0, value - ci[0]) for value, ci in zip(values, bounds)],
                  [max(0.0, ci[1] - value) for value, ci in zip(values, bounds)]]
        axis.bar(labels, values, color=colors, yerr=errors, capsize=4)
        if target is not None:
            axis.axhline(target, color="#b45309", linestyle="--", label="95% target")
            axis.legend(frameon=False)
        axis.set_ylim(0, 1.02); axis.set_ylabel("Probability"); axis.set_title(f"{title} (Wilson 95%, n={n})")
        axis.grid(axis="y", alpha=0.25)
    axes[1, 0].bar(labels, [row["mean_delivered_mw"] for row in rows], color=colors)
    axes[1, 0].set_ylabel("MW"); axes[1, 0].set_title("Mean delivered reduction"); axes[1, 0].grid(axis="y", alpha=0.25)
    axes[1, 1].bar(labels, [row["mean_max_shortfall_mw"] for row in rows], color=colors)
    axes[1, 1].set_ylabel("MW"); axes[1, 1].set_title("Mean scenario maximum shortfall"); axes[1, 1].grid(axis="y", alpha=0.25)
    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180); plt.close(fig)
    return path
