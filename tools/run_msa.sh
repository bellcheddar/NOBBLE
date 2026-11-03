#!/usr/bin/env bash
# Phase 1 MSA precompute. Runs under BoltzMaker's environment, which owns the
# boltz install and therefore its MMseqs2 client.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
BENV="$ROOT/../BoltzMaker/.pixi/envs/default"
export KMP_DUPLICATE_LIB_OK=TRUE
export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$ROOT"
echo "=== NOBBLE MSA precompute started $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
caffeinate -dimsu "$BENV/bin/python" -m nobble.execute.msa
status=$?
echo "=== finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$status ==="
exit $status
