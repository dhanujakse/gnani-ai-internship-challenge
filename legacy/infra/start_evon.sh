#!/usr/bin/env bash
# Launch Evon v3.3 on the GPU box (one 80 GB A100/H100). Keep weights on a persistent volume.
# Requires: vLLM >= 0.12, EVON_API_KEY exported.
set -euo pipefail

: "${EVON_API_KEY:?set EVON_API_KEY before starting}"

exec vllm serve gnani/gnani-evon-v3.3-30B-A3B \
  --trust-remote-code \
  --max-model-len 8192 \
  --served-model-name model \
  --api-key "$EVON_API_KEY" \
  --host 0.0.0.0 \
  --port 8000
