# FlameScope: build, deploy, test and undeploy on macOS (document 11 section 4; call flows CF-01 and CF-13).
# Compatible with the stock macOS GNU Make 3.81 and bash 3.2. `V=1` shows the full commands.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PROJECT        ?= flamescope
COMPOSE_FILE   ?= deploy/docker/compose.yaml
ENV_FILE       ?= .env
COMPOSE        := docker compose -p $(PROJECT) -f $(COMPOSE_FILE) --env-file $(ENV_FILE)
PYTHON         ?= python3.12
VENV           ?= .venv
UI_DIR         ?= src/ui
WAIT_TIMEOUT   ?= 120
SERVICE        ?=
KEEP_STACK     ?=
HELM_RELEASE   ?= flamescope
HELM_NAMESPACE ?= flamescope
HELM_CHART     ?= deploy/helm/flamescope

# Settings shared with compose: the environment wins, then $(ENV_FILE), then the document 11 section 3 default.
# Recursive (=) so the value is read after `env` has created $(ENV_FILE).
env_value = $(or $(shell sed -n 's/^$(1)=//p' $(ENV_FILE) 2>/dev/null | tail -n 1),$(2))
API_PORT        ?= $(call env_value,API_PORT,8000)
UI_PORT         ?= $(call env_value,UI_PORT,3000)
DB_PORT         ?= $(call env_value,DB_PORT,5432)
LLM_PROVIDER    ?= $(call env_value,LLM_PROVIDER,mock)
OLLAMA_BASE_URL ?= $(call env_value,OLLAMA_BASE_URL,http://host.docker.internal:11434)
LLM_MODEL       ?= $(call env_value,LLM_MODEL,qwen2.5:0.5b)
EMBED_MODEL     ?= $(call env_value,EMBED_MODEL,nomic-embed-text)

export KEEP_STACK

COMPOSE_JOB  = $(COMPOSE) --profile job
IMAGES       := flamescope-api:local flamescope-ingest:local flamescope-ui:local
VENV_PYTHON  = $(VENV)/bin/python
SCRIPTS      := deploy/scripts
REPORTS_DIR  := tests/reports
API_URL      = http://localhost:$(API_PORT)/api/v1
UI_URL       = http://localhost:$(UI_PORT)
OLLAMA_ENV   = OLLAMA_BASE_URL=$(OLLAMA_BASE_URL) LLM_MODEL=$(LLM_MODEL) EMBED_MODEL=$(EMBED_MODEL)
SUBMAKE      = $(MAKE) --no-print-directory

comma := ,

ifeq ($(V),1)
Q :=
else
Q := @
endif

banner = @printf '==> %s\n' "$(1)"
# On failure: show the last 50 log lines of the failing service(s) and the `make logs` hint (CF-01).
or_logs = || { $(COMPOSE_JOB) logs --no-color --tail 50 $(1); echo "Failed: $(1); see make logs SERVICE=$(word 1,$(1))" >&2; exit 1; }
require_ollama = $(if $(filter ollama,$(LLM_PROVIDER)),$(OLLAMA_ENV) $(SCRIPTS)/check-ollama.sh,echo "LLM_PROVIDER=$(LLM_PROVIDER): Ollama not required")
require_tool = command -v $(1) >/dev/null 2>&1 || { echo "$(1) is not installed; $(2)" >&2; exit 1; }
ensure_venv = test -x $(VENV_PYTHON) || $(SUBMAKE) venv
ensure_ui_modules = test -d $(UI_DIR)/node_modules || $(SUBMAKE) ui-install

.PHONY: help doctor ollama-pull env venv ui-install
.PHONY: build deploy ingest-seed ingest-harvest undeploy
.PHONY: status logs restart clean open
.PHONY: lint fmt test-unit test-integration test-e2e test all
.PHONY: helm-template helm-deploy helm-undeploy

##@ Setup

help: ## List targets with descriptions (default)
	@awk 'BEGIN {FS = ":.*## "} /^##@ / {printf "\n%s\n", substr($$0, 5)} /^[a-z][a-zA-Z0-9_-]*:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(firstword $(MAKEFILE_LIST))

doctor: ## Check docker, compose, python3.12, node, free ports and Ollama with its models
	$(call banner,Checking host prerequisites)
	$(Q)PROJECT=$(PROJECT) PYTHON=$(PYTHON) API_PORT=$(API_PORT) UI_PORT=$(UI_PORT) DB_PORT=$(DB_PORT) \
		LLM_PROVIDER=$(LLM_PROVIDER) $(OLLAMA_ENV) $(SCRIPTS)/doctor.sh

ollama-pull: ## Pull LLM_MODEL and EMBED_MODEL into Ollama on the host
	$(Q)$(call require_tool,ollama,install it from https://ollama.com/download)
	$(call banner,Pulling $(LLM_MODEL) and $(EMBED_MODEL))
	$(Q)ollama pull $(LLM_MODEL)
	$(Q)ollama pull $(EMBED_MODEL)

env: ## Create .env from .env.example if missing
	$(Q)test -f $(ENV_FILE) || { cp .env.example $(ENV_FILE) && echo "==> Created $(ENV_FILE) from .env.example"; }

venv: ## Create .venv and install -e ".[dev]"
	$(call banner,Preparing $(VENV))
	$(Q)test -x $(VENV_PYTHON) || $(PYTHON) -m venv $(VENV)
	$(Q)$(VENV_PYTHON) -m pip --version >/dev/null 2>&1 || $(VENV_PYTHON) -m ensurepip --upgrade >/dev/null
	$(Q)$(VENV_PYTHON) -m pip install --quiet --disable-pip-version-check -e ".[dev]"

ui-install: ## npm ci in src/ui
	$(call banner,Installing UI dependencies)
	$(Q)cd $(UI_DIR) && npm ci

##@ Build and deploy

build: env ## docker compose build for api, ingest and ui
	$(call banner,Building images)
	$(Q)$(COMPOSE_JOB) build api ingest ui

deploy: env ## Bring up db, ingest job (migrate + seed), api and ui; wait for readiness; print URLs
	$(call banner,Checking LLM provider $(LLM_PROVIDER))
	$(Q)$(require_ollama)
	$(Q)docker image inspect $(IMAGES) >/dev/null 2>&1 || $(SUBMAKE) build
	$(call banner,Starting db)
	$(Q)$(COMPOSE) up -d db $(call or_logs,db)
	$(Q)PROJECT=$(PROJECT) $(SCRIPTS)/wait-healthy.sh db $(WAIT_TIMEOUT) $(call or_logs,db)
	$(call banner,Running ingest job (migrate + seed))
	$(Q)$(COMPOSE_JOB) run --rm ingest || { echo "Failed: ingest; see the output above" >&2; exit 1; }
	$(call banner,Starting api and ui)
	$(Q)$(COMPOSE) up -d api ui $(call or_logs,api ui)
	$(Q)$(SCRIPTS)/wait-for.sh $(API_URL)/ready $(WAIT_TIMEOUT) $(call or_logs,api)
	$(Q)$(SCRIPTS)/wait-for.sh $(UI_URL)/ $(WAIT_TIMEOUT) $(call or_logs,ui)
	$(Q)PROJECT=$(PROJECT) $(SCRIPTS)/wait-healthy.sh ui $(WAIT_TIMEOUT) $(call or_logs,ui)
	@printf '==> FlameScope is up\n  UI:           %s\n  API docs:     %s\n  Architecture: %s\n' \
		"$(UI_URL)" "$(API_URL)/docs" "$(UI_URL)/architecture"

ingest-seed: env ## Re-run seed ingestion
	$(call banner,Running seed ingestion)
	$(Q)$(COMPOSE_JOB) run --rm ingest seed

ingest-harvest: env ## Run harvest ingestion (requires LLM_PROVIDER=ollama)
	$(Q)test "$(LLM_PROVIDER)" = ollama || { echo "ingest-harvest requires LLM_PROVIDER=ollama (now $(LLM_PROVIDER)); set it in $(ENV_FILE)" >&2; exit 1; }
	$(Q)$(require_ollama)
	$(call banner,Running harvest ingestion)
	$(Q)$(COMPOSE_JOB) run --rm ingest harvest

undeploy: env ## docker compose down -v --remove-orphans
	$(call banner,Removing containers$(comma) network and volumes)
	$(Q)$(COMPOSE_JOB) down -v --remove-orphans

##@ Operate

status: env ## docker compose ps plus /ready and /meta/stats summary
	$(Q)$(COMPOSE) ps
	@printf 'ready: '; curl -sS -m 5 -w ' (HTTP %{http_code})\n' $(API_URL)/ready
	@printf 'stats: '; curl -sS -m 5 -w ' (HTTP %{http_code})\n' $(API_URL)/meta/stats

logs: env ## Tail logs (SERVICE=api optional)
	$(Q)$(COMPOSE_JOB) logs -f --tail 100 $(SERVICE)

restart: env ## Restart api and ui (re-reads .env)
	$(call banner,Restarting api and ui)
	$(Q)$(COMPOSE) up -d --force-recreate api ui $(call or_logs,api ui)
	$(Q)$(SCRIPTS)/wait-for.sh $(API_URL)/ready $(WAIT_TIMEOUT) $(call or_logs,api)
	$(Q)$(SCRIPTS)/wait-for.sh $(UI_URL)/ $(WAIT_TIMEOUT) $(call or_logs,ui)

clean: undeploy ## undeploy plus remove local images, .venv, node_modules and caches
	$(call banner,Removing local images)
	$(Q)for image in $(IMAGES); do if docker image inspect $$image >/dev/null 2>&1; then docker image rm $$image; fi; done
	$(call banner,Removing $(VENV)$(comma) node_modules and caches)
	$(Q)$(SCRIPTS)/remove-local.sh $(VENV) $(UI_DIR)/node_modules $(UI_DIR)/.next $(UI_DIR)/coverage \
		$(UI_DIR)/tsconfig.tsbuildinfo .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov $(REPORTS_DIR) tests/e2e/artifacts

open: ## Open the UI in the browser
	$(Q)if [ "$$(uname)" = Darwin ]; then open $(UI_URL); else echo "Open $(UI_URL)"; fi

##@ Test

lint: ## ruff, mypy, xenon, eslint, tsc
	$(Q)$(ensure_venv)
	$(Q)$(ensure_ui_modules)
	$(call banner,ruff)
	$(Q)$(VENV)/bin/ruff check src tests
	$(call banner,mypy)
	$(Q)$(VENV)/bin/mypy src/common src/agents src/api src/ingest
	$(call banner,xenon)
	$(Q)$(VENV)/bin/xenon src --max-absolute B --max-modules A --max-average A -e "src/ui/node_modules/*"
	$(call banner,eslint)
	$(Q)cd $(UI_DIR) && npm run --silent lint
	$(call banner,tsc)
	$(Q)cd $(UI_DIR) && npm run --silent typecheck

fmt: ## ruff format, prettier
	$(Q)$(ensure_venv)
	$(Q)$(ensure_ui_modules)
	$(call banner,ruff format)
	$(Q)$(VENV)/bin/ruff format src tests
	$(call banner,prettier)
	$(Q)cd $(UI_DIR) && npx --no-install prettier --write --log-level warn .

test-unit: ## pytest tests/unit and npm test (Vitest); no Docker needed
	$(Q)$(ensure_venv)
	$(Q)$(ensure_ui_modules)
	$(call banner,pytest tests/unit)
	$(Q)$(VENV_PYTHON) -m pytest tests/unit -q --junitxml=$(REPORTS_DIR)/unit.xml --html=$(REPORTS_DIR)/unit.html --self-contained-html
	$(call banner,Vitest)
	$(Q)cd $(UI_DIR) && npm test --silent

test-integration: ## pytest tests/integration (builds, deploys, verifies APIs; leaves the stack running)
	$(Q)$(ensure_venv)
	$(call banner,pytest tests/integration)
	$(Q)$(VENV_PYTHON) -m pytest tests/integration --junitxml=$(REPORTS_DIR)/integration.xml --html=$(REPORTS_DIR)/integration.html --self-contained-html

test-e2e: ## pytest tests/e2e with Playwright against the running stack
	$(Q)$(ensure_venv)
	$(call banner,Installing Playwright Chromium)
	$(Q)$(VENV_PYTHON) -m playwright install chromium
	$(call banner,pytest tests/e2e)
	$(Q)$(VENV_PYTHON) -m pytest tests/e2e --junitxml=$(REPORTS_DIR)/e2e.xml --html=$(REPORTS_DIR)/e2e.html --self-contained-html

test: ## test-unit, test-integration, test-e2e, then undeploy verification (KEEP_STACK=1 keeps the stack)
	$(Q)$(SUBMAKE) test-unit
	$(Q)$(SUBMAKE) test-integration
	$(Q)$(SUBMAKE) test-e2e
	$(Q)if [ "$(KEEP_STACK)" = 1 ]; then echo "==> KEEP_STACK=1: stack left running"; else $(SUBMAKE) undeploy && PROJECT=$(PROJECT) $(SCRIPTS)/check-undeployed.sh; fi

all: ## build, deploy, test
	$(Q)$(SUBMAKE) build
	$(Q)$(SUBMAKE) deploy
	$(Q)$(SUBMAKE) test

##@ Kubernetes

helm-template: ## Render the optional Helm chart
	$(Q)$(call require_tool,helm,install it (brew install helm) to use the optional Kubernetes path)
	$(Q)helm template $(HELM_RELEASE) $(HELM_CHART) --namespace $(HELM_NAMESPACE)

helm-deploy: ## Install or upgrade the Helm release
	$(Q)$(call require_tool,helm,install it (brew install helm) to use the optional Kubernetes path)
	$(call banner,Deploying Helm release $(HELM_RELEASE) to namespace $(HELM_NAMESPACE))
	$(Q)helm upgrade --install $(HELM_RELEASE) $(HELM_CHART) --namespace $(HELM_NAMESPACE) --create-namespace --wait

helm-undeploy: ## Uninstall the Helm release
	$(Q)$(call require_tool,helm,install it (brew install helm) to use the optional Kubernetes path)
	$(call banner,Removing Helm release $(HELM_RELEASE))
	$(Q)helm uninstall $(HELM_RELEASE) --namespace $(HELM_NAMESPACE)
