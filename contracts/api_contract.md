# Engine contract schema 1.0.0

The public import surface is `flexproof.engine`:

```python
from flexproof.engine import evaluate_commitment, load_scenario, run_scenario

scenario = load_scenario("configs/fp001.yaml")
assessment = evaluate_commitment(scenario, n_scenarios=1000, seed=20261014)
result = run_scenario(scenario, controller="rafc_v")
```

Inputs may be a YAML/JSON path, a mapping, or `ScenarioConfig`. The input schema requires schema version, scenario ID, integer seed, facility, battery, grid event, and recovery settings. Units are documented in `units.md`; the JSON schema is `scenario.schema.json`.

`run_scenario` supports `nominal`, `rule_based`, `deterministic_mpc`, `risk_aware_mpc`, and `rafc_v`. It returns JSON-compatible schema 1.0.0 output, validated against `result.schema.json`. Results carry a run ID, controller, status, accepted commitment or infeasibility reason, reliability evidence, event and recovery telemetry where available, constraint violations, solver metadata, random seed, and assumptions. Status values are `completed`, `infeasible`, `solver_error`, and `invalid_input`; a reliability sub-status can be `confirmed`, `unconfirmed`, or `not_evaluated`.

`evaluate_commitment` returns the candidate table, estimate, Wilson interval, simultaneous lower bound, seed, sample count, and evidence method. These are calibration outputs unless the caller deliberately supplies a held-out split; they must not be presented as held-out validation by default. `run_scenario` defaults the calibration seed to the scenario seed and keeps evidence labeled `calibration`.

See `examples/fp001_scenario.json` and `examples/fp001_nominal_result.json` for valid fixtures. The nominal result fixture is one generated run and does not demonstrate reliability.

The `evaluation.run_closed_loop` files are versioned experiment artifacts (`artifact_type: experiment_result`), not individual `run_scenario` result objects; they therefore do not replace or alter the schema 1.0.0 API contract. Their CSV/JSON values are standard JSON-compatible scalar, list, and mapping values. Member 2 should continue to integrate the per-scenario engine through `flexproof.engine`.

## Application API

- `GET /api/health` reports API and research-engine import health.
- `GET /api/runs?limit=50` lists persisted run metadata; `GET /api/runs/{run_id}` restores the request, scenario, event/recovery telemetry, and independent verification from the database.
- `POST /api/scenarios/validate` validates the request schema and builds the normalized FP-001 scenario. It does not claim physical feasibility.
- `POST /api/scenarios/run` executes the selected controller, persists the complete run, and returns `{status, simulation_type, reliability_certified: false, scenario, result, independent_verification, storage_status}`. The verifier runs separate electrical, battery-energy, aggregate-workload, deadline, and recovery checks against returned telemetry. A simulated run does not establish the 95% statistical reliability target.
- `POST /api/commitments/evaluate` returns a recommended MW, calibration estimates and confidence bounds, candidate details, feasibility explanation, and held-out validation status. Calibration and held-out results must remain clearly distinguished.
- `POST /api/evidence/verify` accepts `{scenario, result, expected_input_hash?, expected_evidence_hash?}` and returns a verification status (`pass`, `fail`, or `insufficient_evidence`), named checks, metrics, verifier version, scope, and limitations.
- `POST /api/evidence/export` accepts the same evidence body and returns the JSON bundle described by `evidence.schema.json`.
- `POST /api/evidence/telemetry.csv` and `POST /api/evidence/report.pdf` return downloadable interval CSV and PDF evidence respectively.
- `GET /api/benchmarks/closed-loop` reads the recorded benchmark summary. It reports whether full local raw files match recorded SHA-256 values, are absent, or mismatch. On mismatch, numerical metrics are not displayed.

Power is MW AC at the facility grid boundary; battery energy is MWh; SoC is a fraction in engine JSON and percentage only in display. Event delivery is recomputed as baseline import minus measured import. Evidence hashes use canonical JSON with integral float values normalized to integers, to remain stable across common JSON clients. These hashes provide content comparison only; they are not signatures or sensor authenticity proofs.

Persistence uses Alembic revision `0001_initial_records`. Local default storage is `.cache/flexproof.sqlite3`; Compose uses PostgreSQL 16. Apply migrations with `python -m alembic upgrade head`. The database stores each scenario once, result metadata without interval arrays, event and recovery intervals as keyed rows, independent verification, and report metadata with output checksums.
