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
from nobble import numeric as _numeric                      # noqa: E402
from nobble.score import weights as W                      # noqa: E402

LIBRARY = Path("data/manifests/library.jsonl")


# `sign_test` lives in `nobble/numeric.py`, beside the project's other
# hand-computed statistic. Two copies of one exact binomial is F154's
# shape, and I wrote them an hour apart (F326).
sign_test = _numeric.sign_test
rounded_p = _numeric.rounded_p
# The switch point below which a p is shown in significant figures, from
# the same config value `rounded_p` rounds to, so the stored figure and the
# printed one cannot disagree (F350).
_P_PLACES = int(paths.thresholds()["scoring"]["p_report_places"])


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
        # `rounded_p`, for the reason in its docstring: `round(p, 5)` is
        # 0.0 for anything below 1e-5, and the sibling scramble tool stored
        # exactly that for its strongest result (F350). This arm's smallest
        # p is 0.0043 today, so the bug has not bitten here; fixed anyway,
        # because the next block added could take it below the line and the
        # failure is silent.
        "p_two_sided": rounded_p(sign_test(above, above + below)),
    }


def _per_block(blocks: dict, read) -> dict[str, float]:
    """Each block's own AUC, keyed by its positive.

    `within_block` computes these and returns only their mean and a sign
    test over them. A comparison between two statistics needs them kept,
    because both are measured on the same blocks and that is the whole
    information the matching provides (F317, F351).
    """
    out: dict[str, float] = {}
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
            out[positive] = (wins + 0.5 * ties) / compared
    return out


def _composite_against_best(blocks: dict, readers: dict, results: list[dict]):
    """The composite against the best unfitted component, block by block.

    Whether the composite earns its place is a standing question, and the
    means invite the wrong answer: held out it sits 0.036 below
    `convergence_score`, which reads as losing. Paired over the same blocks
    it is 8 to 8 with 8 ties, p = 1.0, so the gap is not a difference these
    blocks support (F351).

    Reported here rather than worked out by each consumer, for the reason
    `_power` is here: two copies of a sign-test comparison would be the
    duplication D-NOB-007 forbids, and the hold and `about.json` would then
    agree only by luck.
    """
    unfitted = [row for row in results
                if not str(row.get("statistic", "")).startswith("composite")
                and row.get("mean_within_block_auc") is not None]
    if not unfitted:
        return None
    best = max(unfitted, key=lambda row: row["mean_within_block_auc"])
    name = best["statistic"]
    if name not in readers or "composite, held out" not in readers:
        return None
    mine = _per_block(blocks, readers[name])
    theirs = _per_block(blocks, readers["composite, held out"])
    shared = sorted(set(mine) & set(theirs))
    if not shared:
        return None
    component = sum(1 for key in shared if mine[key] > theirs[key])
    composite = sum(1 for key in shared if mine[key] < theirs[key])
    return {
        "component": name,
        "blocks_compared": len(shared),
        "component_higher": component,
        "composite_higher": composite,
        "tied": len(shared) - component - composite,
        "p_two_sided": rounded_p(sign_test(component, component + composite)),
        "component_mean_auc": best["mean_within_block_auc"],
        "composite_mean_auc": next(
            (row["mean_within_block_auc"] for row in results
             if row.get("statistic") == "composite, held out"), None),
    }


def _power(results: list[dict], threshold: float | None) -> dict | None:
    """How many decisive blocks this arm would need, against what it has.

    F349 measured it and F350 printed it in the publication hold, which
    computed it there. Two copies of a sign-test inversion is D-NOB-007's
    subject and F154's shape, so it lives here with the arm it describes
    and both the hold and `about.json` read it: the atlas already publishes
    this whole report.

    Taken from the best **unfitted** rate, because the in-sample composite
    has the highest by construction and reading it made the hold's first
    version report that the arm was adequately powered (F350).

    `None` where there is no rate to size against, rather than a figure
    over nothing: a statistic above a half in half its blocks or fewer says
    the arm is not underpowered for it, it is simply not there.
    """
    if not results or threshold is None:
        return None
    rows = []
    for row in results:
        decisive = ((row.get("blocks_above_half") or 0)
                    + (row.get("blocks_below_half") or 0))
        if not decisive or row.get("blocks_above_half") is None:
            continue
        if str(row.get("statistic", "")).startswith("composite"):
            continue
        if row.get("mean_within_block_auc") is None:
            continue
        rows.append((row["blocks_above_half"] / decisive, decisive, row))
    if not rows:
        return None
    # By AUC, not by rate (F350d). Chosen by rate this picked
    # `lysine_reach_exposed_fraction` at 13 of 17, and the app's own tooltip
    # says that statistic is "at or below chance" on 369 independently
    # assayed lysines, so its rate over 17 decisive blocks is most likely
    # noise and using it as the favourable case overstates the arm's
    # prospects. It also disagreed with the README, which took
    # `convergence_score`: 27 blocks needed against 48, a factor of 1.8 on
    # the same claim in two documents.
    #
    # An AUC over every block is also a less noisy quantity than a rate over
    # the decisive ones, and `convergence_score` is the statistic with a
    # mechanism (F342) and its confound measured (F344).
    rate, decisive, best = max(
        rows, key=lambda item: item[2]["mean_within_block_auc"])
    if rate <= 0.5:
        return {"status": "no unfitted statistic is above a half in more "
                          "than half of its blocks, so there is no rate to "
                          "size the arm against"}
    needed = next((n for n in range(decisive, 1000)
                   if (value := sign_test(round(rate * n), n)) is not None
                   and value < threshold), None)
    if needed is None:
        return None
    return {
        "statistic": best["statistic"],
        "blocks_above_half": best["blocks_above_half"],
        "decisive": decisive,
        "needed_decisive": needed,
        "threshold": threshold,
        # The hard ceiling, which is why this is a design limit rather than
        # a budget one: the screen holds 32 degraded zinc fingers and eight
        # are significant only for CC-122 or CC-220, which have no CCD code
        # and no curated SMILES, so there is no drug structure to model.
        "positives_in_screen": 32,
        "positives_modellable": 24,
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
    readers = {name: reader(name) for name in names}
    results = [{"statistic": name, **within_block(blocks, readers[name])}
               for name in names]
    unfitted = [row for row in results
                if not row["statistic"].startswith("composite")]
    return {
        "status": "measured",
        "blocks": len(blocks),
        "controls_per_block": sorted({len(v) for v in blocks.values()}),
        "statistics_tested": len(results),
        "power": _power(results, round(0.05 / len(results), 5) if results
                        else None),
        "composite_against_best": _composite_against_best(
            blocks, readers, results),
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
        # `.3g` below 1e-5, so a small p is not printed as 0.00000 from a
        # correct stored value, which is the second half of F350.
        p = ("-" if row["p_two_sided"] is None
             else f"{row['p_two_sided']:.5f}"
             if row["p_two_sided"] >= 10.0 ** -_P_PLACES
             else f"{row['p_two_sided']:.3g}")
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
