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


# The folds and the estimate live in `nobble/score/weights.py`, which owns
# the fit, so the scorer writes the figure into `weights.json` and the About
# page can print it beside the in-sample one. This file reports it at a
# chosen fold count and shows the per-fold spread, which the panel has no
# room for. One spelling of the arithmetic, or the figure a reader sees and
# the figure this prints could differ (F312).
folds = W._folds


def crossval(rows: list[dict], k: int) -> dict:
    labelled = [(row, W._label(row)) for row in rows if W._label(row)]
    if not labelled:
        return {"status": "no labelled pairs"}

    in_sample = W.fit_rows([row for row, _ in labelled])
    if in_sample.status != "fitted":
        return {"status": f"the full fit refused: {in_sample.status}"}

    estimate = W.cross_validate([row for row, _ in labelled], k)
    if estimate.get("auc") is None:
        return {"status": estimate.get("status", "not computed")}

    return {
        "status": "measured",
        "folds": estimate["folds"],
        "labelled_pairs": len(labelled),
        "in_sample_auc": in_sample.objective,
        "in_sample_weights": in_sample.weights,
        "out_of_sample_auc": estimate["auc"],
        "held_out_positives": estimate["held_out_positives"],
        "held_out_negatives": estimate["held_out_negatives"],
        "per_fold": [
            {**fold, "auc_on_this_fold": fold.get("auc"),
             "in_sample_objective": fold.get("its_own_in_sample")}
            for fold in estimate["per_fold"]],
        "optimism": (round(in_sample.objective - estimate["auc"], 4)
                     if in_sample.objective is not None else None),
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
