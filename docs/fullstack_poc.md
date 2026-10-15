# Full stack proof of concept

## Run locally

Use Python 3.12. From the repository root, install the API and development extras and start FastAPI:

```powershell
python -m pip install -e ".[api,dev]"
python -m uvicorn backend.app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`; API documentation is served at `http://127.0.0.1:8000/docs`.

## End-to-end flow

1. The planner validates a request against typed API fields and the FP-001 scenario contract.
2. The API loads the configured FP-001 assumptions, applies the requested event, SoC, seed, reliability target, and controller, then calls `flexproof.engine.run_scenario`.
3. The engine returns its schema 1.0.0 JSON-compatible result. The API assigns a unique request run ID while retaining the deterministic engine run ID.
4. An independent checker recomputes event power balance, delivered reduction, battery energy transitions, interval count, and recovery shared-import limits from telemetry. It reports arithmetic consistency only, not certification.
5. The result, request, scenario configuration, and verification record are stored in SQLite. The UI shows the result, and run history can retrieve it later.
6. A PDF endpoint produces a downloadable summary using the persisted record.

The React development server calls the API at `http://127.0.0.1:8000/api` by default. Set `VITE_API_BASE_URL` to change it. API CORS origins are controlled by comma-separated `FLEXPROOF_CORS_ORIGINS`. The local database path is controlled by `FLEXPROOF_DB_PATH`.

## Docker

From the project root:

```powershell
docker compose up --build
```

The UI is available at `http://localhost:8080` and the API at `http://localhost:8000`. Docker Compose keeps SQLite data in the named `flexproof-data` volume. To stop services, use `docker compose down`; add `-v` only if you intend to delete the persisted prototype database.

Both Compose services use `restart: unless-stopped`; the frontend also has a health check. After Docker Desktop starts, check `docker compose ps` and open `http://localhost:8080`. If the services were explicitly stopped, run `docker compose up -d` from the repository root.

## End-to-end demo checklist

1. Open **Commitment Planner** in the navigation.
2. Keep the FP-001 values (5 MW requested, 60 minutes, 95% target, 35% initial SoC, seed, and 1,000 calibration scenarios), or change a supported input.
3. Choose a controller and click **Validate and Run**. RAFC-V uses calibration scenarios; its evidence is shown as calibration evidence and is not held-out validation.
4. Review the accepted commitment, event chart, SoC/backlog chart, recovery status, and independent arithmetic-check summary.
5. Open **Run History**, select the saved run, and download its PDF report. Refreshing or reopening the page retrieves the same persisted record through the API.

Useful direct checks are `GET /api/health`, `GET /api/runs`, `GET /api/runs/{run_id}/verification`, and `GET /api/runs/{run_id}/report.pdf`. `http://localhost:8000/docs` exposes the OpenAPI reference.

## Verified Docker run

On 2026-10-15, a fresh RAFC-V request was run through the Docker API after Docker's WSL disk was moved to D:. The API returned a persisted 4.9 MW commitment, 42/42 telemetry checks passed, the run appeared in history, and its PDF endpoint returned HTTP 200. Run ID: `FP001-POSTMOVE-E2E-rolling-796daa922f03-41122c0238`. The 98.5% reliability estimate and 96.77% lower confidence bound use 1,000 calibration scenarios; they are not held-out or certification results.

## Scope and limits

The API stores local prototype data without user accounts or access control and is intended for local development/demo use. RAFC-V evidence from a run is calibration evidence, not held-out validation. The independent checker uses the same returned telemetry data and arithmetic definitions; it is not a separate simulator or a utility certification process. Forecasting, multi-user permissions, production database operations, and facility integrations are not included.
