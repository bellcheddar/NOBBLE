#!/usr/bin/env python3
"""Score the predictions registered in F251, F252 and F253, mechanically.

F13 recorded two predictions with explicit falsifiers before their pairs ran,
and `tools/check_prediction.py` scores them rather than leaving them to be
read, because "a scorer that cannot return wrong is not scoring anything"
(F18). Three more were registered in this session, for data that did not yet
exist: refinement's effect on discrimination, the design scan's most
sensitive position, and Tier B's bridging. Without a scorer they would be
read after the fact, which is what F13's mechanism exists to prevent.

Separate from `check_prediction.py` rather than added to it: that tool is
keyed on genes and compares two campaigns, and these three are different
shapes. Same discipline, one tool per prediction family.

The thresholds below are transcribed from the FINDINGS entries and are part
of the predictions. Moving them into config would make the verdicts tunable
once the results are known, which is the opposite of the point: see the
`TOOLS_ALLOWED` note in `tests/test_no_hardcoded_cutoffs.py`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# F251: paired tier-1 against tier-2 AUC over the refined Sievers pairs.
F251_MOVE = 0.10
# F252: window positions by CRBN contact count, measured from the deposition.
F252_SUPPORTED = (5, 6, 7)
F252_REFUTED = (1, 2, 12, 13, 14, 15)
# F253: a Tier B hit, paired against the pair's own scramble.
F253_POSITIVE_SEEDS = 8
F253_SCRAMBLE_SEEDS = 2
F253_SEEDS = 10


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def f251_refinement_discrimination(campaign: Path) -> dict:
    """Does refining the poses improve Delta-ipTM's separation?"""
    from nobble.validate import layers

    verdict = {"finding": "F251",
               "claim": "refinement does not improve discrimination (noise)",
               "falsifier": f"paired AUC moves by more than {F251_MOVE}"}
    tier2 = _rows(campaign / "scores_tier2.jsonl")
    if not tier2:
        verdict.update(status="not yet testable",
                       detail="no scores_tier2.jsonl: the tier-2 stage has "
                              "not been scored")
        return verdict

    tier1 = {row["pair_id"]: row for row in _rows(campaign / "scores.jsonl")}
    paired = []
    for row in tier2:
        base = tier1.get(row.get("pair_id"))
        if not base or base.get("tier") != layers.ROC_ARM:
            continue
        label = base.get("peptide_label")
        if label not in layers.ROC_LABELS:
            continue
        if row.get("delta_iptm") is None or base.get("delta_iptm") is None:
            continue
        paired.append((label, base["delta_iptm"], row["delta_iptm"]))

    # Both classes present, rather than a minimum count. An AUC needs at
    # least one of each and a count would be a cutoff deciding when the
    # prediction becomes scoreable, which is the sort of number that belongs
    # in config or nowhere.
    labels = {row[0] for row in paired}
    if labels != set(layers.ROC_LABELS):
        verdict.update(status="not yet testable",
                       detail=f"{len(paired)} refined Sievers pair(s) carry "
                              f"both tiers' delta, covering {sorted(labels)}: "
                              "an AUC needs both classes")
        return verdict

    def auc(index: int) -> float:
        positives = [row[index] for row in paired if row[0] == "degraded"]
        negatives = [row[index] for row in paired if row[0] == "not_degraded"]
        return layers._auc(positives, negatives)

    before, after = auc(1), auc(2)
    move = after - before
    verdict.update(
        status=("WRONG" if abs(move) > F251_MOVE else "supported"),
        pairs=len(paired),
        tier1_auc=round(before, 4), tier2_auc=round(after, 4),
        move=round(move, 4),
        detail=("paired over the same pairs, direction only: these are the "
                "top decile and not a matched subset, so this is not an "
                "estimate of the arm's AUC"))
    return verdict


def f252_design_scan_position(campaign: Path | None) -> dict:
    """Is the most sensitive scan position one that touches CRBN?"""
    verdict = {"finding": "F252",
               "claim": f"most_sensitive falls in {F252_SUPPORTED}",
               "falsifier": f"it falls in {F252_REFUTED}, which touch CRBN "
                            "not at all"}
    if campaign is None:
        verdict.update(status="not yet testable",
                       detail="no design campaign on disk")
        return verdict
    profile = campaign / "scan_profile.json"
    if not profile.exists():
        verdict.update(status="not yet testable",
                       detail=f"no scan_profile.json in {campaign.name}: the "
                              "scan has not run and been scored")
        return verdict
    payload = json.loads(profile.read_text())
    most = (payload.get("most_sensitive") or {})
    position = most.get("position")
    if position is None:
        verdict.update(status="not yet testable",
                       detail="the profile names no most_sensitive position")
        return verdict
    verdict.update(
        position=position, substitution=most.get("substitution"),
        lift=most.get("lift"),
        status=("supported" if position in F252_SUPPORTED
                else "WRONG" if position in F252_REFUTED
                else "unclear"),
        detail=("positions 5, 6 and 7 carry four or more CRBN contacts in the "
                "deposition; 1, 2 and 12 to 15 carry none"))
    return verdict


def f253_tier_b_bridging(campaign: Path | None) -> dict:
    """Does any Tier B pair bridge where its own scramble does not?"""
    verdict = {"finding": "F253",
               "claim": "no pair clears the bridging line",
               "falsifier": (f"a positive bridges in >= {F253_POSITIVE_SEEDS} "
                             f"of {F253_SEEDS} seeds while its own scramble "
                             f"bridges in <= {F253_SCRAMBLE_SEEDS}")}
    if campaign is None:
        verdict.update(status="not yet testable",
                       detail="no Tier B campaign on disk")
        return verdict
    rows = _rows(campaign / "scores.jsonl")
    if not rows:
        verdict.update(status="not yet testable",
                       detail=f"{campaign.name} has no scores.jsonl: the arm "
                              "has not run and been scored")
        return verdict

    with_bridge = {row["pair_id"]: row.get("bridging_seeds_with_bridge")
                   for row in rows}
    hits, unpaired = [], 0
    for pair_id, count in sorted(with_bridge.items()):
        if not pair_id.startswith("tb_pos_") or count is None:
            continue
        scramble = with_bridge.get("tb_neg_" + pair_id[len("tb_pos_"):])
        if scramble is None:
            unpaired += 1
            continue
        if count >= F253_POSITIVE_SEEDS and scramble <= F253_SCRAMBLE_SEEDS:
            hits.append({"pair_id": pair_id, "positive_seeds": count,
                         "scramble_seeds": scramble})
    verdict.update(
        status="supported" if not hits else "WRONG",
        hits=hits, positives_compared=sum(
            1 for p in with_bridge if p.startswith("tb_pos_")),
        unpaired=unpaired,
        detail=("each positive against its own scramble, which controls "
                "composition where the arm does not. A single hit carries its "
                "denominator: 77 positives is 77 chances"))
    return verdict


def main(argv: list[str] | None = None) -> int:
    import argparse
    import glob

    parser = argparse.ArgumentParser(description="Score F251, F252 and F253.")
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--brief", action="store_true",
                        help="one line per prediction, for tools/status.sh")
    args = parser.parse_args(argv)

    main_campaign = Path(args.campaign) if args.campaign else None
    if main_campaign is None:
        found = sorted(glob.glob("campaigns/campaign_*"))
        main_campaign = Path(found[-1]) if found else None
    design = sorted(glob.glob("campaigns/design_*"))
    tier_b = sorted(glob.glob("campaigns/tier_b_*"))

    results = [
        f251_refinement_discrimination(main_campaign) if main_campaign
        else {"finding": "F251", "status": "not yet testable",
              "detail": "no campaign on disk"},
        f252_design_scan_position(Path(design[-1]) if design else None),
        f253_tier_b_bridging(Path(tier_b[-1]) if tier_b else None),
    ]
    scored = [r for r in results if r["status"] in ("supported", "WRONG",
                                                    "unclear")]
    wrong = [r for r in scored if r["status"] == "WRONG"]
    if args.brief:
        # A status command is scanned, not read. The claim and the falsifier
        # are the same every time once they are registered, so they stay in
        # the full output and the summary carries only what changes.
        print(f"   {len(results)} recorded, {len(scored)} testable, "
              f"{len(wrong)} wrong")
        for row in results:
            note = row["status"]
            if row["status"] == "not yet testable":
                note += f": {row['detail'].split(':')[0]}"
            print(f"   {row['finding']:6} {note}")
        return 1 if wrong else 0

    print(f"registered predictions: {len(results)} recorded, {len(scored)} "
          f"testable, {len(wrong)} wrong\n")
    for row in results:
        print(f"  {row['finding']}  {row['status']}")
        print(f"      claim:     {row['claim']}" if "claim" in row else "")
        if "falsifier" in row:
            print(f"      falsifier: {row['falsifier']}")
        for key in ("pairs", "tier1_auc", "tier2_auc", "move", "position",
                    "substitution", "lift", "hits", "positives_compared",
                    "unpaired"):
            if key in row:
                print(f"      {key}: {json.dumps(row[key])}")
        print(f"      {row['detail']}\n")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
