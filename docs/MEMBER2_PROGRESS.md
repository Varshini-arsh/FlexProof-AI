# Member 2 integration progress

Working branch: `feature/fullstack-verification`. The supplied Shara checkout path was absent on this host, so the branch was fetched into an isolated worktree at `D:\FlexProof-AI-Member2`.

## ZIP review and nominal React checkpoint — verified 2026-10-15

The archive `FlexProof-AI.zip` supplied a nominal FastAPI run endpoint, an engine adapter, six result cards, and three telemetry charts. Only five source files differed substantively from the remote Member 2 branch. Git metadata, virtual environments, installed dependencies, generated builds, and package metadata from the archive were excluded.

Retained the Member 2 layout and result UI, and corrected scenario ID, random seed, and reliability-target propagation; five-minute interval validation; engine-health reporting; configurable API URL; infeasible result explanations; and chart labels. Event chart animations are disabled so evidence screenshots contain complete curves. The nominal model releases a full workload cohort at event start, so its backlog chart shows remaining cohort work.

Validation:

- Python 3.12.10: `python -m pytest -q` — **65 passed**; one installed Starlette/httpx deprecation warning.
- Frontend: `npm run lint` and `npm run build` — passed. Vite reports a 606 kB minified JavaScript chunk.
- Playwright: `npm run test:e2e` — **4 passed**, using installed Edge with `PLAYWRIGHT_CHANNEL=msedge` and `FLEXPROOF_PYTHON` pointing to the available Python 3.12 environment.
- Browser tests click Run Simulation against a real FastAPI process, verify the six cards and three charts, and check infeasible, reserve-SoC, and connection-failure states.
- Nominal FP-001: twelve intervals, 15 MW import, 5 MW reduction, 20.2632% final SoC, and 3.6 MWh remaining workload. These are deterministic model outputs; reliability and recovery are not evaluated by this nominal endpoint.

## Grid Event Monitor — verified

The monitor now uses the latest selected run, retains that run when navigating back to the planner, and displays requested/accepted/delivered reduction, baseline/import charts, twelve interval rows, battery discharge/SoC, flexible computing, backlog, delivery checks, and reported violations. Delivered MW is independently recomputed for display as baseline minus import. Empty evidence and missing measurements are explicit. Browser regression tests validate the table against the actual API response and preserve planner results across navigation. Frontend lint/build and all four browser tests passed after this milestone; the screenshots were visually inspected.

## Risk-aware integration — verified

Imported the unchanged Member 1 research snapshot at `b5712c2` onto this Member 2 branch, with provenance in `ENGINE_SOURCE.md`. API requests can select the supported controllers, seed, calibration size, and recovery import ceiling. `POST /api/commitments/evaluate` returns the requested/recommended MW, calibration estimate, Wilson interval, simultaneous search-adjusted lower bound, candidate evidence, source/controller version, explanation, and explicit unavailable held-out status. The planner displays these distinctions and can execute RAFC-V. Shorter events retain a 240-minute recovery horizon with corresponding absolute deadlines.

Validation: **93 Python tests passed**. Frontend lint/build passed. **Six browser tests passed**, including actual RAFC-V API execution and insufficient calibration shown as unconfirmed. A controller-select accessible-label defect found by the browser test was corrected before passing. The JavaScript bundle remains about 615 kB minified.

## RecoveryGuard — verified

All supported controllers now execute through `flexproof.engine.run_scenario`, which returns the existing joint RecoveryGuard plan. The UI displays the recovery timeline, battery charging, restored compute, shared import ceiling, SoC/backlog, interval evidence, target achievement, violations, and failure explanation. It warns when a recovery plan is conditional on an unsuccessful event. The FP-001 feasible case returned 48 intervals, final SoC at least 35%, and cleared backlog; a nominal event with only a 17 MW recovery ceiling correctly returned infeasible recovery despite successful event delivery.

Validation: **95 Python tests passed** in both the previously available environment and the new dedicated `D:\FlexProof-AI-Member2\.venv` (Python 3.12.10). `pip check` found no broken requirements. **Seven browser tests passed**, frontend lint/build passed, and the RecoveryGuard screenshot was visually inspected. Repeated-run tests compare deterministic physical telemetry while excluding measured solver wall-clock time.

## Independent verification, reports, and benchmark dashboard — verified

Added a separate operational verifier with pass/fail/insufficient-evidence statuses, named arithmetic checks, and content hashes. It rechecks event power balance and delivery, battery SoC and limits, aggregate deferred work and deadlines, recovery shared-capacity limits and targets; it does not trust the simulator's success flag. FastAPI exposes `/api/evidence/verify` and attaches independent checks to each run. The Verification Portal displays checks, limits, hashes, and re-verification results.

Evidence exports now provide a JSON bundle validated by `contracts/evidence.schema.json`, event/recovery interval CSV, and a two-page PDF report. The app benchmark view consumes a checksummed, tracked summary derived from the reproduced raw outputs and reports missing or tampered raw artifacts instead of inventing data.

The 1,000 calibration / 5,000 held-out run completed with seeds 100000 and 400000, respectively. All raw row counts match the aggregate JSON. Both rolling methods selected 4.9 MW and achieved 4,888/5,000 successes (97.76%, Wilson 95% CI 97.31–98.13%); fixed-horizon achieved 4,448/5,000 (88.96%). Rolling RAFC-V and rolling risk-aware MPC had no paired outcome differences (McNemar p=1.0); no RAFC-V incremental benefit is claimed. Detailed results and limitations are in `RESULTS_AND_LIMITATIONS.md`.

Validation at this checkpoint: 124 Python tests previously passed before exports; focused export, verifier, and benchmark-integrity tests then passed 11/11; all 8 browser tests passed, including JSON/CSV/PDF downloads and benchmark display. Frontend lint/build passed. PostgreSQL persistence/migrations and Docker Compose remain to be implemented and verified. The Member 1 source branch was not modified.

## PostgreSQL, container deployment, and final validation � verified 2026-10-16

Completed normalized PostgreSQL persistence and Alembic migrations for scenario configurations, simulation runs, event/recovery telemetry, verification records, and report metadata. The local developer default remains SQLite. Docker Compose runs PostgreSQL, FastAPI, and the React/Nginx frontend on ports 5433, 8011, and 8081. Health checks report database connectivity; API restart testing confirmed stored runs and telemetry remain available.

The React application now includes run history, independent verification, benchmark comparison, and JSON/CSV/PDF evidence downloads. Live Docker browser testing exercised feasible and infeasible recovery outcomes, evidence downloads, benchmark display, and database-backed history. The persistence API assigns unique IDs per execution while retaining the deterministic engine run ID; repeated identical requests produce two history records with identical physical telemetry.

Final validation: **135 Python tests passed** (one Starlette/httpx deprecation warning); **9 Playwright end-to-end tests passed** against Docker; frontend lint/build passed; `docker compose config` passed; Docker health and PostgreSQL restart persistence passed. The Member 1 research source and branch remain unchanged.

The local Docker demonstration is available at `http://localhost:8081`; API health is at `http://localhost:8011/api/health`. No changes have been pushed. The raw 5,000-scenario held-out data remains a local ignored artifact; its checksummed compact summary and comparison plot are tracked. Statistical results and known limitations are recorded in `RESULTS_AND_LIMITATIONS.md`.
