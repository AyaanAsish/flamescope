#!/usr/bin/env bash
# Poll a URL until it answers with a 2xx status or the timeout expires (document 11 section 4).
set -euo pipefail

readonly POLL_INTERVAL_SECONDS=2
readonly REQUEST_TIMEOUT_SECONDS=5

usage() {
  echo "Usage: $(basename "$0") URL TIMEOUT_SECONDS" >&2
  exit 2
}

is_answering() {
  curl -fsS -o /dev/null -m "$REQUEST_TIMEOUT_SECONDS" "$1" 2>/dev/null
}

main() {
  [[ $# -eq 2 ]] || usage
  local url="$1" timeout_seconds="$2"
  local deadline=$((SECONDS + timeout_seconds))
  printf 'Waiting for %s ' "$url"
  until is_answering "$url"; do
    if ((SECONDS >= deadline)); then
      printf '\n%s did not answer within %ss\n' "$url" "$timeout_seconds" >&2
      exit 1
    fi
    printf '.'
    sleep "$POLL_INTERVAL_SECONDS"
  done
  printf ' ok\n'
}

main "$@"
