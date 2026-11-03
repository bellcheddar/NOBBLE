#!/usr/bin/env bash
# Run the corrected-construct campaign, but only after the benchmark queue has
# finished: both use the single MPS device and running them together would
# halve the throughput of each and risk an out-of-memory on the large jobs.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
BENV="$ROOT/../BoltzMaker/.pixi/envs/default"
export KMP_DUPLICATE_LIB_OK=TRUE PYTORCH_ENABLE_MPS_FALLBACK=1 PYTHONPATH="$ROOT"

echo "=== waiting for the benchmark queue to finish $(date -u +%H:%M:%SZ) ==="
while tmux has-session -t nobble-bench 2>/dev/null; do sleep 60; done
echo "=== benchmark queue finished, starting corrected campaign $(date -u +%H:%M:%SZ) ==="

CAMPAIGN="$(ls -d campaigns/corrected_* 2>/dev/null | tail -1)"
if [[ -z "$CAMPAIGN" ]]; then echo "no corrected campaign to run" >&2; exit 2; fi
caffeinate -dimsu "$BENV/bin/python" -m nobble.execute.runner --campaign "$CAMPAIGN"
echo "=== finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$? ==="
