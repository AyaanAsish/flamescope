#!/usr/bin/env bash
# Remove local build artefacts and caches for `make clean`, refusing any path outside the repository.
set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

usage() {
  echo "Usage: $(basename "$0") PATH..." >&2
  exit 2
}

is_inside_repository() {
  case "$1" in
    "" | . | ./ | *..* | "$REPO_ROOT" | "$REPO_ROOT/") return 1 ;;
    "$REPO_ROOT"/*) return 0 ;;
    /*) return 1 ;;
    *) return 0 ;;
  esac
}

remove_pycache() {
  find "$REPO_ROOT/src" "$REPO_ROOT/tests" -type d -name node_modules -prune \
    -o -type d -name __pycache__ -prune -exec rm -rf {} +
}

main() {
  [[ $# -gt 0 ]] || usage
  local path
  for path in "$@"; do
    is_inside_repository "$path" || { echo "Refusing to remove $path: outside $REPO_ROOT" >&2; exit 1; }
  done
  cd "$REPO_ROOT"
  for path in "$@"; do
    rm -rf -- "$path"
  done
  remove_pycache
}

main "$@"
