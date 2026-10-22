# FlexProof AI: Results and Limitations

## Evaluation status

The four-controller scenario-pass benchmark under `results/fp001-cal1000-test5000` is a prior analytical scenario evaluation. It is not a closed-loop execution of the controllers. A separate closed-loop evaluation has completed under the frozen FP-001 configuration; its exact command, seed ranges, sample sizes, and measured outputs are recorded below.

## Corrected closed-loop smoke run

Command:

```powershell
.\.venv\Scripts\python.exe -m evaluation.run_closed_loop --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 100 --test-seed 300000 --commitment-step-mw 0.5 --output-dir results/closed-loop-fp001-smoke
```

The calibration-selected commitment was 4.5 MW for both risk-aware MPC and RAFC-V. On 100 held-out paired seeds, fixed-horizon succeeded in 93/100 cases (Wilson 95% interval 86.25–96.57%); rolling risk-aware MPC and rolling RAFC-V each succeeded in 100/100 (96.30–100%). The paired fixed-versus-each-rolling McNemar p-value was 0.015625 and Holm-adjusted p-value 0.046875 across three controller-pair tests. Risk-aware MPC and RAFC-V had identical commitments and outcomes (p=1.0). All three controllers cleared recovery and workload deadlines in this smoke batch.

This smoke batch is exploratory. Its seven fixed-horizon shortfalls comprised six scenarios with 0.4 MW urgent workload reclaim and one tail meter-noise exceedance slightly beyond the 99th-percentile margin. There were no battery reserve violations or workload deadline misses. Rolling risk-aware MPC and RAFC-V had mean delivered reduction 4.5465 MW and no shortfall; the fixed schedule averaged 4.5211 MW and 0.0211 MWh shortfall per scenario. Mean RecoveryGuard rebound peak was 18.1442 MW for fixed and 18.1512 MW for both rolling arms. These sample statistics are not confirmatory. Do not use 100 scenarios to certify the 95% reliability target or claim controller superiority.

The earlier 42/100 fixed-horizon result is withdrawn. It was caused by an inconsistent comparator that omitted the 99th-percentile meter margin used by rolling dispatch. It is not valid evidence and its artifacts are ignored by Git.

Audit of the withdrawn 100-case output: 58 fixed-horizon failures, of which 55 had positive meter noise, 6 included urgent reclaim, and 6 included battery derating (these disturbance flags overlap); 3 failures had nonpositive meter noise. This confirmed the missing margin artificially disadvantaged that schedule. The corrected matched-margin result above is the valid smoke comparison.

## RecoveryGuard sensitivity

Command: `python -m evaluation.run_recovery_sensitivity --output-dir results/recovery-sensitivity-fp001`.

The deterministic 48-case grid crossed deferred backlog values 0, 2, and 4 MWh; post-event SoC values 22%, 25%, 30%, and 35%; and recovery grid ceilings 18, 19, 20, and 21 MW. Recovery was feasible in 45/48 cases. All three failures were the 4 MWh backlog with 18 MW ceiling and SoC below the 35% target: under 1 MW shared headroom, the 4 MWh workload consumes the entire 4-hour available recovery budget, leaving no capacity to recharge. Feasible-case rebound peaks ranged from 17.0 to 18.3421 MW. This is deterministic sensitivity evidence, not a probability estimate.

## 5,000-scenario closed-loop results

Command:

```powershell
.\.venv\Scripts\python.exe -m evaluation.run_closed_loop --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 5000 --test-seed 400000 --commitment-step-mw 0.1 --output-dir results/closed-loop-fp001-5000
```

The calibrated commitment was 4.9 MW for both rolling arms. Each used 1,000 calibration scenarios (seeds 100000–100999); the untouched held-out range was seeds 400000–404999 (5,000 unique paired scenarios). Both calibrations had 984/1,000 passes (98.4%) and simultaneous lower bound 96.634%, exceeding the modeled 95% target. Held-out estimates and Wilson 95% intervals:

| Controller | Event and recovery successes | Success estimate (95% Wilson interval) | Mean delivered MW | Scenarios with shortfall | Mean shortfall energy (MWh/scenario) | Reserve violation scenarios | Workload deadline misses | Recovery feasible | Mean recovery peak (MW) | Solver time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Fixed horizon | 4,448 / 5,000 | 88.96% (88.06–89.80%) | 4.9057 | 552 | 0.03622 | 0 | 0 | 5,000 / 5,000 | 18.2524 (max 18.3017) | One pre-test schedule solve: 0.0345 s |
| Rolling risk-aware MPC | 4,888 / 5,000 | 97.76% (97.31–98.13%) | 4.9456 | 112 | 0.000808 | 0 | 0 | 5,000 / 5,000 | 18.2634 (max 18.3181) | 0.2295 s/event scenario + 0.0470 s/recovery solve, mean |
| Rolling RAFC-V | 4,888 / 5,000 | 97.76% (97.31–98.13%) | 4.9456 | 112 | 0.000808 | 0 | 0 | 5,000 / 5,000 | 18.2634 (max 18.3181) | Same dispatch as risk-aware MPC |

All recoveries cleared the deferred backlog by minute 300 and met the 35% SoC target; no battery protected-reserve violations or solver failures occurred. For fixed horizon, 512 of 552 delivery-shortfall scenarios had the urgent 0.4 MW reclaim, 35 had battery derating, and 30 had both (factors overlap). Positive meter noise occurred in 284 failures. For rolling dispatch, all 112 shortfall scenarios had urgent reclaim and negative initial SoC estimation error; 7 also had battery derating. These are overlapping disturbance associations, not a causal decomposition. No failures were incorrectly attributed to reserve violations: the controllers short-delivered while maintaining the reserve.

Paired exact McNemar comparison: fixed-horizon versus each rolling arm had 440 rolling-only successes, zero fixed-only successes, and two-sided p=7.04e-133; Holm-adjusted p=2.11e-132 across the three pair comparisons. Their event and joint recovery outcomes matched. Rolling risk-aware MPC versus RAFC-V had zero discordant pairs (p=1.0), zero commitment difference, and identical delivery/recovery metrics. This run therefore finds no incremental RAFC-V benefit over the fair rolling risk-aware MPC comparator. It does find higher simulated success for rolling re-optimization than for the matched-margin fixed schedule under these assumptions; this remains simulation evidence, not field validation.

Paired-bootstrap 95% CI for fixed minus rolling risk-aware MPC: mean delivered MW [-0.04329, -0.03659]; mean shortfall energy [0.03250, 0.03835] MWh/scenario; recovery rebound peak [-0.01199, -0.01014] MW. Thus rolling had higher delivered power and slightly higher rebound peak. Solver runtime is not compared by paired CI: fixed-horizon's 0.0345 s is a one-time schedule solve reused for the test set, while rolling reports per-scenario event solve time. The evaluator's measured test-plus-summary runtime was 1,848.82 s (30m 48.82s); calibration took 0.40 s. The raw JSON and per-scenario CSV are not present in the current checkout; generated `results/` files are ignored by Git. Re-run the command above to regenerate them. The aggregate values in this document are the recorded experiment summary.

## Dispatch v2: diagnosis and held-out result

Diagnosis, fix, and design are in `algorithm_design.md` (Dispatch v2). All v2 runs use the same calibration seeds (100000-100999) and held-out seeds (400000-404999) as the v1 run above.

Command: `python -m evaluation.run_closed_loop --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 5000 --test-seed 400000 --commitment-step-mw 0.05 --dispatch-policy v2 --output-dir results/closed-loop-fp001-v2-5000-step005`.

With a 0.05 MW candidate step, v2 calibrates a **4.95 MW** commitment for both rolling arms. Held-out event and recovery success is 4,878 / 5,000 = **97.56%** (Wilson 95% interval 97.09-97.95%), with 122 scenarios with shortfall, no reserve violations, and mean delivered reduction 4.994 MW (v1 at 4.9 MW: 4.946 MW). Fixed horizon is unchanged at 88.96% (552 shortfall scenarios).

An analytic bound shows this is the physical ceiling: a scenario is deliverable at commitment c if (4.0 - urgent reclaim) + min(3 MW x discharge scale, usable battery energy over the hour) - meter noise >= c. At 4.95 MW this holds in 4,878 / 5,000 scenarios. **v2 succeeded in all 4,878 of them and in none of the other 122 (0 feasible-but-failed).** The same bound at 4.9 MW is 99.16%, so v1's 97.76% left about 70 deliverable scenarios unserved. Against v1 at 4.9 MW on the same scenarios, v1 succeeded alone in 10 scenarios (the extra 0.05 MW cannot always be met) and v2 never succeeded alone; both failed in the same 112 scenarios. This is a trade of a small success rate for 0.05 MW more delivered power, not a strict dominance claim.

Risk-aware MPC and RAFC-V again make identical commitments and outcomes on FP-001, because recovery is never binding there.

## Recovery stress: where recovery-aware commitment matters

FP-001 never stresses recovery, so RAFC-V cannot differ from risk-aware MPC. To test the recovery screen, the grid import ceiling during recovery was lowered from 20 MW to 18.2 MW and 18.0 MW (`configs/fp001_recovery_stress_18p2.yaml`, `..._18p0.yaml`; everything else unchanged). Same calibration seeds, 1,000 held-out events (seeds 400000-400999), v2 dispatch for both rolling arms, 0.1 MW step.

| Recovery ceiling | Controller | Commitment | Event and recovery success |
|---|---|---:|---:|
| 18.2 MW | Rolling risk-aware MPC | 4.9 MW | 0 / 1,000 (0.00%) |
| 18.2 MW | Rolling RAFC-V | 4.5 MW | 1,000 / 1,000 (100.00%) |
| 18.2 MW | Fixed horizon | 4.5 MW | 892 / 1,000 (89.20%) |
| 18.0 MW | Rolling risk-aware MPC | 4.9 MW | 0 / 1,000 (0.00%) |
| 18.0 MW | Rolling RAFC-V | 3.8 MW | 999 / 1,000 (99.90%) |
| 18.0 MW | Fixed horizon | 3.8 MW | 876 / 1,000 (87.60%) |

Risk-aware MPC calibrates its commitment on the event alone, so it still promises 4.9 MW. The shared rolling dispatcher already requires a feasible RecoveryGuard end state, so it cannot meet 4.9 MW within the reduced recovery headroom: the event dispatch was infeasible in all 1,000 scenarios. RAFC-V's recovery screen lowers the commitment to one that recovery can absorb. Paired exact McNemar p-values for risk-aware MPC versus RAFC-V are about 4e-301 (18.0 MW) and 2e-301 (18.2 MW); fixed horizon versus RAFC-V are about 2e-37 and 6e-33.

Interpretation limits: the ceilings were chosen to expose the recovery constraint, so this shows when the recovery-aware screen helps and not that it helps in general. The comparison is against an event-only commitment rule. An MPC that also screens recovery would be expected to match RAFC-V. The extra recovery constraint inside the shared dispatcher is what turns the recovery shortfall into an infeasible event for MPC.

## Assumptions and limitations

- FP-001 uses modeled 20 MW facility baseline, 5 MW request, 60-minute event, and 17 MW recovery base; these are not facility measurements.
- Disturbance probabilities and distributions are research assumptions, not empirically calibrated probabilities.
- A sampled disturbance is constant during one event. Rolling control receives it at each interval and the optimizer uses nominal forecasts for future intervals; a regression test checks that future observations do not change an earlier action.
- Critical-power deviation is common-mode to the baseline-relative reduction measurement. Critical service quality and nonlinear facility dynamics are not represented.
- Flexible compute is MW-equivalent-hours; workload queueing, GPU performance, and workload-specific production traces are abstracted.
- The rolling risk-aware MPC baseline uses event-only commitment calibration. Its dispatch shares RAFC-V's recovery-feasible rolling optimizer and RecoveryGuard, isolating the added recovery-aware commitment screen.
- Fixed-horizon dispatch is computed before the held-out scenarios and includes the same one-sided 99% meter-noise margin. It does not re-optimize after disturbances.
- These are research simulations, not datacentre/utility certification or a claim of general RAFC-V superiority.
