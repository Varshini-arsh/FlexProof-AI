# Member 1 Development Status

## Current branch and working state

Branch snapshot: `feature/simulation-optimization` at `b5712c2d5af49d70627225ae9f1a5127fb84976a`. At the time this status was first written it was local-only; the branch is now present on `origin/feature/simulation-optimization`.

## Completed and validated

- FP-001 facility, battery, workload, event, recovery, typed input/output, and Python engine modules.
- Rule-based and deterministic optimization baselines; scenario-based reliability calibration; RAFC-V; RecoveryGuard.
- Four-controller analytical held-out evaluation and a corrected closed-loop evaluator for fixed-horizon, rolling risk-aware MPC, and rolling RAFC-V.
- Closed-loop experiment exports experiment-level JSON and per-scenario CSV. These are not individual schema 1.0.0 API result records; Member 2 should continue to call `flexproof.engine`.
- Final test suite: 77 passed using `.venv\Scripts\python.exe -m pytest -q`.

## Current experiment

The corrected 100-scenario closed-loop smoke run, independent 5,000-scenario held-out evaluation, and 48-case RecoveryGuard sensitivity sweep are recorded in `RESULTS_AND_LIMITATIONS.md`. The 5,000-run used fresh seeds 400000–404999; both rolling controllers selected 4.9 MW and had identical 97.76% held-out event/recovery success. The sensitivity sweep had 45/48 feasible cases.

## Known limitations

- All uncertainty values remain assumed rather than measured.
- The scenario evaluator uses a constant event-level disturbance with interval-by-interval observation delivery.
- Rolling risk-aware MPC and RAFC-V use the same dispatch/recovery optimizer. The research distinction is the recovery-aware commitment screen; same commitment yields the same controller actions.
- The prior unfair fixed-horizon smoke result is withdrawn and must not be cited.
- Rolling dispatch outperformed the matched-margin fixed schedule on this modeled held-out set, but RAFC-V showed no incremental improvement over rolling risk-aware MPC because both selected the same commitment and produced identical outcomes.
- This prototype is not field validation or utility certification.

## Verification and Git state

The final full test run passed (`77 passed`). New modules compile and `git diff --check` passes. Generated 5,000-scenario CSV/JSON outputs are 3.4 MB/18.7 MB and remain ignored local artifacts. At this integration audit, `feature/simulation-optimization` is published at `b5712c2d5af49d70627225ae9f1a5127fb84976a`; the isolated integration worktree uses a separate local branch and has not been pushed.

## Joint integration audit

Member 2’s `feature/fullstack-verification` consumes `flexproof.engine` and the shared Member 1 simulator, optimization, workload, uncertainty, and recovery implementations. The shared research source blobs compared equal between the two feature branch tips before merge. The full application adds a FastAPI adapter, React UI, independent evidence verifier, report exports, and database persistence without replacing the research optimizer.

The joint integration candidate is published at `integration/joint-poc-review`, commit `bee21d8cdf02139479f7d27cf8e1353945092595`, for review in PR #16. It includes the Member 1 and Member 2 feature tips listed above and does not modify either feature branch or `main`. The combined suite has 135 passing Python tests; the integrated application was exercised with Playwright and Docker as recorded in PR #16. See `docs/MEMBER2_PROGRESS.md` and `docs/RESULTS_AND_LIMITATIONS.md` for combined test and artifact details.
