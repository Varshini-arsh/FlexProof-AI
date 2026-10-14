# Integration guide

Install from the repository with Python 3.12 using pip install -e ".[dev]". The engine will expose flexproof.engine.run_scenario(config, controller=...) and evaluate_commitment(config); controller internals remain outside API dependencies. YAML config is a mapping and output is JSON-serializable schema 1.0.0. Current foundation provides typed config/result shapes in simulator.models; full entry points arrive with the event engine phase.
