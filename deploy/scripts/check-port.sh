#!/usr/bin/env bash
# Report whether a TCP port on the host is free: exit 0 when free, 1 when something listens on it.
# lsof on macOS, ss on Linux.
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") PORT" >&2
  exit 2
}

is_listening() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return
  fi
  ss -ltnH "sport = :$port" 2>/dev/null | grep -q .
}

main() {
  [[ $# -eq 1 && "$1" =~ ^[0-9]+$ ]] || usage
  if is_listening "$1"; then
    echo "port $1 in use"
    exit 1
  fi
  echo "port $1 free"
}

main "$@"
