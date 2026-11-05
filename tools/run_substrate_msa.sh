#!/usr/bin/env bash
# MSAs for the corrected (whole-domain) substrate constructs. Network-bound,
# so it runs happily alongside the GPU queue without contending for it.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
BENV="$ROOT/../BoltzMaker/.pixi/envs/default"
export KMP_DUPLICATE_LIB_OK=TRUE PYTHONPATH="$ROOT" TOKENIZERS_PARALLELISM=false
echo "=== substrate-domain MSA precompute $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
caffeinate -dimsu "$BENV/bin/python" -c "
from nobble.execute.msa import precompute_substrate_domains
import json
s = precompute_substrate_domains()
print(json.dumps({k: v for k, v in s.items() if k != 'results'}, indent=2))
"
STATUS=$?
echo "=== finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$STATUS ==="
# The script used to end on the echo above, so its exit status was the
# echo's and a failed precompute reported success. Nothing gates on this
# one today, which is why it went unnoticed: a status that is never read
# and never right is indistinguishable from one that works (F195).
exit $STATUS
