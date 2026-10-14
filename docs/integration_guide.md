# Integration guide

Install with Python 3.12 using python -m pip install -e ".[dev]".

The current event runner is `simulator.engine.run_nominal_event(config)`, where config is a mapping or YAML path. It returns a JSON-compatible schema 1.0.0 result with twelve interval samples for FP-001. This is a single nominal scenario; it does not evaluate or certify the 95% reliability target.

Recovery planning is available through `optimization.recovery.plan_recovery(config, backlog_mwh=..., current_soc=...)`. It returns schema 1.0.0 JSON-compatible output. Workload restoration and battery charging share the same headroom below the recovery grid-import ceiling. Infeasible planning is returned with status `infeasible`; solver failures are returned as `solver_error` without manufacturing a fallback schedule.

The first integrated RAFC-V controller is `optimization.rafc_v.run_rafc_v(config, calibration_scenarios=1000, calibration_seed=100000, commitment_step_mw=0.1)`. It performs calibration, filters candidates using recovery constraints, solves an event schedule, and verifies nominal recovery. Its reliability estimate and lower confidence bound are calibration evidence only. It returns zero commitment with status `unconfirmed` when the supplied calibration evidence cannot support the target.

The later application API will be flexproof.engine.run_scenario(config, controller=...) and evaluate_commitment(config), independent of FastAPI and database internals.
