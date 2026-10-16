# Integration guide

Install with Python 3.12 using python -m pip install -e ".[dev]".

The current event runner is `simulator.engine.run_nominal_event(config)`, where config is a mapping or YAML path. It returns a JSON-compatible schema 1.0.0 result with twelve interval samples for FP-001. This is a single nominal scenario; it does not evaluate or certify the 95% reliability target.

Recovery planning is available through `optimization.recovery.plan_recovery(config, backlog_mwh=..., current_soc=...)`. It returns schema 1.0.0 JSON-compatible output. Workload restoration and battery charging share the same headroom below the recovery grid-import ceiling. Infeasible planning is returned with status `infeasible`; solver failures are returned as `solver_error` without manufacturing a fallback schedule.

The public `flexproof.engine.run_scenario(config, controller=...)` and `evaluate_commitment(config)` functions are independent of FastAPI and database internals.

## Local application integration

From the repository root, create a Python 3.12 environment and install `python -m pip install -e ".[api,dev]"`. Start the API with `python -m uvicorn backend.app.main:app --reload --port 8000`. In a second terminal, run `cd frontend`, `npm ci`, then `npm run dev`. The Vite app uses `VITE_API_BASE_URL` when set and otherwise calls `http://127.0.0.1:8000/api`.

The planner sends a validated `ScenarioRequest` to `POST /api/scenarios/run`; the response contains the normalized scenario, engine result, and independently recomputed verification. `POST /api/commitments/evaluate` runs risk-aware calibration and labels its evidence as calibration. Held-out validation is reported unavailable unless a separately produced artifact is attached.

The Grid Event Monitor and RecoveryGuard read the selected API run's actual telemetry from React state. `POST /api/evidence/verify` accepts `{ "scenario": ..., "result": ... }`, with optional `expected_input_hash` and `expected_evidence_hash`, and returns `pass`, `fail`, or `insufficient_evidence`. Verification uses independent electrical, battery, and aggregate-work arithmetic. A pass is not service-quality, sensor-authenticity, field, or utility certification.

The Verification Portal downloads a JSON evidence bundle (`POST /api/evidence/export`), interval CSV (`POST /api/evidence/telemetry.csv`), and PDF report (`POST /api/evidence/report.pdf`). SHA-256 values support content comparison; they are not signatures. The bundle conforms to `contracts/evidence.schema.json`.

Runs and interval telemetry are persisted in normalized `scenario_configs`, `simulation_runs`, and `telemetry_intervals` tables. Independent results and export metadata are stored separately in `verification_records` and `report_metadata`. Run history uses `GET /api/runs` and `GET /api/runs/{run_id}`. Configure `DATABASE_URL` and apply `python -m alembic upgrade head` before starting the API. Local runs default to SQLite; Compose connects to PostgreSQL.

`GET /api/benchmarks/closed-loop` serves `results/benchmark_summary.json` and checks the hashes of full raw files when present. It returns `summary_only_raw_files_unavailable` on a clean clone without local raw artifacts and `integrity_mismatch` if a present file differs. The UI does not substitute sample values when the artifact is unavailable or corrupted.

For Docker Compose, use `docker compose -p flexproof-m2 up --build -d`. It runs PostgreSQL, the FastAPI service (8011), and React through Nginx (8081), with the migration applied before the API starts. The named database volume is retained by ordinary `down`.

## Research controller details

For direct experiment use, `optimization.rafc_v.run_rafc_v` accepts calibration scenario count/seed, commitment step, and optional per-interval observations. It performs scenario calibration and rolling dispatch using the research implementation. Calibration evidence is not held-out evidence. `optimization.recovery.plan_recovery` is the shared-headroom RecoveryGuard implementation; the application calls it through `flexproof.engine.run_scenario` and independently checks its returned telemetry. Do not call a successful nominal run a reliability pass.