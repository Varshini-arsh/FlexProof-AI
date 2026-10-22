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

## Live demo

- Frontend: https://flexproof-ai.vercel.app
- Backend API: https://flexproof-api.vercel.app (docs at `/docs`, health at `/api/health`)

Both are deployed on Vercel as two projects: the frontend from the `frontend` folder, and the backend from the repo root (`api/index.py`, `vercel.json`). The backend runs as a serverless function, so run history is kept in `/tmp` and resets between cold starts. This is a demo, not a production deployment.

## Full-stack prototype

Install Python 3.12 and the API/test extras, then start the API:

```powershell
python -m pip install -e ".[api,dev]"
python -m uvicorn backend.app.main:app --reload
```

In another terminal, start the React app:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. The planner validates the scenario, calls the public `flexproof.engine` API, stores the result in SQLite, runs independent arithmetic checks, and offers a PDF report. `GET /api/runs` lists persisted runs. API docs are at `http://127.0.0.1:8000/docs`.

For a containerized run, use `docker compose up --build` and open `http://localhost:8080`. SQLite data persists in the `flexproof-data` volume. Set `FLEXPROOF_DB_PATH` to change the local database path and `VITE_API_BASE_URL` to change the frontend API base.

The result's reliability evidence is calibration evidence only. Independent verification checks returned telemetry arithmetic; it is not facility or utility certification.
See [docs/fullstack_poc.md](docs/fullstack_poc.md) for the data flow, configuration, and scope limits.

Run a smaller four-controller experiment with `python -m evaluation.run_fp001 --calibration-scenarios 200 --test-scenarios 200`. The default runner uses 1,000 calibration and 5,000 held-out scenarios and writes JSON, CSV, and a plot under `results/fp001`.

Run the paired fixed, rolling risk-aware MPC, and rolling RAFC-V evaluation with `python -m evaluation.run_closed_loop --calibration-scenarios 1000 --test-scenarios 100`. It writes per-scenario CSV and aggregate JSON under `results/closed-loop-fp001`. Use the planned 5,000 held-out scenarios for confirmatory reliability estimates.

Run the deterministic RecoveryGuard sensitivity grid with `python -m evaluation.run_recovery_sensitivity`; it writes JSON and CSV under `results/recovery-sensitivity`.
