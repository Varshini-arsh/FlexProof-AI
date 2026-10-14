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
