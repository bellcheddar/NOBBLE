"""Each parent against its own scramble, paired, which nothing had done.

A scramble shares its parent's receptor, its glue, its seeds and its
amino-acid composition, and differs only in the order of the peptide. So the
comparison between a pair and its scramble isolates the sequence, and it is
paired: 31 pairs on this campaign, every one with its parent also scored.

Every other test in the project is unpaired. `matched_control_roc` ranks
degraded against matched non-degraded across the Sievers arm, and the
composite fit pools benchmark, Sievers and scramble rows as one labelled
set. Both have to carry variation between receptors and glues that this
design removes by construction, which is why a statistic can fail there and
pass here without either result being wrong.

The test is a two-sided exact sign test on P(parent > scramble) = 0.5.
Assumption-free, ignores magnitude, and ties are excluded from the
denominator rather than split, so a statistic with many ties is tested on
fewer comparisons and the output says how many.

**What beating a scramble does and does not show.** A scramble destroys the
motif while keeping the composition, so beating it is necessary for a
statistic that reads the degron and nowhere near sufficient. The harder
question is whether a statistic separates a degraded sequence from a natural
non-degraded one, which is what the Sievers arm asks and where Delta-ipTM
fails. A statistic can tell a motif from noise and still not tell one
natural sequence from another.

Writes nothing.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths                                   # noqa: E402
from nobble.execute.campaign import latest                 # noqa: E402
from nobble.score import weights as W                      # noqa: E402

SCRAMBLE_PREFIX = "scr_"


def sign_test(wins: int, trials: int) -> float | None:
    """Two-sided exact binomial p at 0.5, or None with nothing to test.

    Summed from the smaller tail and doubled, which is the standard
    two-sided convention for a symmetric null and exact rather than
    approximated: 31 comparisons is not a regime for a normal approximation,
    and the tails are what the answer turns on.
    """
    if trials <= 0:
        return None
    smaller = min(wins, trials - wins)
    tail = sum(math.comb(trials, k) for k in range(smaller + 1))
    return min(1.0, 2 * tail / 2 ** trials)


def pairs_of(rows: dict) -> list[tuple[str, str]]:
    """(parent, scramble) for every scramble whose parent is also scored."""
    return sorted((name[len(SCRAMBLE_PREFIX):], name) for name in rows
                  if name.startswith(SCRAMBLE_PREFIX)
                  and name[len(SCRAMBLE_PREFIX):] in rows)


def value_of(row: dict, statistic: str):
    if statistic == "composite":
        return row.get("nobble_score")
    return W._features(row).get(statistic)


def compare(rows: dict, statistic: str) -> dict:
    pairs = pairs_of(rows)
    wins = losses = ties = 0
    absent = 0
    for parent, scramble in pairs:
        a = value_of(rows[parent], statistic)
        b = value_of(rows[scramble], statistic)
        if a is None or b is None:
            absent += 1
            continue
        if a > b:
            wins += 1
        elif a < b:
            losses += 1
        else:
            ties += 1
    trials = wins + losses
    return {
        "statistic": statistic,
        "pairs": len(pairs),
        "parent_higher": wins,
        "scramble_higher": losses,
        "tied": ties,
        "one_side_absent": absent,
        "compared": trials,
        "p_two_sided": (round(value, 5)
                        if (value := sign_test(wins, trials)) is not None
                        else None),
        "direction": ("parent" if wins > losses else
                      "scramble" if losses > wins else "neither"),
    }


def report(rows: dict) -> dict:
    statistics = list(W.CANDIDATES) + ["composite"]
    results = [compare(rows, name) for name in statistics]
    tested = [row for row in results if row["p_two_sided"] is not None]
    # The family, stated rather than left to the reader. Six tests at 0.05
    # give a 26 per cent chance of at least one crossing by luck, which is
    # the same arithmetic F280 did for seven.
    family = len(tested)
    return {
        "pairs": results[0]["pairs"] if results else 0,
        "statistics_tested": family,
        "any_one_crossing_by_chance": (round(1 - 0.95 ** family, 3)
                                       if family else None),
        "bonferroni_threshold": (round(0.05 / family, 5) if family else None),
        "results": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    campaign = (Path(args.campaign) if args.campaign
                else latest("campaign") or latest("benchmark"))
    if campaign is None or not (campaign / "scores.jsonl").exists():
        print("no scored campaign", file=sys.stderr)
        return 2

    rows = {row["pair_id"]: row for row
            in paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
            if row.get("pair_id")}
    out = report(rows)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print(f"{campaign.name}: {out['pairs']} parent/scramble pair(s), paired "
          "sign test")
    print(f"  {out['statistics_tested']} statistics tested, so the chance of "
          f"at least one crossing 0.05 by luck is "
          f"{out['any_one_crossing_by_chance']}, and the Bonferroni "
          f"threshold is {out['bonferroni_threshold']}")
    print()
    print(f"  {'statistic':32s} {'parent':>7s} {'scram':>6s} {'tied':>5s} "
          f"{'p':>8s}  direction")
    for row in out["results"]:
        p = "-" if row["p_two_sided"] is None else f"{row['p_two_sided']:.5f}"
        mark = ""
        if (row["p_two_sided"] is not None
                and row["p_two_sided"] < out["bonferroni_threshold"]):
            mark = "  survives the correction"
        print(f"  {row['statistic']:32s} {row['parent_higher']:7d} "
              f"{row['scramble_higher']:6d} {row['tied']:5d} {p:>8s}  "
              f"{row['direction']}{mark}")
    print()
    print("  A scramble keeps the composition and destroys the motif, so")
    print("  beating it is necessary and nowhere near sufficient. Whether a")
    print("  statistic separates a degraded sequence from a natural")
    print("  non-degraded one is what the Sievers arm asks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
