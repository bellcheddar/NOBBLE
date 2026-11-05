#!/usr/bin/env bash
# Run a design scan, after whatever is already on the GPU has finished.
#
# One MPS device, so this waits rather than competing: two campaigns sharing
# it halve each other's throughput and risk an out-of-memory on the larger
# jobs. Same reason run_corrected.sh waits for the benchmark queue.
#
# Preflight runs before the queue, not after. A scan is 240 jobs, and the
# failure worth catching is the silent one: a cofactor asymmetry completes
# perfectly well and reports the missing ion as an effect of something else
# (D-NOB-034, D-NOB-038).
#
# Preflight checks the half it can see from a campaign's own YAMLs: that a
# pair's binary and ternary arms agree about the ion, so Delta-ipTM is not a
# difference across it. The other half, that a variant agrees with its
# parent, is not checked here and does not need to be: the assembler takes
# one cofactor decision from the parent and gives it to every variant, since
# a scan mutates coordinating residues and inferring per variant would drop
# the ion at exactly the positions the scan exists to measure. This comment
# used to credit preflight with both (F151).
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SENV="$ROOT/../BINMAN/.pixi/envs/default"
BENV="$ROOT/../BoltzMaker/.pixi/envs/default"
export KMP_DUPLICATE_LIB_OK=TRUE PYTORCH_ENABLE_MPS_FALLBACK=1 PYTHONPATH="$ROOT"

# shellcheck source=tools/wait_for_gpu.sh
source "$ROOT/tools/wait_for_gpu.sh"
nobble_wait_for_gpu

# shellcheck source=tools/newest_complete.sh
source "$ROOT/tools/newest_complete.sh"
CAMPAIGN="${1:-$(nobble_newest_complete design || true)}"
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
# Checked, because the lift step below reads these scores and a lift
# computed from the previous run's values is a number that looks like a
# measurement of this scan (F194). The same gap as refresh.sh had, in the
# other script that scores and then consumes what it scored.
"$SENV/bin/python" -m nobble.score.run --campaign "$CAMPAIGN"
SCORE_CODE=$?
if [ "$SCORE_CODE" -ne 0 ]; then
  echo "run_design: scoring failed (exit $SCORE_CODE), so the lift below would" >&2
  echo "            be computed from whatever scores.jsonl already held. The" >&2
  echo "            inference is done and recorded; rerun scoring rather than" >&2
  echo "            the scan." >&2
  exit 1
fi

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
    # Beside the campaign, for inspection. Not the published copy:
    # report.build() recomputes the profile into design.json, which is what
    # the atlas ships and the page reads. Both now take the parent and the
    # sequence from this campaign's own campaign.json, so the two agree by
    # construction rather than by coincidence (F147).
    (campaign / 'scan_profile.json').write_text(json.dumps(profile, indent=2))
    print('most sensitive position:', json.dumps(profile.get('most_sensitive')))
"
LIFT_CODE=$?
echo "=== design scan done $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$LIFT_CODE ==="
# The script used to end on that echo, so a failed lift exited 0 and the
# scan reported success with no scan_profile.json written. The inference is
# the expensive part and it is recorded either way; this says whether the
# analysis after it ran (F195).
exit $LIFT_CODE
