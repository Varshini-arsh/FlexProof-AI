# FlexProof AI

FlexProof AI is a local research prototype for datacentre grid flexibility. Its Python engine models facility electricity, flexible workloads, battery dispatch, grid events, reliability-aware commitments, and post-event recovery. The React application uses a FastAPI adapter and displays actual simulation telemetry, independent operational checks, evidence exports, and a checksummed paired benchmark summary.

This is a simulated research PoC, not a field-validated product or utility certification. FP-001 is an explicit modeled configuration. In particular, the 17 MW recovery base is an assumption rather than an automatic consequence of the event.

## Requirements

- Python 3.12
- Node.js 22 or newer with npm
- HiGHS through the `highspy` Python package; no separate solver install is needed

## Run locally on Windows PowerShell

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[api,dev]"
python -m alembic upgrade head
python -m uvicorn backend.app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the Vite URL printed by the dev server. The frontend defaults to `http://127.0.0.1:8000/api`; set `VITE_API_BASE_URL` at build time to use another API URL. To allow another browser origin, configure `FLEXPROOF_CORS_ORIGINS` as a comma-separated list.

By default, local runs persist to `.cache/flexproof.sqlite3`. Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL to use PostgreSQL, then run `python -m alembic upgrade head` before starting the API. Run history is available in the Run History page and under `/api/runs`.

## Run the PostgreSQL-backed Compose demo

Docker Compose uses an isolated project name and ports so it can coexist with other local projects:

```powershell
docker compose -p flexproof-m2 up --build -d
```

Open `http://localhost:8081`; the API is at `http://localhost:8011` and PostgreSQL is exposed on port 5433 for local inspection. The database uses a named persistent volume. Before starting, copy `.env.example` to `.env` and set `POSTGRES_PASSWORD` to a local development value; Compose refuses to start without it. Never commit `.env`. Stop this stack with `docker compose -p flexproof-m2 down`; this leaves the database volume intact.

## Verify and test

```powershell
python -m pytest -q
cd frontend
npm run lint
npm run build
$env:FLEXPROOF_PYTHON = "..\.venv\Scripts\python.exe"
$env:PLAYWRIGHT_CHANNEL = "msedge"
npm run test:e2e
```

Playwright requires Microsoft Edge or another compatible installed browser. The browser tests launch an isolated API on port 8010 and Vite on 5175.

## Research engine and reproducible benchmark

Use the API-independent functions in `flexproof.engine` to load scenarios, evaluate commitments, and run controllers. See `contracts/api_contract.md`, `contracts/units.md`, and `docs/integration_guide.md`.

The checked-in `results/benchmark_summary.json` records a 1,000-scenario calibration and 5,000 paired held-out scenarios, their seeds, confidence intervals, paired tests, and raw file checksums. Full 19 MB JSON and 3.34 MB CSV artifacts are retained locally under `results/closed-loop-fp001-reproduced/` and are not required for app startup. The benchmark API explicitly indicates when those raw files are absent. The results and limitations are in `docs/RESULTS_AND_LIMITATIONS.md`.

See `docs/EVIDENCE_MANIFEST.md` for experiment splits, configuration and artifact hashes, controller versions, reproduction commands, and a recommended sharing method for large raw evidence.

## Reproducible research experiments

The tracked four-controller result set under `results/fp001-cal1000-test5000/` uses calibration seeds 100000–100999 and held-out seeds 200000–204999. The separate closed-loop controller evaluation summarized in `results/benchmark_summary.json` uses calibration seeds 100000–100999 and held-out seeds 400000–404999. These are distinct experiment protocols and are not interchangeable. In particular, the 98.4% value is the calibration estimate (984/1,000); the four-controller held-out result is 4,922/5,000 (98.44%), while the closed-loop rolling held-out result is 4,888/5,000 (97.76%). See `docs/RESULTS_AND_LIMITATIONS.md` before citing either result.

Run the four-controller experiment at a smoke-test size with `python -m evaluation.run_fp001 --calibration-scenarios 200 --test-scenarios 200`. Run the paired closed-loop smoke evaluation with `python -m evaluation.run_closed_loop --calibration-scenarios 1000 --test-scenarios 100`. Run the deterministic RecoveryGuard sensitivity sweep with `python -m evaluation.run_recovery_sensitivity`. Use separate, predeclared seeds for any new confirmatory run; held-out outcomes must not be used to select commitments.
