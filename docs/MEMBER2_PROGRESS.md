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

RecoveryGuard UI, independent verification, evidence exports, PostgreSQL migrations, and the raw-benchmark dashboard remain subsequent milestones. The source Member 1 branches have not been modified.
