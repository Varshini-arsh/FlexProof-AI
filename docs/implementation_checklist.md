# Implementation checklist

- [x] Phase A: Python 3.12 packaging, FP-001 YAML, units/contracts, typed boundary types.
- [x] Phase B: facility/battery models, job backlog/deadlines, grid event telemetry, nominal FP-001 event, result schema validation.
- [ ] Phase C (in progress): rule-based and deterministic MPC baselines, uncertainty generation, scenario-based reliability calibration, and RAFC-V commitment/event/recovery integration are implemented; rolling event re-optimization remains.
- [ ] Phase D (in progress): RecoveryGuard, stable `flexproof.engine` API, strict input and result schema validation, and generated example fixtures are implemented; API edge-case coverage and independent verification readiness remain.
- [ ] Phase E: four-controller experiments, held-out reliability results, ablations, plots.

Latest local validation: `63 passed` (pytest). Editable installation and the documented `flexproof.engine` import were also verified. This validates software behavior only; no held-out reliability claim is made.
