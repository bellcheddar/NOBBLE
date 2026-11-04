"""Score the F13 predictions against the data, mechanically.

F13 recorded what F6 predicts for CDK12 and RBM39 before either pair ran,
with explicit falsifiers. Evaluating that by reading the numbers and
deciding is exactly the step where a prediction quietly becomes a
description: the thresholds move a little, the wording softens, and
nothing was ever really at stake.

So the thresholds live here, taken verbatim from F13, and the verdict is
whatever they produce. One of the two has already failed (F18), which is
the point: a scorer that cannot return "wrong" is not scoring anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Transcribed from FINDINGS.md F13, recorded before either pair ran.
PREDICTIONS = {
    "CDK12": {
        "claim": "improves substantially: a 15-mer of a kinase domain is the "
                 "clearest case of a fragment that cannot fold",
        "falsified_if": "corrected median RMSD stays above 20 A",
        "passes_if": lambda base, corr: corr <= 20.0 and (base - corr) > 2.0,
        "falsified": lambda base, corr: corr > 20.0,
        # The corrected medians that would support the claim, as a closed
        # interval. Declared here with the thresholds it derives from, so the
        # margin below is computed from F13 rather than judged after the fact.
        "supported_interval": lambda base: (0.0, min(20.0, base - 2.0)),
    },
    "RBM39": {
        "claim": "changes little in either direction: at 6.08 A the 15-mer was "
                 "already roughly right",
        "falsified_if": "it moves by more than 2 A in either direction, or gets "
                        "materially worse",
        "passes_if": lambda base, corr: abs(base - corr) <= 2.0,
        "falsified": lambda base, corr: abs(base - corr) > 2.0,
        "supported_interval": lambda base: (base - 2.0, base + 2.0),
    },
}


def evaluate(baseline: Path, corrected: Path) -> dict:
    from nobble.validate import compare

    report = compare.compare(baseline, corrected)
    by_gene = {c["gene"]: c for c in report["comparisons"]}

    out = []
    for gene, spec in PREDICTIONS.items():
        pair = by_gene.get(gene)
        base = (pair or {}).get("baseline_median_rmsd")
        corr = (pair or {}).get("corrected_median_rmsd")
        if base is None or corr is None:
            out.append({
                "gene": gene, "claim": spec["claim"],
                "verdict": "not yet testable",
                "detail": "the pair has not finished in both campaigns",
                "baseline_rmsd": base, "corrected_rmsd": corr,
            })
            continue
        falsified = spec["falsified"](base, corr)
        passed = spec["passes_if"](base, corr)

        # A verdict on a pair that is still running is a verdict on a moving
        # number. The two campaigns were built with the same seed structure,
        # so the complete baseline is the yardstick for whether the corrected
        # side has finished: no extra configuration, and nothing to keep in
        # step by hand.
        baseline_poses = pair.get("baseline_poses") or 0
        corrected_poses = pair.get("corrected_poses") or 0
        provisional = corrected_poses < baseline_poses

        # How far the corrected median would have to move to change the
        # verdict. This is what says whether a provisional verdict is worth
        # anything: "WRONG on 6 of 10 poses" means little on its own and a
        # great deal once the distance to the nearest supporting value is
        # larger than the spread the remaining poses could produce.
        low, high = spec["supported_interval"](base)
        if corr < low:
            margin = low - corr
        elif corr > high:
            margin = corr - high
        else:
            margin = 0.0

        out.append({
            "gene": gene, "claim": spec["claim"],
            "falsified_if": spec["falsified_if"],
            "verdict": "WRONG" if falsified else ("supported" if passed else "unclear"),
            "provisional": provisional,
            "baseline_rmsd": base, "corrected_rmsd": corr,
            "change": round(corr - base, 3),
            "baseline_poses": baseline_poses,
            "corrected_poses": corrected_poses,
            "supported_if_corrected_in": [round(low, 3), round(high, 3)],
            "margin_to_flip": round(margin, 3),
            "bridged": f"{pair.get('baseline_bridged')} -> {pair.get('corrected_bridged')}",
        })

    tested = [r for r in out if r["verdict"] != "not yet testable"]
    return {
        "recorded_in": "FINDINGS.md F13, before either pair ran",
        "predictions": out,
        "tested": len(tested),
        "wrong": sum(1 for r in tested if r["verdict"] == "WRONG"),
        "supported": sum(1 for r in tested if r["verdict"] == "supported"),
        # The third verdict. `evaluate` can return "unclear" for a pair that
        # is neither falsified nor inside its supported interval, and the
        # summary counted the other two, so `tested` could exceed
        # supported + wrong with nothing saying which prediction was
        # unaccounted for. It adds up today, 1 and 1 of 2, and would not the
        # first time a prediction landed in between (F121).
        "unclear": sum(1 for r in tested if r["verdict"] == "unclear"),
        "provisional": sum(1 for r in tested if r.get("provisional")),
        "final": sum(1 for r in tested if not r.get("provisional")),
    }


def main() -> int:
    import argparse
    import glob

    parser = argparse.ArgumentParser(description="Score the F13 predictions.")
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--corrected", default=None)
    args = parser.parse_args()

    baseline = Path(args.baseline or sorted(glob.glob("campaigns/benchmark_*"))[-1])
    corrected = Path(args.corrected or sorted(glob.glob("campaigns/corrected_*"))[-1])
    result = evaluate(baseline, corrected)

    # Every tested prediction appears in exactly one of the three counts, so
    # the sentence accounts for the number it opens with.
    assert result["tested"] == (result["supported"] + result["wrong"]
                                + result["unclear"]), result
    print(f"F13 predictions, {result['tested']} testable "
          f"({result['final']} final, {result['provisional']} provisional), "
          f"{result['supported']} supported, {result['wrong']} wrong, "
          f"{result['unclear']} unclear\n")
    for row in result["predictions"]:
        tag = " (PROVISIONAL)" if row.get("provisional") else ""
        print(f"  {row['gene']:8s} {row['verdict']}{tag}")
        print(f"           predicted: {row['claim']}")
        if row.get("change") is not None:
            print(f"           measured:  {row['baseline_rmsd']} -> "
                  f"{row['corrected_rmsd']} A ({row['change']:+.3f}), "
                  f"bridged {row['bridged']}")
            print(f"           poses:     {row['corrected_poses']} of "
                  f"{row['baseline_poses']} the baseline has")
            low, high = row["supported_if_corrected_in"]
            if row["margin_to_flip"]:
                print(f"           to change the verdict the corrected median "
                      f"would have to reach {low}-{high} A, "
                      f"{row['margin_to_flip']} A away")
            else:
                print(f"           sits inside the supporting range {low}-{high} A")
        else:
            print(f"           {row['detail']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
