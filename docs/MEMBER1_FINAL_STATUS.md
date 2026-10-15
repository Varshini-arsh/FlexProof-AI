# FlexProof AI — Member 1 and local full-stack prototype status

## What is complete

The repository contains a standalone, deterministic research engine for FP-001: facility and battery physics, abstract flexible workloads, event dispatch, uncertainty, reliability-calibrated commitment, RAFC-V, RecoveryGuard, benchmark controllers, reproducible evaluation code, and schema-versioned results. The stable import interface is documented in `integration_guide.md`.

The local full-stack proof of concept connects the React frontend to FastAPI, calls the public Python engine, stores runs in SQLite, recomputes telemetry checks, shows saved history, and generates downloadable PDF reports. Docker Compose packages both services and stores SQLite in a named volume.

## Verified on 2026-10-15

- Branch: `feature/fullstack-poc-integration`; source checkout: `D:\FlexProof-AI`.
- Python suite: **82 passed** with `.\.venv\Scripts\python.exe -m pytest -q`. One Starlette/httpx deprecation warning is emitted by the installed test-client dependency.
- Frontend: `npm run lint` passed; `npm run build` passed. The production bundle has a 609 kB minified JavaScript chunk, which Vite flags for future code splitting.
- Backend and frontend containers reported healthy; backend health, frontend page, and frontend API proxy returned HTTP 200.
- A fresh Docker API request using RAFC-V completed, selected 4.9 MW, persisted to history, passed 42 of 42 arithmetic verification checks, and generated a 31,748-byte PDF. Run ID: `FP001-POSTMOVE-E2E-rolling-796daa922f03-41122c0238`.
- Docker's live WSL disk image is at `D:\DockerData\DockerDesktopWSL\disk\docker_data.vhdx`; the former C: image path no longer exists. Compose services now use `restart: unless-stopped` and the frontend has a container health check.

The fresh run reported 98.5% reliability over 1,000 calibration scenarios and a 95% Wilson lower bound of 96.77%. These are simulated calibration statistics. They are not held-out validation, measured facility performance, or utility certification. The API correctly reports `certification: false`.

## Research evaluation

The corrected 5,000-scenario held-out comparison, calibration split, seed ranges, confidence intervals, paired tests, failure categories, and sensitivity results are documented in `RESULTS_AND_LIMITATIONS.md`. Under those assumptions rolling RAFC-V matched rolling risk-aware MPC; the experiments do not show an incremental benefit for RAFC-V over that fair baseline. The previously unfair fixed-horizon result is withdrawn.

The raw closed-loop 5,000-scenario CSV/JSON files are not present in this checkout. `results/` experiment outputs are ignored by Git; rerun the documented command to regenerate the files. The checked-in four-controller comparison artifacts are analytical scenario-pass summaries, not a replacement for closed-loop results.

## Scope boundary

This is a working local research proof of concept, not a production deployment. Facility values and disturbance distributions remain assumptions. The prototype has no user accounts, access control, multi-user isolation, production database, facility telemetry integration, or operational security review. It must not be described as facility or utility certification.

## Git state

This working branch is `feature/fullstack-poc-integration`, based on the existing simulation and integration work. Review `git status` before committing or publishing. Do not force-push; generated datasets and local databases are excluded from source control.
