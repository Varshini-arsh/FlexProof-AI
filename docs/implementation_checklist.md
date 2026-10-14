# Implementation checklist

- [x] Phase A: Python 3.12 packaging, FP-001 YAML, units/contracts, typed boundary types.
- [x] Phase B: facility/battery models, job backlog/deadlines, grid event telemetry, nominal FP-001 event, result schema validation.
- [ ] Phase C (in progress): rule-based and deterministic MPC baselines, uncertainty generation, scenario-based reliability calibration are implemented; integrated RAFC-V remains.
- [ ] Phase D (in progress): RecoveryGuard joint recovery optimizer and schema validation are implemented; stable integration API and fixtures remain.
- [ ] Phase E: four-controller experiments, held-out reliability results, ablations, plots.

Latest local validation: `54 passed` (pytest). This validates software behavior only; no held-out reliability claim is made.
