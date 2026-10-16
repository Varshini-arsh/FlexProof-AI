# FP-001 evidence manifest

This manifest records the checked-in FP-001 research evidence. Calibration, held-out evaluation, and nominal execution are distinct evidence types. Results are from simulation under modeled assumptions, not field measurements or utility certification.

## Paired closed-loop controller comparison

- Experiment: `FP-001-closed-loop-controller-comparison`, result schema `1.0.0`.
- Method: fixed-horizon schedule, rolling risk-aware MPC, and rolling RAFC-V evaluated on shared held-out disturbances. Commitment selection used calibration data only; held-out outcomes were not used to select commitments.
- Configuration: `configs/fp001.yaml`, SHA-256 `d60b89221194155838a62cc1b5dc824cb9dcf6825f41aa14390fd5395c542b99`; disturbance assumptions are in `configs/uncertainty.yaml` (SHA-256 `f146dd9f4f835e1b980fca811cdc59cfbca0d09a108932b3b6d24468fc668c05`).
- Experiment code provenance: commit `a14604a1aca8dc5966f8b2a766b40d2331a1907c`; Member 1 engine revision `b5712c2d5af49d70627225ae9f1a5127fb84976a`; `evaluation/closed_loop.py` SHA-256 `568242911a6970b60aefea44ff064ba553987e984ef8e567012cc56aa65fbf41`.
- Controller identifiers: `fixed_horizon` is the experiment schedule in `evaluation/closed_loop.py` at the experiment commit; rolling risk-aware MPC uses `rolling-mpc-0.1.0`; rolling RAFC-V uses `rafc-v-0.1.0`; RecoveryGuard uses `recovery-guard-0.1.0`.
- Calibration: 1,000 scenarios, seeds `100000–100999`. Both rolling controllers selected 4.9 MW using calibration only. Passes: 984/1,000 (98.4%); simultaneous lower bound 96.634% at the 95% confidence level.
- Held-out: 5,000 paired scenarios, seeds `400000–404999`. Fixed horizon succeeded in 4,448/5,000 (88.96%). Rolling risk-aware MPC and RAFC-V each succeeded in 4,888/5,000 (97.76%, Wilson 95% CI 97.31–98.13%). The rolling methods had identical commitments and outcomes (paired McNemar p=1.0); no incremental RAFC-V improvement was demonstrated.
- Tracked summary: `results/benchmark_summary.json`, SHA-256 `7caba5bfd7c499c8d2788b539e7364f10cbd11357901fa31812a4d6dd9e1eb0`.
- Primary raw data is not tracked. It is locally available in the integration worktree under `results/closed-loop-fp001-reproduced/`; it has no reviewer download URL. JSON SHA-256 `02d62ec9ddd053d01d51d970c11f2e7f66af7904491c04311215d861909beadc`; CSV SHA-256 `76559ed9fd1443c7d8ec394bf315da3b7795d239b904ccb07a204978c44db8a4`. The 22.4 MB pair remains ignored and unpublished.
- Reproduction command:
  ```powershell
  .\.venv\Scripts\python.exe -m evaluation.run_closed_loop --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 5000 --test-seed 400000 --commitment-step-mw 0.1 --output-dir results/closed-loop-fp001-5000
  ```

## Four-controller analytical scenario evaluation

- Method: 1,000 calibration scenarios (seeds `100000–100999`) and 5,000 held-out scenario passes (seeds `200000–204999`). This evaluation calculates scenario pass outcomes; it does not execute sequential closed-loop controller actions.
- Calibration: 984/1,000 (98.4%); selected commitment 4.9 MW.
- Held-out: rolling risk-aware MPC and RAFC-V each passed 4,922/5,000 (98.44%, Wilson 95% CI 98.06–98.75%). This is a separate evaluation from the paired closed-loop experiment.
- Tracked aggregate JSON SHA-256 `0a4e405e52b1bb25e8f2908fc80d1b9ae6a5aa0f6b3e26f48e981be7d8ae1429`; aggregate CSV SHA-256 `2640e3fa9e6663f10cd1fc8c291ddc3ace481e383829fc93dd43bf7f47a945c4`. Per-scenario raw rows are not available in the repository.
- Reproduction command:
  ```powershell
  .\.venv\Scripts\python.exe -m evaluation.run_fp001 --calibration-scenarios 1000 --calibration-seed 100000 --test-scenarios 5000 --test-seed 200000 --commitment-step-mw 0.1
  ```

## Assumptions and distribution

Disturbance probabilities are modeled assumptions. The 17 MW recovery base is an explicit planning assumption. Workload power is represented in MW-equivalent-hours. Share the large raw files only after team approval, preferably through a versioned GitHub Release asset or controlled evidence archive with this manifest and verified SHA-256 checksums. Do not commit or publicly release raw data by default.
