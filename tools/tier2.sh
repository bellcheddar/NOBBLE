#!/usr/bin/env bash
# Tier 2: select the top decile, build its queue, refine the poses.
#
# Kept separate from tools/refresh.sh on purpose. refresh.sh is cheap and
# idempotent and runs often; this spends GPU hours. It is also strictly
# downstream of scoring, because the decile is chosen from scores that do
# not exist until tier 1 has run.
#
# Tier 2 writes queue_tier2.jsonl, state_tier2.jsonl and results_tier2.jsonl.
# Tier 1's three files are never touched, so a tier-2 run cannot corrupt the
# measurement that selected it.
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
# shellcheck source=tools/wait_for_gpu.sh
source "$ROOT/tools/wait_for_gpu.sh"
nobble_wait_for_gpu

PY_SCI="../BINMAN/.pixi/envs/default/bin/python"
PY_BOLTZ="../BoltzMaker/.pixi/envs/default/bin/python"
CAMPAIGN="${1:-}"

echo "--- select the top decile"
if [ -n "$CAMPAIGN" ]; then
  "$PY_SCI" -m nobble.execute.tier2 "$CAMPAIGN"
else
  "$PY_SCI" -m nobble.execute.tier2
fi

echo "--- refine"
export KMP_DUPLICATE_LIB_OK=TRUE
if [ -n "$CAMPAIGN" ]; then
  caffeinate -dimsu "$PY_BOLTZ" -m nobble.execute.runner "$CAMPAIGN" --tier 2
else
  caffeinate -dimsu "$PY_BOLTZ" -m nobble.execute.runner --tier 2
fi

echo "--- score the refined poses"
# Writes scores_tier2.jsonl. scores.jsonl and weights.json are untouched: the
# composite is not refitted on a decile that the composite itself selected.
if [ -n "$CAMPAIGN" ]; then
  "$PY_SCI" -m nobble.score.run --campaign "$CAMPAIGN" --tier 2
else
  "$PY_SCI" -m nobble.score.run --tier 2
fi

echo "=== tier 2 done. Tier-1 scores are unchanged, by construction. ==="
