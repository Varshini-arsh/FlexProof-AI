# Implementation checklist

- [x] Phase A: Python 3.12 packaging, FP-001 YAML, units/contracts, typed boundary types.
- [x] Phase B: facility/battery models, job backlog/deadlines, grid event telemetry, nominal FP-001 event, result schema validation.
- [ ] Phase C (in progress): rule-based and deterministic MPC baselines, uncertainty generation, scenario-based reliability calibration, RAFC-V commitment/event/recovery integration, and rolling event re-optimization are implemented; disturbance calibration remains assumption-based.
- [ ] Phase D (in progress): RecoveryGuard, stable `flexproof.engine` API, strict input and result schema validation, and generated example fixtures are implemented; API edge-case coverage and independent verification readiness remain.
- [ ] Phase E (in progress): four-controller scenario-pass benchmark and ablations are implemented. Corrected closed-loop fixed-horizon, rolling risk-aware MPC, and rolling RAFC-V evaluation ran for 5,000 held-out cases; RecoveryGuard sensitivity ran for 48 deterministic cases. Broader operating scenarios and measured facility data remain.

Latest validation: `77 passed` (`.venv\\Scripts\\python.exe -m pytest -q`). The 5,000-case closed-loop run and RecoveryGuard sensitivity sweep completed; see `docs/RESULTS_AND_LIMITATIONS.md`. All experiment inputs are modeled assumptions and do not establish field performance.
