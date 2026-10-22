# Integration guide

Install with Python 3.12 using python -m pip install -e ".[dev]".

The current event runner is `simulator.engine.run_nominal_event(config)`, where config is a mapping or YAML path. It returns a JSON-compatible schema 1.0.0 result with twelve interval samples for FP-001. This is a single nominal scenario; it does not evaluate or certify the 95% reliability target.

Recovery planning is available through `optimization.recovery.plan_recovery(config, backlog_mwh=..., current_soc=...)`. It returns schema 1.0.0 JSON-compatible output. Workload restoration and battery charging share the same headroom below the recovery grid-import ceiling. Infeasible planning is returned with status `infeasible`; solver failures are returned as `solver_error` without manufacturing a fallback schedule.

The integrated RAFC-V controller is `optimization.rafc_v.run_rafc_v(config, calibration_scenarios=1000, calibration_seed=100000, commitment_step_mw=0.1)`. It performs calibration, filters candidates using recovery constraints, re-optimizes event dispatch each interval, and verifies nominal recovery. Its reliability estimate and lower confidence bound are calibration evidence only. It returns zero commitment with status `unconfirmed` when the supplied calibration evidence cannot support the target. For simulation and tests, pass one observation mapping per event interval with optional `available_flexible_compute_mw`, `battery_discharge_scale`, `initial_soc_error`, `critical_power_delta_mw`, and `meter_noise_mw` keys.

The stable Member 2 interface is now available and independent of FastAPI and database internals:

```python
from flexproof.engine import evaluate_commitment, run_scenario

assessment = evaluate_commitment("configs/fp001.yaml", n_scenarios=1000, seed=20261014)
result = run_scenario("configs/fp001.yaml", controller="rafc_v")
```

`run_scenario` accepts a YAML/JSON path, mapping, or `ScenarioConfig`, and supports `nominal`, `rule_based`, `deterministic_mpc`, `risk_aware_mpc`, and `rafc_v`. It returns a schema-validated JSON-compatible result and includes a RecoveryGuard plan when event telemetry supports recovery planning. Invalid inputs return status `invalid_input`. `evaluate_commitment` returns calibration evidence and is not a held-out evaluation.

See `contracts/examples/fp001_scenario.json` and `contracts/examples/fp001_nominal_result.json` for fixtures generated through the public API.

For the React/FastAPI prototype, see `docs/fullstack_poc.md`. Install `.[api,dev]`; start `python -m uvicorn backend.app.main:app --reload`, then run `npm ci && npm run dev` in `frontend`. The API is the adapter boundary: it calls `flexproof.engine.run_scenario`, stores runs in SQLite, checks returned power/energy telemetry independently, and provides run retrieval and PDF export. The verification checks arithmetic consistency, not independent certification.
