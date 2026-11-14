#!/usr/bin/env bash
# Host prerequisite checks for `make doctor` (document 11 section 4): one PASS or FAIL line per check,
# non-zero exit when any check fails. Settings come from the environment (the Makefile passes them).
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly REQUIRED_PYTHON="3.12"
readonly MIN_NODE_MAJOR=20

failures=0

usage() {
  echo "Usage: PROJECT=... PYTHON=... API_PORT=... UI_PORT=... DB_PORT=... LLM_PROVIDER=..." \
    "[OLLAMA_BASE_URL=... LLM_MODEL=... EMBED_MODEL=...] $(basename "$0")" >&2
  exit 2
}

run_check() {
  local name="$1" detail
  shift
  if detail="$("$@" 2>&1)"; then
    printf 'PASS  %-12s %s\n' "$name" "$detail"
    return
  fi
  printf 'FAIL  %-12s %s\n' "$name" "$detail"
  failures=$((failures + 1))
}

check_docker() {
  docker info --format 'daemon {{.ServerVersion}} ({{.Architecture}})' 2>/dev/null \
    || { echo "daemon not reachable; start Docker Desktop or 'colima start'"; return 1; }
}

check_compose() {
  docker compose version --short 2>/dev/null \
    || { echo "docker compose v2 not found; install Docker Desktop or the compose plugin"; return 1; }
}

check_python() {
  local version
  version="$("$PYTHON" -c 'import platform; print(platform.python_version())' 2>/dev/null)" \
    || { echo "$PYTHON not found; install Python $REQUIRED_PYTHON or set PYTHON=/path/to/python$REQUIRED_PYTHON"; return 1; }
  [[ "$version" == "$REQUIRED_PYTHON".* ]] \
    || { echo "$PYTHON is $version; Python $REQUIRED_PYTHON required"; return 1; }
  echo "$PYTHON $version"
}

check_node() {
  local version
  version="$(node --version 2>/dev/null)" || { echo "node not found; install Node $MIN_NODE_MAJOR or newer"; return 1; }
  local major="${version#v}"
  major="${major%%.*}"
  ((major >= MIN_NODE_MAJOR)) || { echo "node $version; $MIN_NODE_MAJOR or newer required"; return 1; }
  echo "node $version"
}

is_held_by_project() {
  docker ps --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Ports}}' 2>/dev/null \
    | grep -q ":$1->"
}

check_port() {
  "$SCRIPT_DIR/check-port.sh" "$1" >/dev/null && { echo "port $1 free"; return; }
  is_held_by_project "$1" || { echo "port $1 in use by another process (lsof -nP -iTCP:$1)"; return 1; }
  echo "port $1 held by the $PROJECT stack"
}

check_llm() {
  if [[ "$LLM_PROVIDER" != "ollama" ]]; then
    echo "LLM_PROVIDER=$LLM_PROVIDER; Ollama not required"
    return
  fi
  "$SCRIPT_DIR/check-ollama.sh"
}

main() {
  [[ -n "${PROJECT:-}" && -n "${PYTHON:-}" && -n "${LLM_PROVIDER:-}" ]] || usage
  run_check docker check_docker
  run_check compose check_compose
  run_check python check_python
  run_check node check_node
  run_check api-port check_port "$API_PORT"
  run_check ui-port check_port "$UI_PORT"
  run_check db-port check_port "$DB_PORT"
  run_check ollama check_llm
  ((failures == 0)) || { echo "$failures check(s) failed" >&2; exit 1; }
  echo "All checks passed"
}

main "$@"
