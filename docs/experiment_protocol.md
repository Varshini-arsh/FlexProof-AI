# FP-001 experiment protocol

## Controller set

The runner compares rule-based dispatch, deterministic Pyomo/HiGHS dispatch, risk-aware MPC with event-only commitment calibration, and RAFC-V with recovery-aware commitment. All receive the same held-out disturbance scenarios. Rule-based and deterministic MPC attempt the full request; risk-aware MPC and RAFC-V select commitments from the same calibration seed set and candidate grid. RecoveryGuard is evaluated after dispatch for every controller, while only RAFC-V uses recovery feasibility during commitment selection.

## Split and reproducibility

`evaluation.compare.compare_controllers` takes explicit calibration and test sample counts and seed starts. It rejects overlapping integer seed ranges. Each scenario seed is generated once and reused across all controllers (common random numbers). Default CLI settings are 1,000 calibration scenarios starting at 100000 and 5,000 held-out scenarios starting at 200000. Use smaller counts only for development smoke tests. Do not tune controller parameters against held-out results.

Run the planned test with:

```powershell
python -m evaluation.run_fp001 --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 5000 --test-seed 200000 --commitment-step-mw 0.1
```

The runner writes JSON and CSV metrics plus a PNG plot under `results/fp001` by default. The JSON preserves controller results, solver metadata, calibration and held-out splits, Wilson intervals, and paired exact McNemar tests.

## Metrics and statistical interpretation

Metrics include accepted MW, calibration estimate and lower confidence bound, held-out complete-event success and Wilson interval, joint event/recovery feasibility and Wilson interval, event delivery shortfall count and mean MW shortfall, modeled battery reserve violations, nominal RecoveryGuard status and recovery import peak, solver runtime, and computational failures. Paired McNemar tests use the common held-out scenario ordering. Statistical significance does not establish operational materiality or field performance.

The commitment scenario pass model treats each disturbance realization as persistent through the event. Critical power uncertainty is common-mode to baseline-relative response and does not currently model a separate critical-load service violation. Recovery feasibility is evaluated using the exact cumulative shared-headroom/rate screen for the current RecoveryGuard LP; nominal schedules are independently solved by RecoveryGuard. These results do not replace facility telemetry, production workload traces, utility validation, or held-out testing at the planned 5,000-scenario count.

## Preliminary 1,000 + 1,000 smoke result

The checked-in `results/fp001-cal1000-test1000` output uses 1,000 calibration scenarios (seed start 100000), 1,000 disjoint held-out scenarios (seed start 200000), and a 0.5 MW candidate step. Rule-based and deterministic MPC each attempt 5.0 MW and achieved 95.3% held-out event and joint recovery feasibility (Wilson 95% interval 93.8–96.4%). Risk-aware MPC and RAFC-V each selected 4.5 MW and achieved 99.3% (98.6–99.7%). At this FP-001 setting, RAFC-V and risk-aware MPC had identical commitments and paired outcomes (McNemar p=1.0); this smoke run therefore shows no measured incremental recovery-aware benefit over risk-aware MPC. Full RAFC-V benefit remains unestablished pending the planned experiment matrix and ablations.
