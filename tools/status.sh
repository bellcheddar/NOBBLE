#!/usr/bin/env bash
# Where everything stands, in one screen.
#
# A 60-hour chain across four campaigns leaves its state in tmux sessions,
# queue files, state files and logs. Reading those by hand each time is
# the kind of thing that gets done wrongly at 3am, so this reads them once
# and says what is running, what is queued, which gates are open and
# whether the published site matches the work.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SCI="$ROOT/../BINMAN/.pixi/envs/default/bin/python"
export PYTHONPATH="$ROOT"

echo "=== NOBBLE status $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo

echo "-- GPU sessions"
tmux ls 2>/dev/null | sed 's/^/   /' || echo "   none"
echo

echo "-- campaigns"
"$SCI" - <<'PY'
import json, glob, os
from pathlib import Path
for d in sorted(glob.glob("campaigns/*")):
    p = Path(d)
    q = p / "queue.jsonl"
    if not q.exists():
        continue
    total = sum(1 for line in q.read_text().splitlines() if line.strip())
    done = set()
    state = p / "state.jsonl"
    if state.exists():
        for line in state.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") == "done":
                done.add(r["job_id"])
    scored = 0
    s = p / "scores.jsonl"
    if s.exists():
        scored = sum(1 for line in s.read_text().splitlines() if line.strip())
    pct = 100.0 * len(done) / total if total else 0.0
    mark = "done" if len(done) >= total else "running" if done else "queued"
    print(f"   {p.name:34s} {len(done):5d}/{total:<5d} {pct:5.1f}%  {mark:8s} scored {scored}")
PY
echo

echo "-- running jobs"
# Elapsed time is computed from started_at in state.jsonl, never read off a
# formatted clock: `stat` prints local time and `date -u` prints UTC, and
# comparing the two cost a healthy job once already (F20).
# Both tiers, because a chain run leaves an idle tier 1 beside a live tier 2
# and this asked only tier 1: a five-hour tier-2 job showed here as an empty
# heading. That liveness is per tier is F216's finding, made in the watchdog
# and not carried to its caller.
for tier in 1 2; do
  "$SCI" -m nobble.execute.watchdog --tier "$tier" || true
done
echo

echo "-- gates"
"$SCI" - <<'PY'
import json
from nobble.execute.runner import disk_gate
from nobble.curate.diversity import projected_hours
g = disk_gate()
print(f"   G5 disk      {'OPEN' if g['open'] else 'closed'}  {g['free_gb']} GB free, floor {g['floor_gb']}")
import glob
from pathlib import Path
camps = sorted(glob.glob("campaigns/campaign_*"))
if camps:
    q = Path(camps[-1]) / "queue.jsonl"
    rows = [json.loads(l) for l in q.read_text().splitlines() if l.strip()]
    pairs = len({r["pair_id"] for r in rows})
    # The real token total, not a representative job from whichever campaign
    # was measured last: that method projected this campaign at 104 h and
    # opened Gate G1 on a 54-hour run (F45).
    h = projected_hours(pairs, total_tokens=sum(r["tokens"] for r in rows))
    print(f"   G1 tier 1    {'OPEN' if h.get('gate_g1_open') else 'closed'}  "
          f"{h.get('projected_hours')} h projected, max {h.get('max_compute_hours')}")

    # And the refinement side, which this did not show. projected_hours
    # prices tier 1, so a reader of this section saw "G1 closed" while the
    # decile's refinement cost 31 to 235 hours against 73 remaining and
    # nothing had compared the two (F135). The gate is computed; it was not
    # visible here, which for a status page is most of the way to not being
    # computed.
    from nobble.execute import budget, tier2
    spent = budget.hours_spent()
    campaign = Path(camps[-1])

    # Scoped to the decile, because that is all refinement ever runs on.
    # Pricing every ternary job in the campaign said 159 to 1,190 hours and
    # read as a gate about to stop the build, when the decile is a tenth of
    # it.
    #
    # Sized from the campaign's own pair count rather than read out of
    # tier2.json. The recorded selection answers "what did the last
    # selection cost"; a status page is asked "what will refinement cost",
    # and the two diverge as soon as scoring advances. The selection on disk
    # here was taken against the six pairs scored so far and names one pair,
    # where the finished campaign's decile is sixteen. Which pairs they are
    # needs the scores, so this is the decile's size and not its membership,
    # and it says so.
    every = sorted({r["pair_id"] for r in rows})
    take = max(1, int(len(every) * tier2.DECILE_FRACTION))
    ranked = every[:take]

    report = budget.gate_g1(campaign, ranked)
    t2 = report["tier2"]
    if not t2["priceable"]:
        # Not priced is not closed. The line used to read "closed, 0.0 h"
        # for a campaign with nothing finished, which is the most
        # reassuring thing it could say about a cost nobody knows (F161).
        print(f"   G1 refine    not priced  {t2['jobs']} job(s) over "
              f"{len(ranked)} pair(s), no tier-1 ternary job of this "
              f"campaign has completed")
        print(f"   spent        {spent['hours']} h over {spent['jobs']} job(s)")
        raise SystemExit(0)
    print(f"   G1 refine    {'OPEN' if report['gate_g1_open'] else 'closed'}  "
          f"{t2['hours_low']} to {t2['hours_high']} h for {t2['jobs']} job(s) "
          f"over {len(ranked)} pair(s), {report['hours_remaining']} h left, "
          f"judged on {report['judged_on']}")
    print(f"                a decile-sized slice of {len(every)} pair(s), "
          "not the ranking: that needs the scores")
    # What will happen, not just whether the full decile fits. An OPEN on
    # the line above does not stop the chain: tier2.run drops pairs from the
    # bottom of the ranking until the rest fits, and only an empty result
    # opens the gate for real. Saying only "OPEN" reads as a halt.
    affordable = budget.affordable_pairs(campaign, ranked)
    kept = len(affordable["affordable"])
    print(f"                after reduction {kept} of {len(ranked)} pair(s) "
          f"fit; gate {'OPEN' if affordable['gate_g1_open'] else 'closed'}")
    print(f"   spent        {spent['hours']} h over {spent['jobs']} job(s)")
PY
echo

echo "-- published site"
"$SCI" - <<'PY'
import json
from pathlib import Path
a = Path("deploy/atlas/ATLAS.json")
if a.exists():
    d = json.loads(a.read_text())
    out = d.get("outstanding") or []
    print(f"   atlas holds  {d.get('campaign')}")
    print(f"   outstanding  {len(out)} campaign(s) when built")
else:
    print("   no atlas built")
PY
curl -s -o /dev/null -w "   live         %{http_code} in %{time_total}s\n" https://nobble.mdeller.com/ 2>/dev/null || echo "   live         unreachable"
echo

echo "-- provenance"
"$SCI" tools/provenance.py
echo

echo "-- failures in the logs"
# grep -c exits 1 when it finds nothing, so `|| echo 0` appends a second
# zero and every clean log reads as a failure. Count without the fallback.
found=0
for f in logs/*.log; do
  [[ -f "$f" ]] || continue
  n=$(grep -cE "Traceback|failed:|OOM|Killed|NaN" "$f" 2>/dev/null) || n=0
  if [[ "${n:-0}" -gt 0 ]]; then
    echo "   $(basename "$f"): $n"
    found=$((found + n))
  fi
done
[[ "$found" -eq 0 ]] && echo "   none in $(ls logs/*.log 2>/dev/null | wc -l | tr -d ' ') log file(s)"
