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

# shellcheck source=tools/wait_for_gpu.sh
source "$ROOT/tools/wait_for_gpu.sh"
nobble_wait_for_gpu

# --- 1. the corrected-construct comparison -------------------------------
CORRECTED="$(ls -d campaigns/corrected_* 2>/dev/null | tail -1)"
BASELINE="$(ls -d campaigns/benchmark_* 2>/dev/null | tail -1)"
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
CAMPAIGN="$(ls -d campaigns/campaign_* 2>/dev/null | tail -1)"
if [[ -z "$CAMPAIGN" ]]; then
  echo "no main campaign assembled: run nobble.execute.campaign first" >&2
else
  say "preflight $CAMPAIGN"
  if "$SENV/bin/python" tools/preflight.py "$CAMPAIGN"; then
    say "running the main campaign"
    bash tools/run_queue.sh --campaign "$CAMPAIGN" || true
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

DESIGN="$(ls -d campaigns/design_* 2>/dev/null | tail -1)"
if [[ -n "$DESIGN" ]]; then
  say "design scan"
  bash tools/run_design.sh "$DESIGN" || true
fi

say "chain complete"
