#!/usr/bin/env python
"""Did refinement move the poses towards the crystal?

The question Gate G6 turns on (F212). Tier 1 recovered no pose within 3 A of
its deposited counterpart across the seven benchmark pairs, median 17.54 A,
in frames verified correct. Pocket conditioning changed nothing. Tier-2
refinement is the remaining rung of the fallback ladder, and until
`select_top_decile` carried the recovery controls (D-NOB-075) the decile held
no pair with a crystal, so the refinement could not be measured at all.

Pairs every refined pose with the tier-1 pose of the same job and reports the
move. Nothing here decides anything: the verdict is the threshold's, read
from `config/thresholds.toml`, and this prints what the thresholds say about
the numbers it measured.

Both anchors are printed beside every pair, because a peptide RMSD is only a
measure of the prediction if the receptor it was superposed on actually
superposed, and a refinement that changed the anchor would make the two
numbers incomparable rather than better or worse.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths                                        # noqa: E402
from nobble.numeric import finite                               # noqa: E402
from nobble.score import poses                                  # noqa: E402
from nobble.validate import layers                              # noqa: E402

# What counts as having moved, rather than as the same pose measured twice.
# Reused rather than invented: `campaign_change_margin_a` is already defined
# as the change in median RMSD that counts as a real improvement or
# regression when one set of poses is compared against another, which is
# exactly this comparison. A second key holding the same number would be a
# second place to change it.
MOVED_A = float(paths.thresholds()["scoring"]["campaign_change_margin_a"])
# No "recovered" cutoff is defined here, deliberately. Spec 5.1 reports a
# success-rate curve rather than a single success, the breakpoints are
# configured, and choosing one of them in this file would be choosing how
# lenient the gate's own evidence is. Both tiers are reported at every
# configured breakpoint instead, and the verdict keys on the strictest
# breakpoint whose count actually changed.
BREAKPOINTS = tuple(float(point) for point in
                    paths.thresholds()["scoring"]["rmsd_breakpoints"])


def _recovery(job: dict):
    target = layers.recovery_target(job.get("pair_id"))
    if not target:
        return None
    try:
        return poses.recovery_against_crystal(
            job, target["pdb_id"], target["substrate_chain"],
            target["substrate_acc"], target["receptor_chain"],
            target["receptor_acc"])
    except Exception:                                           # noqa: BLE001
        return None


def compare(campaign: Path) -> dict:
    tier1 = {job["job_id"]: job for job
             in paths.read_jsonl(campaign / "results.jsonl", tolerate_torn=True)}
    refined_path = campaign / "results_tier2.jsonl"
    if not refined_path.exists():
        return {"status": "not_computed: no refined results on disk", "pairs": {}}

    rows = []
    for job in paths.read_jsonl(refined_path, tolerate_torn=True):
        base = job["job_id"].removesuffix("__tier2")
        before = tier1.get(base)
        if before is None:
            continue
        after_result = _recovery(job)
        before_result = _recovery(before)
        if after_result is None or before_result is None:
            continue
        if not (finite(before_result.rmsd) and finite(after_result.rmsd)):
            continue
        rows.append({
            "pair_id": job["pair_id"],
            "job_id": base,
            "tier1_rmsd": before_result.rmsd,
            "tier2_rmsd": after_result.rmsd,
            "move": round(after_result.rmsd - before_result.rmsd, 3),
            "tier1_anchor": before_result.receptor_rmsd,
            "tier2_anchor": after_result.receptor_rmsd,
            "tier1_identity": before_result.peptide_identity,
            "tier2_identity": after_result.peptide_identity,
        })

    if not rows:
        return {"status": "not_computed: no refined pose has a tier-1 "
                          "counterpart with a measurable RMSD yet", "pairs": {}}

    by_pair: dict[str, dict] = {}
    for pair_id in sorted({row["pair_id"] for row in rows}):
        mine = [row for row in rows if row["pair_id"] == pair_id]
        by_pair[pair_id] = {
            "n": len(mine),
            "tier1_best": round(min(row["tier1_rmsd"] for row in mine), 3),
            "tier2_best": round(min(row["tier2_rmsd"] for row in mine), 3),
            "tier1_median": round(st.median(row["tier1_rmsd"] for row in mine), 3),
            "tier2_median": round(st.median(row["tier2_rmsd"] for row in mine), 3),
            "median_move": round(st.median(row["move"] for row in mine), 3),
            "anchor_shifted": any(
                row["tier1_anchor"] is not None and row["tier2_anchor"] is not None
                and abs(row["tier2_anchor"] - row["tier1_anchor"]) > MOVED_A
                for row in mine),
        }

    moves = [row["move"] for row in rows]
    improved = sum(1 for move in moves if move <= -MOVED_A)
    worsened = sum(1 for move in moves if move >= MOVED_A)
    curve = {
        f"within_{point}A": {
            "tier1": sum(1 for row in rows if row["tier1_rmsd"] <= point),
            "tier2": sum(1 for row in rows if row["tier2_rmsd"] <= point),
        }
        for point in BREAKPOINTS
    }

    return {
        "status": "computed",
        "campaign": campaign.name,
        "poses_compared": len(rows),
        "pairs_compared": len(by_pair),
        "pairs_expected": len(layers.RECOVERY_TARGETS),
        "moved_threshold_a": MOVED_A,
        "breakpoints_a": list(BREAKPOINTS),
        "curve": curve,
        "tier1_median": round(st.median(row["tier1_rmsd"] for row in rows), 3),
        "tier2_median": round(st.median(row["tier2_rmsd"] for row in rows), 3),
        "median_move": round(st.median(moves), 3),
        "improved": improved,
        "worsened": worsened,
        "unchanged": len(moves) - improved - worsened,
        "pairs": by_pair,
        "detail": rows,
    }


def verdict(report: dict) -> str:
    """What the thresholds say. Mechanical, so it is theirs and not a reading.

    Ordered so that a change smaller than the configured margin cannot be
    reported as a result. A pose that moved 0.37 A from 5.36 to 4.99 crosses
    the 5 A breakpoint, and reporting that as "refinement crossed 5 A" would
    turn a pose measured twice into a recovery.
    """
    if report["status"] != "computed":
        return report["status"]
    partial = ""
    if report["pairs_compared"] < report["pairs_expected"]:
        partial = (f"{report['pairs_compared']} of {report['pairs_expected']} "
                   f"pair(s) refined so far, so this is partial: ")

    crossings = {point: counts for point, counts in report["curve"].items()
                 if counts["tier2"] > counts["tier1"]}
    inside = {point: counts["tier2"] for point, counts
              in report["curve"].items() if counts["tier2"]}
    tail = f". Poses within each breakpoint now: {inside}" if inside else ""

    # A median move inside the margin is the same pose measured twice.
    if abs(report["median_move"]) < report["moved_threshold_a"]:
        note = ""
        if crossings:
            note = (f", though {sum(c['tier2'] - c['tier1'] for c in crossings.values())} "
                    f"pose(s) sit on the far side of a breakpoint they were "
                    f"just outside ({sorted(crossings)})")
        return (partial + f"refinement did not move the poses: median "
                f"{report['median_move']:+.2f} A, inside the "
                f"{report['moved_threshold_a']} A margin that counts as a "
                f"real change{note}{tail}")

    if crossings:
        point = sorted(crossings, key=lambda key: crossings[key]["tier2"])[0]
        counts = crossings[point]
        label = point.replace("within_", "").replace("A", " A")
        return (partial + f"refinement crossed {label}: {counts['tier2']} "
                f"pose(s) against {counts['tier1']} before, median move "
                f"{report['median_move']:+.2f} A{tail}")

    direction = "closer" if report["median_move"] < 0 else "further"
    return (partial + f"refinement moved the poses {direction} by a median "
            f"{report['median_move']:+.2f} A without crossing a breakpoint: "
            f"{report['improved']} closer, {report['worsened']} further, "
            f"{report['unchanged']} inside the margin{tail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campaign", nargs="?", default=None)
    parser.add_argument("--json", action="store_true",
                        help="the full report rather than the table")
    args = parser.parse_args(argv)

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("campaign")
    if campaign is None:
        print("no campaign found", file=sys.stderr)
        return 2

    report = compare(Path(campaign))
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    if report["status"] != "computed":
        print(report["status"])
        return 0

    print(f"{'pair':26s} {'n':>3s} {'tier1':>8s} {'tier2':>8s} {'move':>8s}  anchor")
    for pair_id, pair in report["pairs"].items():
        flag = "  <- anchor shifted" if pair["anchor_shifted"] else ""
        print(f"{pair_id:26s} {pair['n']:3d} {pair['tier1_median']:8.2f} "
              f"{pair['tier2_median']:8.2f} {pair['median_move']:+8.2f}  "
              f"stable{flag}" if not pair["anchor_shifted"] else
              f"{pair_id:26s} {pair['n']:3d} {pair['tier1_median']:8.2f} "
              f"{pair['tier2_median']:8.2f} {pair['median_move']:+8.2f}"
              f"{flag}")
    print()
    print(f"{report['poses_compared']} pose(s) over {report['pairs_compared']} "
          f"of {report['pairs_expected']} pair(s)")
    print("verdict:", verdict(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
