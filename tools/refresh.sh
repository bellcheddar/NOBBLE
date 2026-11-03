#!/usr/bin/env bash
# Recompute everything downstream of the campaign, then rebuild the published
# slice. Safe to run while a queue is live: every stage reads whatever has
# landed and reports what is still missing rather than waiting for it.
#
#   score -> validate -> throughput -> atlas
#
# Deployment is deliberately NOT part of this: refreshing is cheap and
# repeatable, pushing to a public site is neither.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SCI="$ROOT/../BINMAN/.pixi/envs/default/bin/python"
export KMP_DUPLICATE_LIB_OK=TRUE PYTHONPATH="$ROOT"

CAMPAIGN="${1:-$(ls -d campaigns/benchmark_* 2>/dev/null | tail -1)}"
[[ -n "$CAMPAIGN" ]] || { echo "refresh: no campaign found" >&2; exit 2; }
echo "=== refreshing $CAMPAIGN ==="

echo "--- score"
"$SCI" -m nobble.score.run --campaign "$CAMPAIGN" 2>&1 | tail -3

echo "--- validate"
"$SCI" -c "
import pathlib, json
from nobble.validate.layers import run
r = run(pathlib.Path('$CAMPAIGN'))
for name, layer in r['layers'].items():
    print(f\"    {name}: {layer['status'][:90]}\")
"

echo "--- throughput"
"$SCI" -m nobble.execute.runner --campaign "$CAMPAIGN" --throughput 2>&1 \
  | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(f\"    {d.get('jobs_timed')} jobs timed, median {d.get('median_seconds_per_token')} s/token, {d.get('affordable_pairs')} affordable pairs\")
except Exception as e:
    print('    throughput not updated:', e)
"

echo "--- atlas"
"$SCI" deploy/build_atlas.py 2>&1 | tail -3
echo "=== refreshed. Deploy separately with deploy/deploy.sh ==="
