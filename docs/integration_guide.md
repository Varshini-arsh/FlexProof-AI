# Integration guide

Install with Python 3.12 using python -m pip install -e ".[dev]".

The current Phase B runner is simulator.engine.run_nominal_event(config), where config is a mapping or YAML path. It returns a JSON-compatible schema 1.0.0 result with twelve interval samples for FP-001. This is a single nominal scenario; it does not evaluate or certify the 95% reliability target.

The later application API will be flexproof.engine.run_scenario(config, controller=...) and evaluate_commitment(config), independent of FastAPI and database internals.