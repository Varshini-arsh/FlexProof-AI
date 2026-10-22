# FlexProof AI implementation checklist

## Phase A — Foundation: complete

- [x] Python 3.12 package and dependency groups.
- [x] FP-001 and uncertainty YAML configurations.
- [x] Units, typed boundary models, versioned JSON schemas, and valid fixtures.
- [x] Setup, engine, and integration documentation.

## Phase B — Physically consistent simulator: complete

- [x] Facility AC-side power balance, battery SoC and inverter limits, workload backlog/deadlines, grid events, and telemetry.
- [x] Nominal FP-001 scenario execution and constraint checks.
- [x] Battery, workload, facility, dispatch, recovery, and integration tests.

## Phase C — Controllers: complete for the FP-001 model

- [x] Transparent rule-based and Pyomo/HiGHS deterministic controllers.
- [x] Seeded uncertainty scenarios and scenario-based reliability calibration.
- [x] Reliability-aware commitments, recovery-aware RAFC-V screening, and rolling event re-optimization.
- [x] Tests guard against future-observation leakage and distinguish calibration evidence from held-out outcomes.

## Phase D — Recovery and integration: complete for the local prototype

- [x] RecoveryGuard jointly allocates grid headroom to battery charging and deferred compute, and returns explicit infeasibility.
- [x] Stable `flexproof.engine` import API and schema-validated JSON-compatible results.
- [x] FastAPI adapter, SQLite run history, arithmetic verification, and PDF report endpoint.
- [x] React planner and history pages call the API; Docker Compose serves the UI and API and persists the database in a named volume.
- [x] End-to-end Docker request after disk migration: RAFC-V run saved, retrieved from history, verified, and exported as PDF.

## Phase E — Research evaluation: implemented and run for FP-001 assumptions

- [x] Four-controller common-scenario evaluation, corrected paired closed-loop comparison, Wilson intervals, paired tests, and RecoveryGuard sensitivity.
- [x] 5,000 paired held-out scenarios and a 48-case deterministic recovery sensitivity grid; results are recorded in `RESULTS_AND_LIMITATIONS.md`.
- [x] Ablation code covers reliability calibration, recovery-aware commitment, and rolling re-optimization. The analytical scenario-pass ablation does not estimate closed-loop held-out effects for every ablation.

## Current verification

- `.\.venv\Scripts\python.exe -m pytest -q`: **82 passed**, one upstream Starlette/httpx deprecation warning.
- `npm run lint` (from `frontend`): **passed**.
- `npm run build` (from `frontend`): **passed**. Vite reports a 609 kB minified JS bundle; this is a load-time optimization opportunity, not a build failure.
- Docker Compose: backend and frontend run; API health, frontend proxy, FP-001 defaults, persisted history, verification, and PDF endpoints responded successfully.

## Limits and follow-up research

- Disturbance probabilities and the FP-001 facility/recovery values are modeled assumptions, not measured facility data.
- The 5,000-scenario result is evidence for the specified simulator only. It does not establish field performance, utility certification, or general RAFC-V superiority; rolling RAFC-V matched the fair rolling risk-aware MPC baseline in the recorded evaluation.
- Raw 5,000-scenario closed-loop JSON/CSV are not present in this checkout because generated `results/` outputs are ignored. Reproduce them with the command in `RESULTS_AND_LIMITATIONS.md`.
- Production hosting, authentication, authorization, multi-user data isolation, external database operations, facility telemetry integration, and operational security are outside this local proof of concept.
