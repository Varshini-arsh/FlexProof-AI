# Implementation checklist

- [x] Phase A: Python 3.12 packaging, FP-001 YAML, units/contracts, typed boundary types.
- [x] Phase B: facility/battery models, job backlog/deadlines, grid event telemetry, nominal FP-001 event, result schema validation.
- [ ] Phase C (in progress): rule-based and deterministic MPC baselines, uncertainty generation, scenario-based reliability calibration, and RAFC-V commitment/event/recovery integration are implemented; rolling event re-optimization remains.
- [ ] Phase D (in progress): RecoveryGuard, stable `flexproof.engine` API, strict input and result schema validation, and generated example fixtures are implemented; API edge-case coverage and independent verification readiness remain.
- [ ] Phase E (in progress): four-controller common-random-number runner, held-out Wilson intervals, paired McNemar tests, CSV/JSON output, and plots are implemented. A 1,000-scenario smoke evaluation is recorded; planned 5,000-scenario test, ablations, and technical report remain.

Latest local validation: `67 passed` (pytest). Editable installation and the documented `flexproof.engine` import were verified. The 1,000-scenario held-out smoke run is preliminary and uses modeled assumptions.
