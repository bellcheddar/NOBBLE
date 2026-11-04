#!/usr/bin/env bash
# Run a design scan, after whatever is already on the GPU has finished.
#
# One MPS device, so this waits rather than competing: two campaigns sharing
# it halve each other's throughput and risk an out-of-memory on the larger
# jobs. Same reason run_corrected.sh waits for the benchmark queue.
#
# Preflight runs before the queue, not after. A scan is 240 jobs, and the
# failure worth catching is the silent one: a variant whose cofactor differs
# from its parent's completes perfectly well and reports the missing ion as
# the substitution's effect (D-NOB-038).
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SENV="$ROOT/../BINMAN/.pixi/envs/default"
BENV="$ROOT/../BoltzMaker/.pixi/envs/default"
export KMP_DUPLICATE_LIB_OK=TRUE PYTORCH_ENABLE_MPS_FALLBACK=1 PYTHONPATH="$ROOT"

# shellcheck source=tools/wait_for_gpu.sh
source "$ROOT/tools/wait_for_gpu.sh"
nobble_wait_for_gpu

CAMPAIGN="${1:-$(ls -d campaigns/design_* 2>/dev/null | tail -1)}"
if [[ -z "$CAMPAIGN" ]]; then
  echo "no design campaign to run: assemble one with nobble.design.assemble" >&2
  exit 2
fi

echo "=== preflight $CAMPAIGN ==="
if ! "$SENV/bin/python" tools/preflight.py "$CAMPAIGN"; then
  echo "preflight failed: refusing to spend 240 jobs on it" >&2
  exit 1
fi

echo "=== running design scan $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
caffeinate -dimsu "$BENV/bin/python" -m nobble.execute.runner --campaign "$CAMPAIGN"
status=$?
echo "=== inference finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$status ==="

echo "=== score ==="
"$SENV/bin/python" -m nobble.score.run --campaign "$CAMPAIGN"

echo "=== lift ==="
"$SENV/bin/python" -c "
import json, sys
from pathlib import Path
sys.path.insert(0, '$ROOT')
from nobble.design import lift as L
campaign = Path('$CAMPAIGN')
meta = json.loads((campaign / 'campaign.json').read_text())
report = L.from_scores(campaign / 'scores.jsonl', meta['parent'])
print(json.dumps({k: v for k, v in report.items() if k != 'lifts'}, indent=2))
if report.get('lifts'):
    objects = [L.Lift(**item) for item in report['lifts']]
    profile = L.scan_profile(objects, meta['parent_sequence'])
    (campaign / 'scan_profile.json').write_text(json.dumps(profile, indent=2))
    print('most sensitive position:', json.dumps(profile.get('most_sensitive')))
"
echo "=== design scan done $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
