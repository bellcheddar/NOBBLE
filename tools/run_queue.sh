#!/usr/bin/env bash
# Phase 2 queue runner. Runs under BoltzMaker's environment (boltz + torch MPS).
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
BENV="$ROOT/../BoltzMaker/.pixi/envs/default"
export KMP_DUPLICATE_LIB_OK=TRUE
export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$ROOT"
echo "=== NOBBLE queue runner started $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
caffeinate -dimsu "$BENV/bin/python" -m nobble.execute.runner "$@"
status=$?
echo "=== finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$status ==="
exit $status
