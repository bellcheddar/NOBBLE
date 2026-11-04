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
# wait_for_gpu.sh says it is "sourced by every script that starts
# inference", and this is the script that starts it: the chain, tier 2 and
# the design scan all reach inference through here, and all three waited
# before calling it while this waited for nothing. Running it directly, with
# a campaign already going, put two runs on one MPS device (F60).
# shellcheck source=tools/wait_for_gpu.sh
source "$ROOT/tools/wait_for_gpu.sh"
nobble_wait_for_gpu

echo "=== NOBBLE queue runner started $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
caffeinate -dimsu "$BENV/bin/python" -m nobble.execute.runner "$@"
status=$?
echo "=== finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$status ==="
exit $status
