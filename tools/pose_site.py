#!/usr/bin/env python3
"""Is the predicted degron at the wrong site, or in the wrong pose there?

Pose recovery fails: 0 of 65 poses within 3 A, median 17.54 A (F212), and
tier-2 refinement sharpens without recovering (F215). A single RMSD cannot say
whether the model never found the degron site or found it and laid the chain
along it in the wrong register, and the headline reads differently in each
case.

The measurement itself is `nobble.score.poses.footprint`, beside the RMSD it
decomposes and sharing its receptor superposition. This is the command-line
view of it over a campaign, which adds the two things that are properties of a
campaign rather than of a pose:

* `confounded`: the pair's poses were folded from a superseded input (F219),
  so its footprint is not a measurement of the current input.
* which pose to read, each pair's best by RMSD or all of them. The best pose
  per pair is a best-case selection, and whether the agreement survives the
  other seeds is the difference between a result and a cherry-pick (F227).

**No verdict is emitted and no cutoff is introduced.** Calling a Jaccard of
0.3 "the right site" would be inventing an acceptance threshold to decide a
gate, which is the thing D-NOB-076 explicitly refused to do for pose recovery.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score import poses
from nobble.validate.layers import recovery_target


def contact_cutoff() -> float:
    """The contact distance the measurement uses, from config.

    Read once at import in `poses`, the same way that file already reads
    `docked_contact_cutoff_a`. One spelling of the threshold, in the module
    that applies it.
    """
    return poses.CONTACT_CUTOFF


def _confounded(campaign: Path) -> set[str]:
    """Pairs whose poses came from an input no longer on disk (F219)."""
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import stale_featurisation as featurisation
    except ImportError:
        return set()
    try:
        rows = featurisation.disagreements(campaign)
    except OSError:
        return set()
    return {row["job_id"].split("__")[0] for row in rows}


def _every_pose(campaign: Path) -> list[dict]:
    """Every pose with an RMSD, not just each pair's best."""
    validation = campaign / "validation.json"
    if not validation.exists():
        return []
    layer = json.loads(validation.read_text())["layers"].get("pose_recovery", {})
    return [row for row in (layer.get("detail") or []) if row.get("rmsd") is not None]


def _best_per_pair(campaign: Path) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for row in _every_pose(campaign):
        current = best.get(row["pair_id"])
        if current is None or row["rmsd"] < current["rmsd"]:
            best[row["pair_id"]] = row
    return best


def footprints(campaign: Path, cutoff: float | None = None,
               only: set[str] | None = None,
               every_pose: bool = False) -> list[dict]:
    """One record per pose, through `poses.footprint`.

    `only` restricts to named pairs. Each record reads two structures off disk,
    so a test that needs one pair should ask for one pair.
    """
    campaign = Path(campaign)
    confounded = _confounded(campaign)
    results = {row["job_id"]: row for row in
               (json.loads(line) for line
                in (campaign / "results.jsonl").read_text().splitlines()
                if line.strip())}

    if every_pose:
        candidates = [(row["pair_id"], row) for row in
                      sorted(_every_pose(campaign),
                             key=lambda r: (r["pair_id"], r["job_id"]))]
    else:
        candidates = sorted(_best_per_pair(campaign).items())

    records = []
    for pair_id, chosen in candidates:
        if only is not None and pair_id not in only:
            continue
        target = recovery_target(pair_id)
        job = results.get(chosen["job_id"])
        if target is None or job is None:
            records.append({"pair_id": pair_id, "job_id": chosen["job_id"],
                            "rmsd": chosen["rmsd"], "status": "no_structure"})
            continue
        record = poses.footprint(job, target, cutoff)
        record["rmsd"] = chosen["rmsd"]
        # Campaign-level, so it overrides the geometric status: a footprint
        # measured against a superseded input is not wrong, it is about an
        # input that is no longer there.
        if pair_id in confounded:
            record["status"] = "confounded"
        records.append(record)
    return records


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", nargs="?", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--every-pose", action="store_true",
                        help="every pose, not each pair's best")
    args = parser.parse_args(argv)

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("campaign") or latest("benchmark")
    if campaign is None:
        print("no campaign found", file=sys.stderr)
        return 2

    records = footprints(Path(campaign), every_pose=args.every_pose)
    if args.json:
        print(json.dumps(records, indent=2))
        return 0
    if not records:
        print("no pose recovery detail to read: run validation first")
        return 2

    cutoff = records[0].get("cutoff_a", contact_cutoff())
    print(f"footprint of the lowest-RMSD pose per pair, contacts within "
          f"{cutoff} A\n")
    print(f"{'pair':24} {'rmsd':>6} {'gap':>6} {'dep':>4} {'pred':>5} "
          f"{'shared':>6} {'jacc':>6} {'onWindow':>9}")
    for record in records:
        if "jaccard" not in record:
            print(f"{record['pair_id']:24} {record['rmsd']:6.2f}"
                  f"{'':40} {record['status']}")
            continue
        flag = "" if record["status"] == "measured" else f"  <- {record['status']}"
        print(f"{record['pair_id']:24} {record['rmsd']:6.2f} "
              f"{record['centroid_gap_a']:6.2f} {record['deposited_contacts']:4d} "
              f"{record['predicted_contacts']:5d} {record['shared_contacts']:6d} "
              f"{record['jaccard'] if record['jaccard'] is not None else '--':>6} "
              f"{record['window_residues_touched']:4d}"
              f"/{record['window_residues']:<4d}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
