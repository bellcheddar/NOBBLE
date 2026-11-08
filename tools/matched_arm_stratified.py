"""The Sievers arm as the matched design it is, not as a pooled split.

`nobble/curate/peptides.py` is explicit about why that arm exists: "the whole
value of this set is that its negatives came out of the same screen as its
positives", and "every one of the 32 positives is kept, and each is paired
with the `negatives_per_positive` non-degraded zinc fingers closest to it in
length and amino-acid composition". Each control inherits its positive's
drug, so the comparison is within-drug, and each records
`parent_peptide_id`.

Spec 5.3's `matched_control_roc` then pools all of them and takes one AUC
over 24 positives against 96 negatives, which throws the matching away. A
positive that outranks its own four composition-matched, length-matched,
same-drug controls is a different and much better-controlled claim than one
that outranks the pooled 96.

**Why this has to join a manifest.** The pairing does not reach
`scores.jsonl`. `data/manifests/library.jsonl` carries
`parent_peptide_id` on all 96 matched negatives; the campaign assembler does
not copy it into the queue, so the score rows carry the key with a value of
None. A reader of the scores alone would conclude there is no pairing, which
is the F285 error: absent data read as a measured zero.

The statistic is a within-block AUC. For each positive, the fraction of its
own matched controls it outranks, ties at a half. Reported as the mean over
blocks, and tested at the block level with an exact sign test on how many
blocks exceed 0.5: 24 blocks are the independent units, and a test over the
96 comparisons would treat four comparisons sharing a positive as four
independent facts.

**The composite is scored twice, in sample and held out.** It was fitted on
these pairs (F312), so its in-sample figure here is the same optimism in a
different slicing. The held-out score comes from the fold that did not see
the pair, through `weights.cross_validate`'s own fold assignment.

Writes nothing.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths                                   # noqa: E402
from nobble.execute.campaign import latest                 # noqa: E402
from nobble.score import weights as W                      # noqa: E402

LIBRARY = Path("data/manifests/library.jsonl")


def sign_test(wins: int, trials: int) -> float | None:
    if trials <= 0:
        return None
    smaller = min(wins, trials - wins)
    tail = sum(math.comb(trials, k) for k in range(smaller + 1))
    return min(1.0, 2 * tail / 2 ** trials)


def blocks_of(rows: dict, source: str = "sievers_zf") -> dict[str, list[str]]:
    """positive peptide id -> its matched control peptide ids."""
    if not LIBRARY.exists():
        return {}
    blocks: dict[str, list[str]] = defaultdict(list)
    for entry in paths.read_jsonl(LIBRARY, tolerate_torn=True):
        if entry.get("source") != source:
            continue
        parent = entry.get("parent_peptide_id")
        child = entry.get("peptide_id")
        if parent and child and parent in rows and child in rows:
            blocks[parent].append(child)
    return dict(blocks)


def held_out_composite(rows: list[dict], folds: int = 5) -> dict[str, float]:
    """Composite score for each labelled row from the fold that excluded it."""
    labelled = [(row, W._label(row)) for row in rows if W._label(row)]
    out: dict[str, float] = {}
    for fold in W._folds(labelled, folds):
        held = set(fold)
        train = [row for index, (row, _side) in enumerate(labelled)
                 if index not in held]
        fitted = W.fit_rows(train)
        if fitted.status != "fitted":
            continue
        for index in fold:
            row, _side = labelled[index]
            score = W.apply(row, fitted.weights)
            if score is not None and row.get("peptide_id"):
                out[row["peptide_id"]] = score
    return out


def within_block(blocks: dict, read) -> dict:
    """Mean within-block AUC and a block-level sign test."""
    per_block = []
    for positive, controls in sorted(blocks.items()):
        value = read(positive)
        if value is None:
            continue
        wins = ties = compared = 0
        for control in controls:
            other = read(control)
            if other is None:
                continue
            compared += 1
            if value > other:
                wins += 1
            elif value == other:
                ties += 1
        if compared:
            per_block.append((wins + 0.5 * ties) / compared)
    above = sum(1 for value in per_block if value > 0.5)
    below = sum(1 for value in per_block if value < 0.5)
    return {
        "blocks": len(per_block),
        "mean_within_block_auc": (round(sum(per_block) / len(per_block), 4)
                                  if per_block else None),
        "blocks_above_half": above,
        "blocks_below_half": below,
        "p_two_sided": (round(value, 5)
                        if (value := sign_test(above, above + below)) is not None
                        else None),
    }


def report(rows: list[dict], folds: int = 5) -> dict:
    by_peptide = {row["peptide_id"]: row for row in rows
                  if row.get("peptide_id")}
    blocks = blocks_of(by_peptide)
    if not blocks:
        return {"status": "no matched blocks: the library manifest carries no "
                          "parent_peptide_id for this arm"}
    held = held_out_composite(rows, folds)

    def reader(statistic):
        if statistic == "composite, held out":
            return lambda pid: held.get(pid)
        if statistic == "composite, in sample":
            return lambda pid: by_peptide[pid].get("nobble_score")
        return lambda pid: W._features(by_peptide[pid]).get(statistic)

    names = list(W.CANDIDATES) + ["composite, in sample", "composite, held out"]
    results = [{"statistic": name, **within_block(blocks, reader(name))}
               for name in names]
    unfitted = [row for row in results
                if not row["statistic"].startswith("composite")]
    return {
        "status": "measured",
        "blocks": len(blocks),
        "controls_per_block": sorted({len(v) for v in blocks.values()}),
        "statistics_tested": len(results),
        "bonferroni_threshold": round(0.05 / len(results), 5) if results else None,
        "unfitted_statistics": len(unfitted),
        "results": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    campaign = (Path(args.campaign) if args.campaign
                else latest("campaign") or latest("benchmark"))
    if campaign is None or not (campaign / "scores.jsonl").exists():
        print("no scored campaign", file=sys.stderr)
        return 2
    rows = paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
    out = report(rows, args.folds)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    if out["status"] != "measured":
        print(out["status"])
        return 1

    print(f"{campaign.name}: {out['blocks']} matched block(s), "
          f"{out['controls_per_block']} control(s) each")
    print(f"  {out['statistics_tested']} statistics, Bonferroni threshold "
          f"{out['bonferroni_threshold']}")
    print()
    print(f"  {'statistic':30s} {'blocks':>6s} {'mean AUC':>9s} "
          f"{'above':>7s} {'p':>8s}")
    for row in out["results"]:
        p = "-" if row["p_two_sided"] is None else f"{row['p_two_sided']:.5f}"
        auc = "-" if row["mean_within_block_auc"] is None else \
            f"{row['mean_within_block_auc']:.4f}"
        above = f"{row['blocks_above_half']}/{row['blocks_above_half'] + row['blocks_below_half']}"
        print(f"  {row['statistic']:30s} {row['blocks']:6d} {auc:>9s} "
              f"{above:>7s} {p:>8s}")
    print()
    print("  Each positive against its own four composition-matched,")
    print("  length-matched, same-drug controls. The composite was fitted on")
    print("  these pairs, so read its held-out row and not its in-sample one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
