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
# shellcheck source=tools/newest_complete.sh
source "$ROOT/tools/newest_complete.sh"

CAMPAIGN="${1:-}"
if [[ -z "$CAMPAIGN" ]]; then
  # Completeness first, then "has it produced anything to score". A campaign
  # that never wrote campaign.json is a failed assembly, and the naive
  # `ls -d | tail -1` here would have handed one to the scorer (F57, F190).
  candidate="$(nobble_newest_complete campaign || true)"
  if [[ -n "$candidate" && -s "$candidate/results.jsonl" ]]; then
    CAMPAIGN="$candidate"
  fi
fi
[[ -n "$CAMPAIGN" ]] || CAMPAIGN="$(nobble_newest_complete benchmark || true)"
[[ -n "$CAMPAIGN" ]] || { echo "refresh: no campaign found" >&2; exit 2; }
echo "=== refreshing $CAMPAIGN ==="

# Each step's status is captured before anything pipes it away, and the
# steps are not treated alike (F194).
#
# Scoring and the atlas build gate publication. `| tail -3` discarded their
# status, so a failed score left `scores.jsonl` as the previous run's and
# the atlas copied it, and a refused atlas build printed its refusal while
# this script went on to say "refreshed". The drift check cannot catch the
# first, because a rebuild reads the same stale file: that is F171's
# compare-stale-against-stale one layer up.
#
# Throughput is not gating. It feeds a panel, and blocking a valid
# campaign's publication because a timing summary failed would be the
# wrong trade: it warns.
STEP_LOG="$(mktemp -t nobble_refresh_step)"
trap 'rm -f "$STEP_LOG"' EXIT

echo "--- score"
"$SCI" -m nobble.score.run --campaign "$CAMPAIGN" > "$STEP_LOG" 2>&1
SCORE_CODE=$?
tail -3 "$STEP_LOG"
if [ "$SCORE_CODE" -ne 0 ]; then
  echo "refresh: scoring failed (exit $SCORE_CODE), so nothing is published." >&2
  echo "        scores.jsonl still holds the previous run's values and the" >&2
  echo "        atlas build would copy them. The published atlas stands," >&2
  echo "        which is stale rather than wrong (F59)." >&2
  exit 1
fi

echo "--- validate"
"$SCI" -c "
import pathlib, json
from nobble.validate.layers import run
r = run(pathlib.Path('$CAMPAIGN'))
for name, layer in r['layers'].items():
    print(f\"    {name}: {layer['status'][:90]}\")
"

# The opt-out, decided once, because it has to gate both side effects on
# shared state and used to gate only one (F170).
NO_PUBLISH=0
if [[ "${NOBBLE_NO_PUBLISH:-}" == "1" || "${2:-}" == "--no-publish" ]]; then
  NO_PUBLISH=1
fi

echo "--- throughput"
# data/throughput.json is read by the app, by the projection that sizes a
# campaign and decides Gate G1, and by wait_for_gpu.sh. Writing it from a
# campaign someone is merely inspecting replaces the running campaign's
# measurement with that one's, which is F131's incident arriving through a
# tool instead of a test. --no-publish said it meant "change nothing shared"
# and gated the atlas alone (F170).
if [[ "$NO_PUBLISH" == "1" ]]; then
  echo "    skipped (--no-publish): data/throughput.json is shared state and"
  echo "    still describes whatever campaign last measured it"
else
"$SCI" -m nobble.execute.runner --campaign "$CAMPAIGN" --throughput > "$STEP_LOG" 2>&1
THROUGHPUT_CODE=$?
if [ "$THROUGHPUT_CODE" -ne 0 ]; then
  echo "    throughput failed (exit $THROUGHPUT_CODE): data/throughput.json still" >&2
  echo "    describes whatever last measured it. Not fatal, because this feeds" >&2
  echo "    a panel rather than the science, and refusing to publish a good" >&2
  echo "    campaign over a timing summary is the wrong trade (F194)." >&2
fi
cat "$STEP_LOG" \
  | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(f\"    {d.get('jobs_timed')} jobs timed, median {d.get('median_seconds_per_token')} s/token, {d.get('affordable_pairs')} affordable pairs\")
except Exception as e:
    print('    throughput not updated:', e)
"
fi

# Publishing is opt-out, because scoring a secondary campaign to look at
# it should not change what the public site serves. Running
# `refresh.sh campaigns/corrected_...` to inspect a half-finished run
# republished the atlas from it, which is a side effect nobody asks for
# when they say "score this".
if [[ "$NO_PUBLISH" == "1" ]]; then
  echo "--- atlas skipped (--no-publish): $CAMPAIGN scored but not published"
else
  echo "--- atlas"
  "$SCI" deploy/build_atlas.py "$CAMPAIGN" > "$STEP_LOG" 2>&1
  ATLAS_CODE=$?
  tail -4 "$STEP_LOG"
  if [ "$ATLAS_CODE" -ne 0 ]; then
    echo "refresh: the atlas build refused (exit $ATLAS_CODE). Nothing was" >&2
    echo "        published and the previously published atlas stands. The" >&2
    echo "        reason is above: a refusal on stale inputs is the build" >&2
    echo "        working, not failing." >&2
    exit 1
  fi
fi
echo "=== refreshed. Deploy separately with deploy/deploy.sh ==="
