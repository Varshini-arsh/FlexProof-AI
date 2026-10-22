"""Publication-ready plots for controller comparison outputs."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


def plot_controller_comparison(result: dict[str, Any], output_path: str | Path) -> Path:
    rows=[row for row in result["results"] if row.get("complete_event_success_probability") is not None]
    if not rows:
        raise ValueError("comparison has no valid controller results to plot")
    names=[row["controller"].replace("_","\n") for row in rows]
    commitments=[row["accepted_commitment_mw"] for row in rows]
    success=[row["event_and_recovery_success_probability"] for row in rows]
    intervals=[row["joint_wilson_interval"] for row in rows]
    errors=[[max(0.0,value-ci[0]) for value,ci in zip(success,intervals)],
            [max(0.0,ci[1]-value) for value,ci in zip(success,intervals)]]
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),constrained_layout=True)
    axes[0].bar(names,commitments,color="#3978a8")
    axes[0].set_ylabel("Accepted commitment (MW)")
    axes[0].set_title("Calibrated commitment")
    axes[0].grid(axis="y",alpha=0.25)
    axes[1].bar(names,success,color="#468c69",yerr=errors,capsize=4)
    axes[1].axhline(0.95,color="#a84442",linestyle="--",linewidth=1,label="95% target")
    axes[1].set_ylim(0,1.02)
    axes[1].set_ylabel("Held-out event + recovery success")
    axes[1].set_title(f"Wilson intervals, n={result['heldout_sample_count']}")
    axes[1].legend(frameon=False)
    axes[1].grid(axis="y",alpha=0.25)
    path=Path(output_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=180)
    plt.close(fig)
    return path
