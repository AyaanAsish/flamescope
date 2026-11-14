#!/usr/bin/env bash
# Wait until a compose service container reports health "healthy" (CF-01: start db, wait healthy).
# The compose project name comes from PROJECT (default flamescope).
set -euo pipefail

readonly POLL_INTERVAL_SECONDS=2

usage() {
  echo "Usage: [PROJECT=flamescope] $(basename "$0") SERVICE TIMEOUT_SECONDS" >&2
  exit 2
}

container_id() {
  docker ps -aq \
    --filter "label=com.docker.compose.project=${PROJECT:-flamescope}" \
    --filter "label=com.docker.compose.service=$1" | head -n 1
}

health_status() {
  local id
  id="$(container_id "$1")"
  [[ -n "$id" ]] || { echo "missing"; return; }
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id"
}

# A container that is unhealthy or has exited will not recover on its own, so stop waiting early.
is_hopeless() {
  [[ "$1" == "unhealthy" || "$1" == "exited" ]]
}

main() {
  [[ $# -eq 2 ]] || usage
  local service="$1" timeout_seconds="$2" status
  local deadline=$((SECONDS + timeout_seconds))
  printf 'Waiting for service %s to be healthy ' "$service"
  status="$(health_status "$service")"
  until [[ "$status" == "healthy" ]]; do
    if is_hopeless "$status" || ((SECONDS >= deadline)); then
      printf '\nService %s is %s (timeout %ss)\n' "$service" "$status" "$timeout_seconds" >&2
      exit 1
    fi
    printf '.'
    sleep "$POLL_INTERVAL_SECONDS"
    status="$(health_status "$service")"
  done
  printf ' ok\n'
}

main "$@"
