# FlexProof AI

Research engine for datacentre flexibility simulation, reliability-aware commitment, and recovery planning.

## Setup

Requires Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

The engine is independent of web APIs and databases. See contracts/units.md and contracts/api_contract.md.
FP-001 is a modeled assumption, not measured data or grid certification. The 17 MW recovery base is an explicit post-event planning baseline for non-flexible demand plus scheduled non-deferred compute. Deferred jobs and battery charging share the 20 MW recovery ceiling.

The stable Python entry points are `flexproof.engine.load_scenario`, `evaluate_commitment`, and `run_scenario`. See docs/integration_guide.md for controller options and contracts/examples for schema-valid input/output fixtures.

Run a smaller four-controller experiment with `python -m evaluation.run_fp001 --calibration-scenarios 200 --test-scenarios 200`. The default runner uses 1,000 calibration and 5,000 held-out scenarios and writes JSON, CSV, and a plot under `results/fp001`.
