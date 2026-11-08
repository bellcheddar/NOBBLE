"""An out-of-sample estimate for the composite, which it has never had.

`nobble/score/weights.py` reports its objective as in-sample and says so in a
caveat on the fit itself, which is right. It then says "The matched-control
ROC is the held-out measurement". **That is true of `delta_iptm` and false of
the composite.** `_label` is deliberately not scoped to one arm, because spec
4.8 fits the weights on the benchmark panel and the Sievers matched set, so
the Sievers pairs are in the fit; spec 5.3 scopes the ROC to the Sievers
split, which is therefore inside the fit's own training data. A raw statistic
is held out from a fit it took no part in. A fitted composite is not.

So the project has an in-sample figure, a correct caveat saying it is
in-sample, and nothing to compare it with. This computes the comparison.

Stratified k-fold over the labelled pairs. Each fold refits through
`weights.fit_rows`, the same grid search the campaign runs, and scores only
the pairs it did not see. The held-out scores are pooled and one AUC is taken
over them.

Folds are dealt deterministically: sorted by pair id, then round robin within
each label. No seed to record and no run-to-run variation, which matters for
a number that will be quoted next to the in-sample one.

**What a pooled cross-validated AUC is and is not.** The held-out scores come
from different weight vectors, one per fold, so this estimates the
performance of the *procedure* rather than of any single weighting. That is
the right question for a grid search over five weights on 31 positives, where
the procedure's optimism is the thing at issue. It is not a confidence
interval and it is not an estimate for the published weights, which were fitted
on everything.

Writes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths                                   # noqa: E402
from nobble.execute.campaign import latest                 # noqa: E402
from nobble.score import weights as W                      # noqa: E402


def folds(labelled: list[tuple[dict, str]], k: int) -> list[list[int]]:
    """Stratified, deterministic fold assignment.

    Round robin within each label after sorting by pair id, so each fold gets
    as even a share of the 31 positives as the arithmetic allows. A random
    split would put a number next to the in-sample one that moves between
    runs, and the first question anyone asks of a cross-validated figure is
    whether it is stable.
    """
    assignment = [0] * len(labelled)
    for side in ("positive", "negative"):
        members = sorted(
            (index for index, (_row, label) in enumerate(labelled)
             if label == side),
            key=lambda index: str(labelled[index][0].get("pair_id") or index))
        for position, index in enumerate(members):
            assignment[index] = position % k
    return [[index for index, fold in enumerate(assignment) if fold == f]
            for f in range(k)]


def crossval(rows: list[dict], k: int) -> dict:
    labelled = [(row, W._label(row)) for row in rows if W._label(row)]
    if not labelled:
        return {"status": "no labelled pairs"}

    in_sample = W.fit_rows([row for row, _ in labelled])
    if in_sample.status != "fitted":
        return {"status": f"the full fit refused: {in_sample.status}"}

    k = min(k, sum(1 for _, side in labelled if side == "positive"))
    held_positive: list[float] = []
    held_negative: list[float] = []
    per_fold = []
    for number, held in enumerate(folds(labelled, k), start=1):
        held_set = set(held)
        train = [row for index, (row, _) in enumerate(labelled)
                 if index not in held_set]
        fitted = W.fit_rows(train)
        if fitted.status != "fitted":
            per_fold.append({"fold": number, "status": fitted.status,
                             "held_out": len(held)})
            continue
        fold_positive, fold_negative = [], []
        for index in held:
            row, side = labelled[index]
            score = W.apply(row, fitted.weights)
            if score is None:
                continue
            (fold_positive if side == "positive" else fold_negative).append(score)
        held_positive.extend(fold_positive)
        held_negative.extend(fold_negative)
        per_fold.append({
            "fold": number,
            "held_out": len(held),
            "positives": len(fold_positive),
            "negatives": len(fold_negative),
            "auc_on_this_fold": (round(value, 4) if (value := W._auc(
                fold_positive, fold_negative)) is not None else None),
            "components_used": fitted.components_used,
            "weights": fitted.weights,
            "in_sample_objective": fitted.objective,
        })

    pooled = W._auc(held_positive, held_negative)
    return {
        "status": "measured",
        "folds": k,
        "labelled_pairs": len(labelled),
        "in_sample_auc": in_sample.objective,
        "in_sample_weights": in_sample.weights,
        "out_of_sample_auc": round(pooled, 4) if pooled is not None else None,
        "held_out_positives": len(held_positive),
        "held_out_negatives": len(held_negative),
        "per_fold": per_fold,
        "optimism": (round(in_sample.objective - pooled, 4)
                     if pooled is not None and in_sample.objective is not None
                     else None),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--loo", action="store_true",
                        help="leave one out, which is folds = positives")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    campaign = (Path(args.campaign) if args.campaign
                else latest("campaign") or latest("benchmark"))
    if campaign is None:
        print("no campaign assembled", file=sys.stderr)
        return 2
    scores = campaign / "scores.jsonl"
    if not scores.exists():
        print(f"{campaign.name} has no scores.jsonl", file=sys.stderr)
        return 2

    rows = paths.read_jsonl(scores, tolerate_torn=True)
    k = 10 ** 6 if args.loo else args.folds
    report = crossval(rows, k)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    if report["status"] != "measured":
        print(f"composite cross-validation: {report['status']}")
        return 1

    print(f"composite on {campaign.name}, {report['labelled_pairs']} labelled "
          f"pair(s), {report['folds']} fold(s)")
    print(f"  in sample      AUC {report['in_sample_auc']}")
    print(f"  out of sample  AUC {report['out_of_sample_auc']}  "
          f"over {report['held_out_positives']} held-out positive(s) and "
          f"{report['held_out_negatives']} negative(s)")
    print(f"  optimism       {report['optimism']}")
    print()
    print("  per fold, each fitted without the pairs it then scored")
    for fold in report["per_fold"]:
        if "auc_on_this_fold" not in fold:
            print(f"    {fold['fold']}: refused, {fold['status']}")
            continue
        print(f"    {fold['fold']}: held out {fold['positives']}+"
              f"{fold['negatives']}, AUC {fold['auc_on_this_fold']}, "
              f"its own in-sample {fold['in_sample_objective']}")
    print()
    print("  The pooled figure estimates the procedure, not the published")
    print("  weights: each held-out score comes from a different fold's fit.")
    print("  The matched-control ROC is not a held-out measurement for the")
    print("  composite, because spec 4.8 fits on the Sievers arm as well as")
    print("  the panel, so those pairs are inside the training data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
