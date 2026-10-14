# FP-001 experiment protocol

## Controller set

The runner compares rule-based dispatch, deterministic Pyomo/HiGHS dispatch, risk-aware MPC with event-only commitment calibration, and RAFC-V with recovery-aware commitment and rolling event dispatch. All receive the same held-out disturbance scenarios. Rule-based and deterministic MPC attempt the full request; risk-aware MPC and RAFC-V select commitments from the same calibration seed set and candidate grid. RecoveryGuard is evaluated after dispatch for every controller, while only RAFC-V uses recovery feasibility during commitment selection.

## Split and reproducibility

`evaluation.compare.compare_controllers` takes explicit calibration and test sample counts and seed starts. It rejects overlapping integer seed ranges. Each scenario seed is generated once and reused across all controllers (common random numbers). Default CLI settings are 1,000 calibration scenarios starting at 100000 and 5,000 held-out scenarios starting at 200000. Use smaller counts only for development smoke tests. Do not tune controller parameters against held-out results.

Run the planned test with:

```powershell
python -m evaluation.run_fp001 --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 5000 --test-seed 200000 --commitment-step-mw 0.1
```

The runner writes JSON and CSV metrics plus a PNG plot under `results/fp001` by default. The JSON preserves controller results, solver metadata, calibration and held-out splits, Wilson intervals, and paired exact McNemar tests.

## Metrics and statistical interpretation

Metrics include accepted MW, calibration estimate and lower confidence bound, held-out complete-event success and Wilson interval, joint event/recovery feasibility and Wilson interval, event delivery shortfall count and mean MW shortfall, modeled battery reserve violations, nominal RecoveryGuard status and recovery import peak, solver runtime, and computational failures. Paired McNemar tests use the common held-out scenario ordering. Statistical significance does not establish operational materiality or field performance.

The commitment scenario pass model treats each disturbance realization as persistent through the event. Critical power uncertainty is common-mode to baseline-relative response and does not currently model a separate critical-load service violation. Recovery feasibility is evaluated using the exact cumulative shared-headroom/rate screen for the current RecoveryGuard LP; nominal schedules are independently solved by RecoveryGuard. Held-out reliability uses scenario pass calculations rather than closed-loop execution of each controller; rolling performance under sequential disturbance observations is not yet included in the 5,000-scenario statistics. These results do not replace facility telemetry, production workload traces, or utility validation.

## Preliminary 1,000 + 1,000 smoke result

The checked-in `results/fp001-cal1000-test1000` output uses 1,000 calibration scenarios (seed start 100000), 1,000 disjoint held-out scenarios (seed start 200000), and a 0.5 MW candidate step. Rule-based and deterministic MPC each attempt 5.0 MW and achieved 95.3% held-out event and joint recovery feasibility (Wilson 95% interval 93.8–96.4%). Risk-aware MPC and RAFC-V each selected 4.5 MW and achieved 99.3% (98.6–99.7%). At this FP-001 setting, RAFC-V and risk-aware MPC had identical commitments and paired outcomes (McNemar p=1.0); this smoke run therefore shows no measured incremental recovery-aware benefit over risk-aware MPC. Full RAFC-V benefit remains unestablished pending the planned experiment matrix and ablations.

## FP-001 1,000 calibration + 5,000 held-out result

The current larger run is checked in under `results/fp001-cal1000-test5000` (calibration seeds 100000–100999; test seeds 200000–204999; candidate step 0.1 MW). Rule-based and deterministic MPC attempted 5.0 MW and delivered complete events in 4,743/5,000 scenarios (94.86%, Wilson 95% interval 94.21–95.44%). Their point estimate is below the 95% target and the confidence interval spans it, so the target is not statistically established for that commitment. Risk-aware MPC and RAFC-V selected 4.9 MW, with calibration estimate 98.4% and simultaneous lower bound 96.63%; held-out success was 4,922/5,000 (98.44%, Wilson 95% interval 98.06–98.75%).

Joint event-and-recovery success matched event success for each controller in this run. All four nominal RecoveryGuard plans completed; modeled battery reserve violations were zero. RAFC-V and risk-aware MPC had identical commitments and outcomes (paired exact McNemar p=1.0). The comparison therefore supports the reliability-aware commitment reduction relative to attempting the full request, but shows no incremental RAFC-V improvement over risk-aware MPC for FP-001. This is a model-based result for one frozen setup, not evidence of general superiority.

The output includes ablations for disabling reliability calibration (deterministic MPC vs risk-aware MPC), disabling recovery-aware commitment (risk-aware MPC vs RAFC-V), and disabling rolling re-optimization (RAFC-V fixed horizon vs rolling). For the nominal FP-001 schedule, rolling re-optimized 12 times and delivered a minimum measured reduction of 4.9465 MW for a 4.9 MW commitment; fixed-horizon delivered 4.9 MW. Both cleared the 4.0 MWh workload backlog and completed RecoveryGuard. Rolling ended at 25.04% SoC versus 25.53% for fixed-horizon, with nominal recovery peaks of 18.262 and 18.249 MW respectively. This schedule comparison does not establish a held-out rolling-control benefit: the held-out evaluator does not execute sequential controller actions. In FP-001, recovery-aware commitment selected the same MW as event-only risk calibration.

## Corrected closed-loop protocol

Run the three-arm closed-loop comparison with:

```powershell
.\.venv\Scripts\python.exe -m evaluation.run_closed_loop --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 5000 --test-seed 400000 --commitment-step-mw 0.1 --output-dir results/closed-loop-fp001-5000
```

The 1,000 calibration seeds (100000-100999) are distinct from the 5,000 held-out seeds (400000-404999), the 100-case smoke sample (300000-300099), and the analytical benchmark test range (200000-204999). Commitments are selected from calibration evidence only. The fixed-horizon plan includes the same one-sided 99% meter-noise margin as rolling dispatch. Rolling risk-aware MPC and RAFC-V share the rolling optimizer and RecoveryGuard; only RAFC-V calibration applies the recovery feasibility screen. Results, confidence intervals, failure counts, runtime, and limitations are in `RESULTS_AND_LIMITATIONS.md`.

The earlier 42/100 fixed-horizon smoke outcome is withdrawn: its schedule omitted the rolling controller's meter margin. It must not be used as evidence. The corrected 100-case smoke run and 5,000-case held-out run use matched margins. The 5,000-case JSON/CSV are local, reproducible experiment artifacts and remain excluded from the code/docs commit because of their size.
