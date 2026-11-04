"""Which measurements survive a change of sampling regime (F137).

Tier 2 re-runs the top decile's ternary jobs at 25 diffusion samples and 10
recycles against tier 1's 1 and 3. That makes some of a pair's numbers
comparable between the two runs and some of them not, and the distinction is
not about which quantity matters: it is about the shape of the statistic.

A minimum over seeds can only fall as samples are added, because the minimum
of a larger sample of the same distribution is smaller in expectation.
`iptm_min_ternary` at 25 samples beside `iptm_min_binary` at 1 is therefore
lower before anything physical has changed, and `delta_iptm`, which is their
difference, moves with it. That is D-NOB-032 and it is why scoring writes
tier 2 to its own file.

A mean, a median or a proportion has no such bias. More samples make it less
noisy, not systematically smaller. `bridge_formation_rate` is a proportion
over jobs, `bridge_percentile` is a median of percentiles, and
`convergence_score` is built from a mean pairwise RMSD. Each answers the same
question at either sampling regime.

So the comparison is a whitelist rather than a blacklist. A quantity added to
`scores.jsonl` later is withheld until someone has thought about its shape,
which is the safe default: the failure of a blacklist here is a biased number
presented as an improvement, and it would look exactly like a result.

Imports `nobble.numeric` and nothing else. The app serves a precomputed
atlas on a droplet with no scoring stack and no gemmi, so this has to be
readable from both sides, and `numeric` is pure stdlib for that reason.

`finite` rather than `isinstance(value, (int, float))`, which is what I wrote
first and what `tests/test_numeric_rule.py` rejected within the minute. That
check admits a NaN, and a NaN difference would reach the page as the literal
`NaN`, which `JSON.parse` refuses: the panel would not render at all (F130).
"""
from __future__ import annotations

from nobble.numeric import finite

# Comparable across sampling regimes, with what each is and why it survives.
COMPARABLE = {
    "bridge_formation_rate": "proportion of seeds whose glue bridged both chains",
    "bridge_percentile": "median percentile against the observed bridge envelope",
    "convergence_score": "built from the mean pairwise peptide RMSD across seeds",
    "plip_fingerprint_match": "proportion of the deposited contact set recovered",
}

# Withheld, and the reason is the same for all of them: each is a minimum
# over seeds or a difference of two such minima.
WITHHELD = {
    "delta_iptm": "a difference of two minima over seeds",
    "delta_iptm_global": "a difference of two minima over seeds",
    "delta_iptm_median": "a difference of medians of differently sampled arms",
    "iptm_min_ternary": "a minimum over seeds",
    "iptm_min_binary": "a minimum over seeds",
    "iptm_min_ternary_global": "a minimum over seeds",
    "iptm_min_binary_global": "a minimum over seeds",
    "iptm_min_ternary_conditioned": "a minimum over seeds",
    "iptm_min_ternary_unconstrained": "a minimum over seeds",
    "nobble_score": "a weighted sum that includes delta_iptm",
}

WITHHELD_NOTE = (
    "A minimum over seeds falls as diffusion samples are added, so these "
    "would differ between the two runs before anything physical had changed."
)


def compare(tier1: dict | None, tier2: dict | None) -> dict:
    """Side-by-side for the comparable quantities only.

    Either side may be absent: a pair that was never refined has no tier-2
    row, and that is the normal state rather than a gap to fill with nulls.
    """
    tier1 = tier1 or {}
    tier2 = tier2 or {}
    rows = []
    for key, what in COMPARABLE.items():
        before = tier1.get(key)
        after = tier2.get(key)
        if before is None and after is None:
            continue
        rows.append({
            "key": key,
            "what": what,
            "tier1": before,
            "tier2": after,
            # Stated rather than left to the reader's subtraction, and only
            # when both exist. Refinement is meant to improve a pose, so the
            # direction is the point.
            "change": (round(after - before, 4)
                       if finite(before) and finite(after) else None),
        })
    return {
        "rows": rows,
        "withheld": sorted(WITHHELD),
        "withheld_note": WITHHELD_NOTE,
        "refined": bool(tier2),
    }
