#!/usr/bin/env bash
# Verify that undeploy left no containers, networks or volumes of the compose project behind (CF-13).
# The compose project name comes from PROJECT (default flamescope).
set -euo pipefail

usage() {
  echo "Usage: [PROJECT=flamescope] $(basename "$0")" >&2
  exit 2
}

leftovers() {
  local project="$1"
  docker ps -a --filter "name=$project" --format 'container {{.Names}}'
  docker network ls --filter "name=$project" --format 'network {{.Name}}'
  docker volume ls --filter "name=$project" --format 'volume {{.Name}}'
}

main() {
  [[ $# -eq 0 ]] || usage
  local project="${PROJECT:-flamescope}" remaining
  remaining="$(leftovers "$project")"
  if [[ -n "$remaining" ]]; then
    printf 'Undeploy left resources of %s behind:\n%s\n' "$project" "$remaining" >&2
    exit 1
  fi
  echo "No $project containers, networks or volumes remain"
}

main "$@"
