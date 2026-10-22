# RAFC-V algorithm design

## Current implementation (0.1.0)

`optimization.rafc_v.run_rafc_v` combines three stages:

1. Generate seeded modeled disturbances and evaluate candidate commitments over a calibration scenario set.
2. Select the largest candidate whose Bonferroni-adjusted one-sided Wilson lower bound meets the configured complete-event target. With `recovery_aware=True`, a scenario passes only when the event is feasible and the recovery workload and charging tasks pass cumulative shared-headroom and per-resource rate checks by their configured deadlines.
3. For candidates in descending order, solve the event using a receding horizon: optimize over all remaining event intervals, apply the first interval only, update SoC/backlog and observations, then solve again. Each solve includes terminal constraints for a feasible shared-capacity recovery. After the event, independently solve the full workload/battery schedule with RecoveryGuard. If event or recovery planning fails, reject that candidate and try the next calibrated candidate.

If no candidate has sufficient statistical evidence, the returned accepted commitment is zero and reliability status is `unconfirmed`; the controller does not promote nominal feasibility to a reliability claim. If calibrated candidates exist but all nominal plans fail, status is `infeasible`.

## Recovery feasibility screen

For the present RecoveryGuard linear program, both recovery tasks are available from the recovery horizon start. Let `W` be deferred workload energy, `C` required AC-side battery charging energy, `h` interval duration in hours, `d_w` the workload-clear interval, `d_c` the battery-SoC target interval, `P_w` the workload power limit, `P_c` the charge power limit, and `H` the shared import headroom. Feasibility is equivalent to:

- `W <= min(P_w, H) * d_w * h`
- `C <= min(P_c, H) * d_c * h`
- `W + C <= H * max(d_w, d_c) * h`

These checks capture task rate limits, individual deadline capacity, and the shared grid budget for this LP. The chosen nominal schedule is still solved by RecoveryGuard; sampled recovery outcomes are screened analytically to avoid solving thousands of identical-structure LPs.

## Dispatch v2 (opt-in, `dispatch_policy="v2"`)

Diagnosis of the 112 failures in the 5,000-scenario run (v1, 4.9 MW): every failure was one 5-minute interval of shortfall. v1 delivers the commitment plus a 0.0466 MW meter margin in every interval, so it spends battery energy on the margin early. When urgent reclaim (0.4 MW) coincides with a negative initial SoC error, the battery reaches its protected reserve one interval too early and the last interval misses the commitment. About 70 of the 112 failures were physically deliverable.

v2 changes the rolling dispatcher in two ways and recalibrates the commitment to match:

1. **Soft margin.** The commitment (plus the observed meter noise) is the priority target. The meter margin is a lower-priority goal, so it can never cost energy that the commitment needs later in the event.
2. **Persistence forecast.** Future intervals are planned with the compute and battery limits observed in the current interval, instead of nominal limits. This matches the stated model assumption that a disturbance is constant within one event. It never reads future observations; a regression test checks this.
3. **Matching calibration.** The commitment screen plans for the observed meter noise instead of a fixed 99% margin (`meter_margin_mw=0.0, observed_noise=True`).

The defaults are unchanged (`dispatch_policy="v1"`, `forecast="nominal"`, `soft_margin=False`), so earlier results remain reproducible. In the closed-loop evaluator, `--dispatch-policy v2` applies to both rolling arms, so any RAFC-V versus risk-aware MPC difference still comes only from the commitment screen.

## Evidence and limitations

The returned estimate and confidence bound describe calibration scenarios only. They do not represent held-out validation or field certification. Disturbance probabilities and distributions are initial modeled assumptions. The rolling dispatcher can consume current per-interval flexible-capacity, battery-derating, initial-SoC, critical-demand, and meter observations; future intervals use nominal forecasts and are re-planned as observations arrive. The current held-out benchmark scores scenario passes rather than executing the controller in closed loop, so its rolling-reoptimization ablation compares nominal schedules only. The confidence-bound search uses a Bonferroni adjustment across candidate commitments.
