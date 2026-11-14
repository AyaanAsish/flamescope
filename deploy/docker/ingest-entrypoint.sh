#!/usr/bin/env bash
# Ingest job entrypoint (document 06 section 4): migrate, then the requested ingest command.
# Arguments override INGEST_COMMAND, e.g. `compose run --rm ingest seed --only ACR`.
set -euo pipefail

flamescope-ingest migrate

if [[ $# -gt 0 ]]; then
  exec flamescope-ingest "$@"
fi

# INGEST_COMMAND may carry options ("seed --only ACR"), so split it into words.
read -r -a ingest_args <<< "${INGEST_COMMAND:-seed}"
exec flamescope-ingest "${ingest_args[@]}"
