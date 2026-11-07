#!/usr/bin/env bash
# Everything left, in the order it has to happen, behind whatever is already
# on the GPU.
#
# There is one MPS device, so these are strictly sequential: two campaigns
# sharing it halve each other's throughput and risk an out-of-memory on the
# larger jobs. Each stage is resumable on its own (the runner skips completed
# job ids from state.jsonl), so a kill anywhere is recoverable by rerunning
# this script rather than by reasoning about where it stopped.
#
# Order, and why:
#   1. the corrected-construct comparison, which is cheap and answers a
#      question already paid for
#   2. the main campaign, which carries the matched-control ROC: the
#      project's falsifiable test
#   3. tier 2, which refines the top decile and needs the ranking the main
#      campaign produces
#   4. the design scan, last on purpose. Its own tab says the composite is
#      not trustworthy until the Sievers arm has run, so running it before
#      the ROC would produce lifts that have to be caveated into
#      uselessness.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SENV="$ROOT/../BINMAN/.pixi/envs/default"
export PYTHONPATH="$ROOT"

say() { echo "=== $* $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="; }

# A stall detector that only runs after the stall can no longer matter is not
# a detector. `nobble.execute.watchdog` tells a working campaign apart from a
# stopped one, which is the ambiguity F20 cost most of a night to, and it was
# reachable only through `tools/status.sh`, called on the last line of this
# script. So during the forty-seven hours when a stall is possible, nothing
# consulted it (F112).
#
# Armed here instead, for the length of the chain. Read-only: it compares
# recorded timings and prints, and it is the runner's own timeout that stops
# a job. Quiet unless the verdict stops being "ok", so the chain log carries
# a line only when there is something to see.
# Keyed on the exit code, which the watchdog already provides: 0 ok, 1 a job
# running longer than the slowest comparable one it has finished, 2 a job past
# the bound the runner itself allows. Grepping the printed verdict would key
# on its spacing, which is the kind of coupling F54 was.
WATCHDOG_EVERY="${NOBBLE_WATCHDOG_SECONDS:-600}"
watchdog_loop() {
  local verdict code
  while true; do
    sleep "$WATCHDOG_EVERY"
    verdict="$("$SENV/bin/python" -m nobble.execute.watchdog 2>&1)"
    code=$?
    if [ "$code" -ne 0 ]; then
      echo "=== WATCHDOG exit $code $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
      printf '%s\n' "$verdict"
    fi
  done
}
watchdog_loop &
WATCHDOG_PID=$!
# Taken down with the chain however the chain ends, so a killed run does not
# leave a loop behind polling a campaign nobody is running.
trap 'kill "$WATCHDOG_PID" 2>/dev/null || true' EXIT
say "watchdog armed, every ${WATCHDOG_EVERY}s"

# The newest *complete* campaign with a prefix. Complete means it wrote
# campaign.json, which every assembler writes last.
#
# `ls -d campaigns/design_* | tail -1` picked the newest directory, and a
# failed assembly leaves one holding an empty yaml/ and an empty outputs/.
# Three of those sat in campaigns/ from a failing design scan, and the
# newest of them was what this would have handed to run_design.sh. The
# Python side learned this in campaign.latest(); this is the same rule in
# the other language, which is where F54 and F55 both ended up (F57).
# shellcheck source=tools/newest_complete.sh
source "$ROOT/tools/newest_complete.sh"
newest_complete() { nobble_newest_complete "$@" || true; }

# shellcheck source=tools/wait_for_gpu.sh
source "$ROOT/tools/wait_for_gpu.sh"
nobble_wait_for_gpu

# --- 1. the corrected-construct comparison -------------------------------
CORRECTED="$(newest_complete corrected)"
BASELINE="$(newest_complete benchmark)"
if [[ -n "$CORRECTED" && -n "$BASELINE" ]]; then
  say "scoring the corrected campaign"
  "$SENV/bin/python" -m nobble.score.run --campaign "$CORRECTED" || true
  say "comparing corrected against baseline"
  "$SENV/bin/python" -c "
import json, sys
from pathlib import Path
sys.path.insert(0, '$ROOT')
from nobble.validate import compare
report = compare.run(Path('$BASELINE'), Path('$CORRECTED'))
print(json.dumps(report, indent=2, default=str)[:3000])
" || true
fi

# --- 2. the main campaign ------------------------------------------------
CAMPAIGN="$(newest_complete campaign)"
if [[ -z "$CAMPAIGN" ]]; then
  echo "no main campaign assembled: run nobble.execute.campaign first" >&2
else
  say "preflight $CAMPAIGN"
  if "$SENV/bin/python" tools/preflight.py "$CAMPAIGN"; then
    say "running the main campaign"
    bash tools/run_queue.sh --campaign "$CAMPAIGN" || true

    # F47: bench02_BRD4_VHL's fifteen jobs were emitted with a
    # hydroxyproline on BRD4 Pro379, because the modification rule keyed on
    # the E3 rather than on the degron class. The rule is fixed; the YAMLs
    # on disk are not. Correcting it mid-run would have left one pair
    # holding two different inputs, so it waits until here: the GPU is free
    # and nothing has been published. The run_queue call that follows skips
    # every job already in state, so it runs exactly the fifteen this
    # clears and nothing else.
    # Through tools/corrections.sh, not rerun_pair.py directly (F302).
    #
    # This called `rerun_pair.py bench02_BRD4_VHL --apply` unconditionally,
    # and that path clears results whether or not anything needs correcting.
    # On the 2026-11-07 restart, forty minutes after the same fifteen jobs
    # had been corrected, it printed "corrected 0 YAML(s)" and then removed
    # fifteen output directories: an hour of GPU on every chain start to
    # arrive back where it started, with the correct results destroyed
    # first.
    #
    # `corrections.sh` has had the guard since F267, reads "nothing to
    # correct" off a rehearsal rather than off an ambiguous exit code, and
    # covers scr_bench03 as well, which this stage never did. Two spellings
    # of one correction, and the chain was using the one without the guard.
    # `--no-refresh` because the next stage refreshes.
    say "correcting the F47 pair and the scramble inputs"
    bash tools/corrections.sh --apply --no-refresh || \
      echo "a correction refused: see above. The atlas build refuses while" \
           "an input disagrees with its results, so nothing wrong is" \
           "published." >&2

    say "scoring, validating and publishing the main campaign"
    bash tools/refresh.sh "$CAMPAIGN" || true
  else
    echo "preflight failed: refusing to start a 52-hour run on it" >&2
    exit 1
  fi
fi

# --- 3. tier 2 -----------------------------------------------------------
if [[ -n "${CAMPAIGN:-}" && -f "$CAMPAIGN/scores.jsonl" ]]; then
  say "tier 2 on the top decile"
  bash tools/tier2.sh "$CAMPAIGN" || true
fi

# --- 4. the design scan --------------------------------------------------
# Re-assembled here rather than reusing the campaign built before any of
# this ran. The scan's parent is chosen by measured Delta-ipTM, and until
# the main campaign scores, the only evidence is the seven benchmark pairs.
# Picking the target from 158 pairs instead of 7 is the whole reason the
# scan is queued last; reusing a parent chosen from the benchmark alone
# would throw that away.
say "re-assembling the design scan against the full campaign"
"$SENV/bin/python" -c "
import json, sys
sys.path.insert(0, '$ROOT')
from nobble.app import data
from nobble.design import report, assemble
data.configure('$CAMPAIGN' if '$CAMPAIGN' else None)
parent = (report.build().get('preview') or {}).get('parent')
if parent:
    out = assemble.assemble(parent['peptide_id'])
    print(json.dumps({k: out.get(k) for k in
                      ('campaign_id', 'parent', 'pairs', 'jobs_emitted')}, indent=2))
    print('chosen because:', parent.get('chosen_because'))
else:
    print('no scannable parent')
" || true

DESIGN="$(newest_complete design)"
if [[ -n "$DESIGN" ]]; then
  say "design scan"
  bash tools/run_design.sh "$DESIGN" || true
fi

# --- 4b. Tier B ----------------------------------------------------------
# Eleven ligandable-unproven ligases against the seven proven glue-degron
# pairs, each with its degron's scramble: 154 pairs, 1,540 jobs, about 39
# hours (D-NOB-073). Gate G1's construct half closed when Marc named the
# domains (D-NOB-072); its compute half closed when he lifted the 96-hour
# ceiling as arbitrary on his own hardware.
#
# After the design scan rather than before it, for the same reason the scan
# goes last: this arm reads nothing the scan produces, but it is the longest
# single stage left and putting it ahead of the scan would delay the scan by
# a day and a half for no gain.
#
# Assembled here rather than reused from disk if a complete one exists,
# because the arm depends on the form and the library and both can change
# between runs. assemble_tier_b reuses a complete campaign by default, which
# is what makes rerunning this script cheap.
say "assembling Tier B"
TIERB_ASSEMBLE="$("$SENV/bin/python" -c "
import json, sys
sys.path.insert(0, '$ROOT')
from nobble.execute.campaign import assemble_tier_b
out = assemble_tier_b()
print(json.dumps({k: out.get(k) for k in
                  ('path', 'reused', 'pairs', 'jobs_emitted')}))
" 2>&1)"
ASSEMBLE_CODE=$?
printf '%s\n' "$TIERB_ASSEMBLE"
if [ "$ASSEMBLE_CODE" -ne 0 ]; then
  echo "Tier B assembly failed, so the arm is skipped. The rest of the chain" >&2
  echo "    is unaffected: nothing downstream reads Tier B." >&2
else
  TIERB="$(newest_complete tier_b)"
  if [[ -z "$TIERB" ]]; then
    echo "Tier B assembled but no complete campaign is on disk: not running" >&2
  else
    say "preflight $TIERB"
    if "$SENV/bin/python" tools/preflight.py "$TIERB"; then
      say "running Tier B"
      bash tools/run_queue.sh --campaign "$TIERB" || true
      # Checked, not ignored: the arm's whole output is these scores, and a
      # silent scoring failure would leave 39 hours of inference unread
      # (F194, F195).
      say "scoring Tier B"
      if ! "$SENV/bin/python" -m nobble.score.run --campaign "$TIERB"; then
        echo "Tier B scoring failed: the poses are on disk, rerun the scorer" >&2
        echo "    rather than the GPU." >&2
      fi
    else
      echo "Tier B preflight failed: refusing to spend 1,540 jobs on it" >&2
    fi
  fi
fi

# --- 5. publish, once, at the end ----------------------------------------
# The atlas was built straight after the main campaign, before tier 2 and
# the design scan existed. Without rebuilding here, both would run for
# hours and produce nothing the site could show: refined poses the
# catalogue cannot offer and a scan profile with no chart. Rebuilt once,
# at the end, rather than during a run (D-NOB-041: a mid-run publish can
# copy a structure while Boltz is writing it).
if [[ -n "${CAMPAIGN:-}" ]]; then
  say "rebuilding the atlas with tier 2 and the design scan included"
  bash tools/refresh.sh "$CAMPAIGN" || true
fi

# Deploying is the point of having published an atlas, and Marc granted it
# explicitly. It runs last, after everything that could still change the
# bundle. deploy.sh refuses to report success unless all nine routes answer
# 200 and the fingerprint the droplet reports is the tree that was shipped:
# every route answering 200 says the app works, not that it is this version
# of the app (F140).
# The hold is checked before the deploy rather than inside it, so that a held
# atlas reads as a decision in the chain log and not as a deploy that broke.
# deploy.sh checks it again as its first pre-flight step: this one is for the
# reader, that one is the gate.
say "deploying"
if ! PYTHONPATH=. KMP_DUPLICATE_LIB_OK=TRUE "$SENV/bin/python" \
     tools/publication_hold.py >/dev/null 2>&1; then
  say "publication is held, so the atlas stays local"
  PYTHONPATH=. KMP_DUPLICATE_LIB_OK=TRUE "$SENV/bin/python" \
    tools/publication_hold.py || true
else
  bash deploy/deploy.sh || echo "deploy failed: the atlas is built locally, rerun deploy/deploy.sh" >&2
fi

# Score the predictions recorded before any of this ran. Mechanical, so
# the verdict is the thresholds' rather than a reading of the numbers
# after the fact (F13, F18).
say "scoring the F13 predictions"
"$SENV/bin/python" tools/check_prediction.py || true

say "chain complete"
bash tools/status.sh || true
