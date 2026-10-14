# RAFC-V algorithm design

## Current implementation (0.1.0)

`optimization.rafc_v.run_rafc_v` combines three stages:

1. Generate seeded modeled disturbances and evaluate candidate commitments over a calibration scenario set.
2. Select the largest candidate whose Bonferroni-adjusted one-sided Wilson lower bound meets the configured complete-event target. With `recovery_aware=True`, a scenario passes only when the event is feasible and the recovery workload and charging tasks pass cumulative shared-headroom and per-resource rate checks by their configured deadlines.
3. For candidates in descending order, solve the nominal event schedule with Pyomo/HiGHS and then solve a joint workload/battery recovery schedule with RecoveryGuard. If the nominal plan fails either solve, reject it and try the next calibrated candidate.

If no candidate has sufficient statistical evidence, the returned accepted commitment is zero and reliability status is `unconfirmed`; the controller does not promote nominal feasibility to a reliability claim. If calibrated candidates exist but all nominal plans fail, status is `infeasible`.

## Recovery feasibility screen

For the present RecoveryGuard linear program, both recovery tasks are available from the recovery horizon start. Let `W` be deferred workload energy, `C` required AC-side battery charging energy, `h` interval duration in hours, `d_w` the workload-clear interval, `d_c` the battery-SoC target interval, `P_w` the workload power limit, `P_c` the charge power limit, and `H` the shared import headroom. Feasibility is equivalent to:

- `W <= min(P_w, H) * d_w * h`
- `C <= min(P_c, H) * d_c * h`
- `W + C <= H * max(d_w, d_c) * h`

These checks capture task rate limits, individual deadline capacity, and the shared grid budget for this LP. The chosen nominal schedule is still solved by RecoveryGuard; sampled recovery outcomes are screened analytically to avoid solving thousands of identical-structure LPs.

## Evidence and limitations

The returned estimate and confidence bound describe calibration scenarios only. They do not represent held-out validation or field certification. Disturbance probabilities and distributions are initial modeled assumptions. The deterministic MPC supplies a fixed event schedule; rolling event re-optimization, held-out experiment management, and comparative controller studies remain future work. The confidence-bound search uses a Bonferroni adjustment across candidate commitments.
