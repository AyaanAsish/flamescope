# Prompt 04 - Dockerfiles, Compose and the optional Helm chart

Create the container build and runtime definition for FlameScope on macOS with Docker.

## Contract

1. Read `docs/architecture/11-deployment-and-operations.md` fully, then documents 02 (sections 4 and 5), 06 (section 4), 09 (CF-01, CF-13) and 12 (section 2, files `test_01_build.py` and `test_02_deploy.py`, which will verify your work).
2. Names are contracts: file paths, service names, image tags, compose project name, volume names, ports, environment variables and health checks come from document 11 verbatim.
3. Scope: `deploy/docker/**`, `deploy/helm/flamescope/**`, `.dockerignore`. Do not create the Makefile (prompt 05). Do not change application code except to fix a defect that blocks a container from starting; report any such fix.
4. Conflict procedure: record in `docs/architecture/DESIGN-CONFLICTS.md`, take the conservative reading, report.
5. No state-changing git commands. No attribution in any file.

## Files to create

### `deploy/docker/Dockerfile.api`
- Multi-stage on `python:3.12-slim`. Builder stage installs the project into a virtual environment from `pyproject.toml` with `src/common`, `src/agents`, `src/api`. Final stage copies the virtual environment and `src/data`, sets `DATA_DIR=/app/src/data`, runs as non-root uid 10001, exposes 8000.
- `HEALTHCHECK` calling `/api/v1/health` using Python's standard library (no curl in the image).
- Command: `uvicorn flamescope_api.main:create_app --factory --host 0.0.0.0 --port 8000`.

### `deploy/docker/Dockerfile.ingest`
- Same base and pattern, packages `src/common`, `src/agents`, `src/ingest`, plus `src/data`.
- Entrypoint script `deploy/docker/ingest-entrypoint.sh`: `set -euo pipefail`; run `flamescope-ingest migrate`; then `flamescope-ingest ${INGEST_COMMAND:-seed}` (allow arguments to override). Non-root uid 10001; `/data/raw` writable by that user.

### `deploy/docker/Dockerfile.ui`
- Multi-stage on `node:20-alpine`: dependencies (`npm ci`), build (`next build` with standalone output), runtime (copy `.next/standalone`, `.next/static`, `public`). Non-root user. Port 3000. `HEALTHCHECK` using Node's standard library to request `/`.
- `API_INTERNAL_URL` must be honoured at runtime by the rewrite; if Next.js needs it at build time, pass a build argument with default `http://api:8000` and document it in a comment.

### `.dockerignore` (repository root)
Exclude `.git`, `.venv`, `node_modules`, `.next`, `tests`, `docs`, `prompts`, `.claude`, `CLAUDE.md`, caches, `.env`.

### `deploy/docker/compose.yaml`
Exactly as document 11 section 2: services `db`, `ingest` (profile `job`), `api`, `ui`; `name: flamescope`; build contexts at the repository root; image tags `flamescope-api:local`, `flamescope-ingest:local`, `flamescope-ui:local`; health checks; `depends_on` with `service_healthy`; volumes `flamescope_pgdata` and `flamescope_raw`; `db` bound to `127.0.0.1`; ports from `API_PORT`, `UI_PORT`, `DB_PORT` with defaults; environment from `.env` with safe defaults so the stack starts in mock mode with no `.env` edits.

### Image requirements (verified by tests)
- Build on both Apple Silicon and Intel Macs with no platform pin.
- Final images contain no compilers or build caches; Python images use `--no-cache-dir`; layers ordered so dependency layers cache when only source changes.
- Run as non-root. Read-only root filesystem compatible where practical (`/tmp` writable).
- Labels: `org.opencontainers.image.title`, `.description`, `.source` (leave source URL as a build argument), `.version`.

### `deploy/helm/flamescope/` (optional path, document 11 section 6)
`Chart.yaml`, `values.yaml`, templates for: `api` Deployment and Service, `ui` Deployment and Service, `db` StatefulSet, Service and PVC, `ingest` Job as a post-install and post-upgrade hook, `raw` PVC, ConfigMap, Secret, Ingress, OpenShift Route guarded by `route.enabled`, NetworkPolicy, `_helpers.tpl`, `NOTES.txt`. Probes match the compose health checks. Security contexts compatible with the OpenShift restricted SCC (no fixed UID requirement, `runAsNonRoot: true`, drop all capabilities). `values.yaml` keys mirror document 11 section 3.

## Verify (run these, fix until clean)

1. `docker compose -p flamescope -f deploy/docker/compose.yaml config` validates.
2. Build all three images.
3. Start `db`; run the ingest job (`docker compose ... run --rm ingest`); it exits 0 and reports seeded investigations.
4. Start `api` and `ui`; wait until healthy. `GET http://localhost:8000/api/v1/ready` returns 200; `GET http://localhost:3000/` returns 200; `GET http://localhost:3000/api/v1/health` returns 200 through the rewrite.
5. Confirm each container's user is non-root and image architecture matches the host.
6. `docker compose ... down -v --remove-orphans` leaves no `flamescope` containers, networks or volumes.
7. `helm lint deploy/helm/flamescope` and `helm template` succeed if Helm is installed; otherwise say it was not verified.

## Report

Files created, image sizes, verification results for each step above, any application fixes made, any conflicts recorded, and anything not verified on this machine.
