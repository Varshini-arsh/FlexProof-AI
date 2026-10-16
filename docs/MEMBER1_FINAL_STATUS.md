# Member 1 research engine status at integration checkpoint

Member 2 integrated the Member 1 public Python engine from source revision `b5712c2d5af49d70627225ae9f1a5127fb84976a` into the isolated `feature/fullstack-verification` worktree. The simulator, optimization, baseline, evaluation, configuration, and contract files were checked against that snapshot and retained byte-for-byte. Member 1's branch was not modified.

The API imports `flexproof.engine` and executes nominal, rule-based, deterministic MPC, risk-aware MPC, and RAFC-V controllers. The paired closed-loop runner writes per-scenario CSV and aggregate JSON, reports Wilson intervals and paired McNemar/bootstrap tests, and supplies a checksummed summary to the benchmark dashboard.

The 5,000-scenario outcomes and limitations are recorded in [RESULTS_AND_LIMITATIONS.md](RESULTS_AND_LIMITATIONS.md). They support the tested 4.9 MW commitment under modeled assumptions and these fixed seeds, but are not field validation. Rolling RAFC-V and rolling risk-aware MPC had identical held-out outcomes; no incremental RAFC-V performance advantage was demonstrated.

Remaining research work includes recovery sensitivity and ablations for reliability calibration, recovery-aware planning, and rolling re-optimization; additional seeds; independently sourced uncertainty data; and alternate facility scales and workload deadlines. Those are not part of the reproduced run.
