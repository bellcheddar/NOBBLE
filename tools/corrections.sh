#!/usr/bin/env bash
# The corrections that need the GPU, in order, then the refresh they feed.
#
# Two pairs of the main campaign hold poses folded from an input that is no
# longer what the project means to run:
#
#   bench02_BRD4_VHL        15 job(s)  F47/F219: the YAMLs were corrected and
#                                      Boltz re-folded them from its own cached
#                                      featurisation, so the hydroxyproline is
#                                      still in the poses. Corrected from a
#                                      known-good campaign.
#   scr_bench03_BRD4_CRBN    5 job(s)  F262: the ternary YAMLs were written
#                                      without their glue, so the arm was a
#                                      second binary arm and its Delta-ipTM is
#                                      0.0 by construction. The correct YAML
#                                      has never existed on disk, so this one
#                                      is regenerated from the current code
#                                      (F265).
#
# Both refuse to clear results unless the input will actually change, so
# running this twice is not destructive: the second run reports nothing to do.
#
# Order matters. The waits come before anything is cleared, because clearing
# twenty results while the chain is still scoring would hand its scorer a
# campaign with twenty holes in it. `run_queue.sh` waits for the GPU itself,
# but by then the damage would be done, so this waits first and explicitly.
#
# The atlas rebuild at the end is the point of the whole exercise: it refuses
# today on both of these (F219 and F266). It rebuilds the local slice and
# does not publish anything: deploying is a separate rsync that
# publication_hold.py refuses while D-NOB-076 stands, and the live site goes
# on serving the benchmark panel until that is decided. An earlier version of
# this comment said the rebuild publishes the contrast the site is missing,
# which conflated the build directory with the host (F261, corrected).
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SCI="$ROOT/../BINMAN/.pixi/envs/default/bin/python"
export KMP_DUPLICATE_LIB_OK=TRUE PYTHONPATH="$ROOT"

APPLY=""
[[ "${1:-}" == "--apply" ]] && APPLY="1"

# shellcheck source=tools/newest_complete.sh
source "$ROOT/tools/newest_complete.sh"
CAMPAIGN="$(nobble_newest_complete campaign || true)"
[[ -n "$CAMPAIGN" ]] || { echo "corrections: no complete campaign" >&2; exit 2; }
echo "=== corrections for $CAMPAIGN ==="

if [[ -z "$APPLY" ]]; then
  echo
  echo "DRY RUN. Each correction is rehearsed below; nothing is written."
  echo "Rerun with --apply to perform them, which waits for the GPU first."
  echo
fi

run_one() {
  local pair="$1"; shift
  echo "--- $pair"
  # The rehearsal decides whether there is anything to do, rather than the
  # apply's exit code: rerun_pair exits 2 for "nothing to correct" and for
  # several real failures, and a script that treated them alike would skip a
  # broken correction silently.
  local rehearsal status
  rehearsal="$("$SCI" tools/rerun_pair.py "$pair" --campaign "$CAMPAIGN" "$@" 2>&1)"
  status=$?
  printf '%s\n' "$rehearsal" | sed 's/^/    /'
  # "Nothing to do" is read off the rehearsal, not off its exit code, and
  # not only when it failed. The regenerate path exits 2 and says
  # "byte-identical"; the reference path exits 0 and says "0 of 15 YAML(s)
  # differ" with "no stale featurisation left to clear", which is exactly the
  # state bench02 is in once its correction has worked. The first draft of
  # this put the check inside the non-zero branch, so a second run after a
  # successful correction would have cleared fifteen results and re-run
  # fifteen jobs on an input that was already right: about an hour of GPU to
  # arrive back where it started.
  if printf '%s' "$rehearsal" | grep -q "byte-identical"; then
    echo "    nothing to correct: the YAMLs are already what the code emits"
    return 0
  fi
  if printf '%s' "$rehearsal" | grep -q "no stale featurisation left to clear" \
     && printf '%s' "$rehearsal" | grep -qE "^\s*0 of [0-9]+ YAML\(s\) differ"; then
    echo "    nothing to correct: inputs match and no cache disagrees"
    return 0
  fi
  if [[ "$status" -ne 0 ]]; then
    echo "    REFUSED: not correcting $pair" >&2
    return 1
  fi
  [[ -n "$APPLY" ]] || return 0

  "$SCI" tools/rerun_pair.py "$pair" --campaign "$CAMPAIGN" "$@" --apply || return 1
  bash tools/run_queue.sh --campaign "$CAMPAIGN" || return 1
}

if [[ -n "$APPLY" ]]; then
  # shellcheck source=tools/wait_for_gpu.sh
  source "$ROOT/tools/wait_for_gpu.sh"
  nobble_wait_for_gpu
fi

failed=0
run_one bench02_BRD4_VHL || failed=1
run_one scr_bench03_BRD4_CRBN --regenerate || failed=1

if [[ -n "$APPLY" ]]; then
  echo "--- refresh: score, validate, throughput, atlas"
  bash tools/refresh.sh "$CAMPAIGN" || failed=1
else
  echo "--- refresh: would run tools/refresh.sh $CAMPAIGN"
fi

echo
if [[ "$failed" -eq 0 ]]; then
  echo "=== corrections ${APPLY:+applied}${APPLY:-rehearsed} with no refusal ==="
else
  echo "=== one or more corrections refused: see above ===" >&2
fi
exit "$failed"
