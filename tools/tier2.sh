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
# No -e. The runner exits 1 when any job failed, and a refinement run that
# loses one job of ten should still score the nine that ran: aborting here
# would throw away the compute to report a failure the log already shows.
# Every other runner in tools/ does the same.
set -uo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
# shellcheck source=tools/wait_for_gpu.sh
source "$ROOT/tools/wait_for_gpu.sh"
nobble_wait_for_gpu

PY_SCI="../BINMAN/.pixi/envs/default/bin/python"
PY_BOLTZ="../BoltzMaker/.pixi/envs/default/bin/python"
CAMPAIGN="${1:-}"

echo "--- select the top decile"
# Exit 3 is Gate G1: the decile, after automatic reduction, does not fit in
# what is left of max_compute_hours. Refining nothing is the point, so stop
# here rather than running the refiner against a queue that was not written
# (F135).
# Output captured as well as shown, so the decision below reads the
# selector's own answer rather than inferring it from an exit code. Exit 0
# covers a selection, a refusal with nothing rankable and an unpriceable
# refusal alike, and only the first writes a queue (F193).
SELECT_LOG="$(mktemp -t nobble_tier2_select)"
trap 'rm -f "$SELECT_LOG"' EXIT
if [ -n "$CAMPAIGN" ]; then
  "$PY_SCI" -m nobble.execute.tier2 "$CAMPAIGN" 2>&1 | tee "$SELECT_LOG"
else
  "$PY_SCI" -m nobble.execute.tier2 2>&1 | tee "$SELECT_LOG"
fi
# zsh is not in play here (this script declares bash), but the status still
# has to come from the pipeline's first element rather than from tee (F188).
SELECT_CODE="${PIPESTATUS[0]}"
if [ "$SELECT_CODE" -eq 3 ]; then
  echo "=== GATE G1: refinement does not fit the compute budget. Not refining. ==="
  exit 3
fi

# The postcondition, not the status: refine only what this selection queued.
QUEUE="$(sed -n 's/^TIER2_QUEUE=//p' "$SELECT_LOG" | tail -1)"
if [ -z "$QUEUE" ]; then
  echo "=== tier 2: the selector printed no TIER2_QUEUE line, so this is an" >&2
  echo "    older build or it died before reporting. Not refining, because a" >&2
  echo "    refiner with nothing to read logs as though it had refined. ===" >&2
  exit 4
fi
if [ "$QUEUE" = "none" ]; then
  echo "=== tier 2: the selection wrote no queue, so there is nothing to"
  echo "    refine. See tier2.json for which refusal it was. ==="
  exit 0
fi
echo "--- refining the queue this selection wrote: $QUEUE"

echo "--- refine"
export KMP_DUPLICATE_LIB_OK=TRUE
if [ -n "$CAMPAIGN" ]; then
  caffeinate -dimsu "$PY_BOLTZ" -m nobble.execute.runner --campaign "$CAMPAIGN" --tier 2
else
  caffeinate -dimsu "$PY_BOLTZ" -m nobble.execute.runner --tier 2
fi
REFINE_CODE=$?
# Remembered, not acted on yet. The runner exits 1 when any job failed, and
# aborting here would skip scoring the jobs that succeeded, which is what
# `tests/test_scripts.py` forbids and what tier2.sh itself did once. So the
# refinement's status is carried to the end and combined with the scorer's
# (F195).
if [ "$REFINE_CODE" -ne 0 ]; then
  echo "    refinement exited $REFINE_CODE: at least one job failed. Scoring" >&2
  echo "    what did run, and this script will exit non-zero at the end." >&2
fi

echo "--- score the refined poses"
# Writes scores_tier2.jsonl. scores.jsonl and weights.json are untouched: the
# composite is not refitted on a decile that the composite itself selected.
if [ -n "$CAMPAIGN" ]; then
  "$PY_SCI" -m nobble.score.run --campaign "$CAMPAIGN" --tier 2
else
  "$PY_SCI" -m nobble.score.run --tier 2
fi
SCORE_CODE=$?

# Ending on the echo below exited 0 whatever the scoring did, so refined
# poses that failed to score read as a completed refinement: the same shape
# as F193 one step later in the same script (F195).
if [ "$SCORE_CODE" -ne 0 ]; then
  echo "tier 2: the refinement ran but scoring it failed (exit $SCORE_CODE)," >&2
  echo "        so scores_tier2.jsonl may be absent or from an earlier run." >&2
  echo "        The poses are on disk; rerun the scorer rather than the GPU." >&2
  exit "$SCORE_CODE"
fi

echo "=== tier 2 done. Tier-1 scores are unchanged, by construction. ==="
# The refinement's status has the last word, after the poses it produced
# have been scored. Ending on the echo above exited 0 even when jobs failed.
exit "$REFINE_CODE"
