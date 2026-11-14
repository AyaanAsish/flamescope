# Prompt 05 - Makefile: build, deploy and undeploy the whole stack

Create the single entry point for building, deploying, testing and undeploying FlameScope on macOS using Python and Docker.

## Contract

1. Read `docs/architecture/11-deployment-and-operations.md` (section 4 is the binding list of targets), then document 09 (CF-01 and CF-13) and document 12 (how tests call the Makefile).
2. Target names, variable names, the compose invocation and the bring-up order come from document 11 verbatim. Do not add, rename or drop targets without the conflict procedure (`docs/architecture/DESIGN-CONFLICTS.md`).
3. Scope: `Makefile` at the repository root and helper scripts under `deploy/scripts/`. Do not modify Dockerfiles, compose or application code except to fix a defect that blocks a target; report any such fix.
4. No state-changing git commands. No attribution in any file.

## Requirements

### Portability
- Must work with the stock macOS GNU Make 3.81 and bash 3.2: no `.ONESHELL`, no `$(file ...)`, no `&:` grouped targets, no associative arrays, no `mapfile`. Recipes use tabs.
- `SHELL := /bin/bash`; `.DEFAULT_GOAL := help`; every target `.PHONY`.
- Works on Apple Silicon and Intel; with Docker Desktop or Colima. Detect `docker compose` v2 and fail with a clear message if missing.
- Also runs on Linux unchanged (the `open` target falls back to printing the URL).

### Variables (overridable from the environment or command line)
```
PROJECT        ?= flamescope
COMPOSE_FILE   ?= deploy/docker/compose.yaml
ENV_FILE       ?= .env
COMPOSE        := docker compose -p $(PROJECT) -f $(COMPOSE_FILE) --env-file $(ENV_FILE)
PYTHON         ?= python3.12
VENV           ?= .venv
UI_DIR         ?= src/ui
API_PORT       ?= 8000
UI_PORT        ?= 3000
WAIT_TIMEOUT   ?= 120
SERVICE        ?=
KEEP_STACK     ?=
```

### Targets
Implement every target in document 11 section 4 with exactly that behaviour: `help`, `doctor`, `env`, `venv`, `ui-install`, `ollama-pull`, `lint`, `fmt`, `build`, `deploy`, `ingest-seed`, `ingest-harvest`, `status`, `logs`, `restart`, `undeploy`, `clean`, `test-unit`, `test-integration`, `test-e2e`, `test`, `all`, `open`, `helm-template`, `helm-deploy`, `helm-undeploy`.

Details:
- `help`: self-documenting from `## ` comments after each target name, grouped under headings (Setup, Build and deploy, Operate, Test, Kubernetes).
- `doctor`: checks Docker daemon, compose v2, Python 3.12, Node, that `API_PORT`, `UI_PORT` are free or already held by this project's containers, and, when `LLM_PROVIDER=ollama`, that Ollama answers at `OLLAMA_BASE_URL` (via `localhost`) with `LLM_MODEL` and `EMBED_MODEL` pulled; prints versions and a pass or fail line per check; non-zero exit on failure.
- `env`: copies `.env.example` to `.env` only if `.env` is missing.
- `deploy`: depends on `env`; follows CF-01 exactly - start `db`, wait healthy, run the ingest job (`$(COMPOSE) --profile job run --rm ingest`), start `api` and `ui`, wait for `http://localhost:$(API_PORT)/api/v1/ready` and `http://localhost:$(UI_PORT)/`, then print the UI, API docs and Architecture page URLs. It builds images if they are missing. Any failure prints the last 50 log lines of the failing service and exits non-zero.
- `ingest-harvest`: refuses to run when `LLM_PROVIDER=mock` with a clear message.
- `undeploy`: `$(COMPOSE) --profile job down -v --remove-orphans`; idempotent (succeeds when nothing is running).
- `clean`: `undeploy`, remove the three `:local` images, `$(VENV)`, `$(UI_DIR)/node_modules`, `$(UI_DIR)/.next`, Python and test caches. Never touches files outside the repository.
- `test-unit`: creates the virtual environment if missing; runs `pytest tests/unit` and `npm test` in the UI directory.
- `test-integration`: runs `pytest tests/integration` (the suite itself builds and deploys; see document 12 section 2).
- `test-e2e`: ensures Playwright browsers are installed (`python -m playwright install chromium`), runs `pytest tests/e2e`.
- `test`: unit, integration, end-to-end in order; honours `KEEP_STACK=1`.
- `all`: `build`, `deploy`, `test`.
- Helm targets: release name and namespace variables; print a clear message if Helm is not installed.

### Helper scripts in `deploy/scripts/`
- `wait-for.sh URL TIMEOUT_SECONDS`: polls with `curl -fsS`, prints progress dots, exits non-zero on timeout. Bash 3.2 compatible.
- `wait-healthy.sh SERVICE TIMEOUT_SECONDS`: polls `docker inspect` health status of the compose service.
- `check-port.sh PORT`: reports whether a port is free using `lsof` (macOS) with an `ss` fallback (Linux).
All scripts: `set -euo pipefail`, executable bit set, usage message.

### Output quality
Quiet by default with clear step banners (`==> Building images`); `V=1` shows full commands. Exit codes are reliable so tests can assert on them.

## Verify (run on this machine)

1. `make help` lists every documented target.
2. `make doctor` passes.
3. From a clean state: `make build`, `make deploy`, `make status`, `make ingest-seed` (idempotent), `make restart`, `make logs SERVICE=api` (interrupt after a few lines), `make undeploy`.
4. `make deploy` twice in a row succeeds (idempotent bring-up).
5. `make undeploy` twice in a row succeeds; afterwards no `flamescope` containers, networks or volumes exist.
6. Check with `make -n deploy` that no GNU Make 4-only features are used; if `/usr/bin/make` is 3.81, run with it.

## Report

The target list with one line each, verification results per step, any fixes made outside the Makefile, conflicts recorded, and anything not verified here.
