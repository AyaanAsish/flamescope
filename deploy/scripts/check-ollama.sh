#!/usr/bin/env bash
# Verify that Ollama on the host answers and has LLM_MODEL and EMBED_MODEL pulled (document 11 section 4).
# OLLAMA_BASE_URL names host.docker.internal for the containers; the host reaches it via localhost.
set -euo pipefail

readonly REQUEST_TIMEOUT_SECONDS=5
readonly PULL_HINT="run 'make ollama-pull'"

usage() {
  echo "Usage: OLLAMA_BASE_URL=... LLM_MODEL=... EMBED_MODEL=... $(basename "$0")" >&2
  exit 2
}

host_base_url() {
  echo "${OLLAMA_BASE_URL/host.docker.internal/localhost}"
}

pulled_model_names() {
  local tags
  tags="$(curl -fsS -m "$REQUEST_TIMEOUT_SECONDS" "$1/api/tags")" || return 1
  { grep -Eo '"name": *"[^"]*"' <<< "$tags" || true; } | sed -E 's/"name": *"([^"]*)"/\1/'
}

# Ollama stores an untagged model as "<name>:latest".
has_model() {
  local wanted="$1" names="$2"
  [[ "$wanted" == *:* ]] || wanted="$wanted:latest"
  grep -qxF "$wanted" <<< "$names"
}

main() {
  [[ -n "${OLLAMA_BASE_URL:-}" && -n "${LLM_MODEL:-}" && -n "${EMBED_MODEL:-}" ]] || usage
  local base_url names model missing=0
  base_url="$(host_base_url)"
  if ! names="$(pulled_model_names "$base_url")"; then
    echo "Ollama does not answer at $base_url; start the Ollama app or 'ollama serve', then $PULL_HINT" >&2
    exit 1
  fi
  for model in "$LLM_MODEL" "$EMBED_MODEL"; do
    has_model "$model" "$names" && continue
    echo "Ollama model $model is not pulled; $PULL_HINT" >&2
    missing=1
  done
  ((missing == 0)) || exit 1
  echo "Ollama at $base_url with $LLM_MODEL and $EMBED_MODEL"
}

main "$@"
