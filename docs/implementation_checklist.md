# Implementation checklist

- [x] Phase A: Python 3.12 packaging, FP-001 YAML, units/contracts, typed boundary types.
- [x] Phase B: facility/battery models, job backlog/deadlines, grid event telemetry, nominal FP-001 event, result schema validation.
- [ ] Phase C (in progress): rule-based and deterministic MPC baselines, uncertainty generation, scenario-based reliability calibration, RAFC-V commitment/event/recovery integration, and rolling event re-optimization are implemented; disturbance calibration remains assumption-based.
- [ ] Phase D (in progress): RecoveryGuard, stable `flexproof.engine` API, strict input and result schema validation, and generated example fixtures are implemented; API edge-case coverage and independent verification readiness remain.
- [ ] Phase E (in progress): four-controller common-random-number runner, held-out Wilson intervals, paired McNemar tests, CSV/JSON output, plots, a 5,000-scenario FP-001 run, and three ablations are implemented. Rolling-ablation held-out effect is not estimated; sequential closed-loop uncertainty evaluation and broader sensitivity experiments remain.

Latest local validation: `71 passed` (pytest). Editable installation and the documented `flexproof.engine` import were verified. The 5,000-scenario result uses modeled assumptions and does not establish field performance.
