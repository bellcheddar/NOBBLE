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

# Default to the main campaign once one has results, else the benchmark
# panel. Hard-defaulting to the benchmark meant a finished main campaign
# was silently never scored or published.
CAMPAIGN="${1:-}"
if [[ -z "$CAMPAIGN" ]]; then
  for candidate in $(ls -d campaigns/campaign_* 2>/dev/null | tail -1); do
    [[ -s "$candidate/results.jsonl" ]] && CAMPAIGN="$candidate"
  done
fi
[[ -n "$CAMPAIGN" ]] || CAMPAIGN="$(ls -d campaigns/benchmark_* 2>/dev/null | tail -1)"
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

# Publishing is opt-out, because scoring a secondary campaign to look at
# it should not change what the public site serves. Running
# `refresh.sh campaigns/corrected_...` to inspect a half-finished run
# republished the atlas from it, which is a side effect nobody asks for
# when they say "score this".
if [[ "${NOBBLE_NO_PUBLISH:-}" == "1" || "${2:-}" == "--no-publish" ]]; then
  echo "--- atlas skipped (--no-publish): $CAMPAIGN scored but not published"
else
  echo "--- atlas"
  "$SCI" deploy/build_atlas.py "$CAMPAIGN" 2>&1 | tail -4
fi
echo "=== refreshed. Deploy separately with deploy/deploy.sh ==="
