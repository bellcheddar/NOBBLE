"""Design lift: how much a variant moved its parent's Delta-ipTM.

    lift = delta_iptm(variant) - delta_iptm(parent)

A difference of differences. Delta-ipTM already cancels whatever the
receptor and the peptide contribute on their own; subtracting the parent's
Delta-ipTM cancels whatever the parent degron contributes, leaving the
effect of the single substitution.

That only holds if the parent and the variant were run the same way. If the
variant was co-folded with a different glue, a different receptor
construct, a different number of seeds or a different sampling tier, the
lift reports that difference instead of the substitution, and it reports it
in a plausible-looking number that nothing else flags. So the conditions are
compared explicitly and a mismatched pair returns no lift rather than a
wrong one.

This is the same rule as D-NOB-032 (sampling tiers) and D-NOB-034 (the
structural cofactor), applied one level up: a quantity defined as a
difference is interpretable only when its two terms differ in one thing.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble import paths
from nobble.numeric import finite

# The fields that must match between a variant and its parent for the
# subtraction to mean anything.
MATCHED_CONDITIONS = ("construct", "e3_gene", "ligand_key", "modality")

# Below this many seeds on either side, the minima the Delta-ipTMs are built
# from are not comparable: a minimum over two samples and a minimum over five
# are different statistics.
MINIMUM_SEEDS = int(paths.thresholds()["design"]["minimum_seeds"])
# How much of the parent's bridging rate a variant must keep before the
# bridge counts as weakened rather than merely noisier.
BRIDGE_RATE_RETAINED_MIN = float(
    paths.thresholds()["design"]["bridge_rate_retained_min"]
)


@dataclass
class Lift:
    variant_id: str
    parent_peptide_id: str
    substitution: str | None = None
    position: int | None = None
    variant_delta_iptm: float | None = None
    parent_delta_iptm: float | None = None
    lift: float | None = None
    # Bridge formation beside the lift, not inside it. F16 and F17 showed
    # this is informative and independent: it needs no crystal, and it
    # separates "the substitution weakened the interface" from "the
    # substitution stopped the glue reaching both chains at all". A scan
    # that loses the bridge has broken the ternary rather than detuned it.
    variant_bridged: str | None = None
    parent_bridged: str | None = None
    bridge_lost: bool | None = None
    bridge_rate_change: float | None = None
    bridge_weakened: bool | None = None
    # Whether either side's delta_iptm is driven by a collapsed seed.
    #
    # delta_iptm is a difference of minima, so one seed that collapses drags
    # the minimum down and inflates the difference by however far it fell.
    # The scorer detects it and sets `seed_collapse_affects_delta`, and
    # D-NOB-081 found the scan's own parent being chosen that way: ZN565 at
    # +0.8886 on a binary minimum of 0.0601 against a median of 0.8619.
    #
    # Reported rather than refused, unlike `mismatches`. A condition mismatch
    # means the two runs are not comparable and the lift would report the
    # conditions; a collapse means the lift is comparable and one of its two
    # terms is unreliable. So the number stands with a flag and
    # `scan_profile` keeps it out of the ordering, which is the same
    # treatment recovery_delta gives a confounded pair.
    collapse_affected: str | None = None
    status: str = "not_computed"
    mismatches: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _conditions(row: dict) -> dict:
    return {key: row.get(key) for key in MATCHED_CONDITIONS}


def compute(variant_row: dict, parent_row: dict) -> Lift:
    """Lift for one variant against its parent, or a refusal with the reason."""
    result = Lift(
        variant_id=variant_row.get("pair_id") or variant_row.get("variant_id", "?"),
        parent_peptide_id=parent_row.get("peptide_id", "?"),
        substitution=variant_row.get("substitution"),
        position=variant_row.get("position"),
    )

    # A substitution that changes nothing is not a variant. Its two runs
    # differ only by seed, so its "lift" is the noise floor, and nothing
    # downstream distinguishes that from a real effect: it sorts into the
    # ranking like any other number and can come out on top. The alanine
    # scan never emits one, because a position already alanine is scanned
    # to glycine, but the refusal belongs here rather than relying on every
    # future generator remembering.
    substitution = variant_row.get("substitution")
    if isinstance(substitution, str) and len(substitution) >= 3:
        if substitution[0] == substitution[-1]:
            result.status = (
                f"not_computed: {substitution} substitutes a residue for "
                "itself. The two runs differ only by seed, so the difference "
                "between them is the noise floor rather than an effect"
            )
            return result

    variant_delta = variant_row.get("delta_iptm")
    parent_delta = parent_row.get("delta_iptm")
    result.variant_delta_iptm = variant_delta
    result.parent_delta_iptm = parent_delta

    if not finite(variant_delta):
        result.status = "not_computed: the variant has no delta_iptm"
        return result
    if not finite(parent_delta):
        result.status = (
            "not_computed: the parent has no delta_iptm. A variant without its "
            "parent scored is not a design result, it is one number"
        )
        return result

    variant_conditions = _conditions(variant_row)
    parent_conditions = _conditions(parent_row)
    mismatches = [
        {"field": key, "variant": variant_conditions[key], "parent": parent_conditions[key]}
        for key in MATCHED_CONDITIONS
        if variant_conditions[key] != parent_conditions[key]
    ]

    for side, row in (("variant", variant_row), ("parent", parent_row)):
        for arm in ("seeds_binary", "seeds_ternary"):
            count = row.get(arm)
            if isinstance(count, int) and count < MINIMUM_SEEDS:
                mismatches.append({
                    "field": f"{side}.{arm}",
                    "variant": count, "parent": MINIMUM_SEEDS,
                })

    # Equal depth, not merely sufficient depth. delta_iptm is a difference of
    # minima over seeds, and a minimum is not robust to sample count, so a
    # variant scored over four seeds against a parent scored over five has a
    # systematically lower minimum before any substitution is considered.
    # Both pairs come from the same campaign with the same seed tuple, so
    # they normally match: they stop matching when a job fails, which is
    # exactly when nobody is looking at seed counts.
    for arm in ("seeds_binary", "seeds_ternary"):
        variant_count = variant_row.get(arm)
        parent_count = parent_row.get(arm)
        if (isinstance(variant_count, int) and isinstance(parent_count, int)
                and variant_count != parent_count):
            mismatches.append({
                "field": arm, "variant": variant_count, "parent": parent_count,
            })

    if mismatches:
        result.mismatches = mismatches
        result.status = (
            "not_computed: the variant and its parent were not run the same way, "
            "so the difference between them would report the conditions rather "
            "than the substitution"
        )
        return result

    result.lift = round(variant_delta - parent_delta, 4)

    sides = [side for side, row in (("variant", variant_row), ("parent", parent_row))
             if row.get("seed_collapse_affects_delta")]
    if sides:
        result.collapse_affected = " and ".join(sides)

    v_with = variant_row.get("bridging_seeds_with_bridge")
    v_total = variant_row.get("bridging_seeds_total")
    p_with = parent_row.get("bridging_seeds_with_bridge")
    p_total = parent_row.get("bridging_seeds_total")
    if v_total:
        result.variant_bridged = f"{v_with or 0}/{v_total}"
    if p_total:
        result.parent_bridged = f"{p_with or 0}/{p_total}"
    if v_total and p_total:
        # Lost outright, not merely reduced: the parent bridged and the
        # variant did not, in any seed.
        result.bridge_lost = bool((p_with or 0) > 0 and (v_with or 0) == 0)

        # And the case between the two. F19 recorded that a healthy-looking
        # lift can hide a broken ternary, and the fix then covered outright
        # loss. A parent at 10/10 against a variant at 1/10 is not outright
        # loss and is barely different from it, yet it carried no flag at
        # all: with a positive lift it reads as an improvement, and the
        # chart, which outlines only lost bridges, drew it as a clean point.
        variant_rate = (v_with or 0) / v_total
        parent_rate = (p_with or 0) / p_total
        result.bridge_rate_change = round(variant_rate - parent_rate, 4)
        if parent_rate > 0:
            result.bridge_weakened = bool(
                variant_rate < parent_rate * BRIDGE_RATE_RETAINED_MIN
            )
        else:
            # Nothing to lose. A parent that never bridged cannot have its
            # bridge weakened, and saying otherwise would put every variant
            # of a failed parent under suspicion.
            result.bridge_weakened = False

    result.status = "computed"
    return result


def scan_profile(lifts: list[Lift], parent_sequence: str) -> dict:
    """Per-position summary of an alanine scan.

    The arm's one claim that survives an uncalibrated score. "Position 7
    matters more than position 3" is a statement about the ordering of
    lifts, and an ordering is robust to a monotone miscalibration of the
    scale in a way "this peptide will be degraded" is not. The absolute
    numbers are reported alongside and are not the point.
    """
    by_position: dict[int, Lift] = {}
    for item in lifts:
        if item.status != "computed" or item.substitution is None:
            continue
        # The generator records the position; prefer it. Re-deriving it from
        # the label works for K7A and stops working the moment a label is
        # anything else, and a scan that silently loses a position just
        # leaves a gap in the chart.
        position = item.position
        if position is None:
            digits = "".join(c for c in item.substitution[1:-1] if c.isdigit())
            if not digits:
                continue
            position = int(digits)
        by_position[position] = item

    rows = []
    for position, residue in enumerate(parent_sequence, start=1):
        item = by_position.get(position)
        rows.append({
            "position": position,
            "wild_type": residue,
            "substitution": item.substitution if item else None,
            "lift": item.lift if item else None,
            "collapse_affected": item.collapse_affected if item else None,
            "bridged": item.variant_bridged if item else None,
            "bridge_lost": item.bridge_lost if item else None,
            "bridge_rate_change": item.bridge_rate_change if item else None,
            "bridge_weakened": item.bridge_weakened if item else None,
            "status": item.status if item else "not_scored",
        })

    scored = [row for row in rows if row["lift"] is not None]
    # Ordered over the positions whose lift is not driven by a collapsed seed.
    # "Position 7 matters more than position 3" is the arm's one durable
    # claim, and a position whose lift comes from one collapsed binary seed
    # would take the top of that ordering on an artefact.
    comparable = [row for row in scored if not row.get("collapse_affected")]
    ranked = sorted(comparable, key=lambda row: row["lift"])
    return {
        "parent_sequence": parent_sequence,
        "positions": rows,
        "scored": len(scored),
        "of": len(rows),
        "comparable": len(comparable),
        # Named, not merely subtracted: a reader comparing `scored` against
        # `comparable` needs to know which positions went and why (F74).
        "collapse_affected": [row["substitution"] for row in scored
                              if row.get("collapse_affected")],
        # Most negative lift: replacing this residue hurt the interface most,
        # which is the operational meaning of "this position matters".
        # Positions where the substitution did not merely reduce the
        # interface but removed the bridge entirely. A different and
        # stronger claim than a large negative lift.
        "bridge_breaking": [r["substitution"] for r in rows if r.get("bridge_lost")],
        # Weakened but not lost, kept separate because it is a weaker claim
        # than bridge_breaking and a stronger one than a poor lift.
        "bridge_weakening": [r["substitution"] for r in rows
                             if r.get("bridge_weakened") and not r.get("bridge_lost")],
        "most_sensitive": ranked[0] if ranked else None,
        "least_sensitive": ranked[-1] if ranked else None,
        "note": (
            "Lift is delta_iptm(variant) minus delta_iptm(parent). Negative "
            "means the substitution reduced glue dependence. The ordering of "
            "positions is the durable claim here; the absolute values inherit "
            "whatever calibration delta_iptm has, which is not yet established."
        ),
    }


def from_scores(scores_path: Path, parent_peptide_id: str) -> dict:
    """Load a campaign's scores and compute lifts for one parent's variants."""
    if not scores_path.exists():
        return {"status": "no scores", "lifts": []}
    rows = paths.read_jsonl(scores_path, tolerate_torn=True)
    parent = next((row for row in rows if row.get("peptide_id") == parent_peptide_id), None)
    if parent is None:
        return {"status": f"parent {parent_peptide_id} not scored", "lifts": []}

    variants = [row for row in rows if row.get("parent_peptide_id") == parent_peptide_id
                and row.get("tier") == "design"]
    lifts = [compute(row, parent) for row in variants]
    # A status on the success path too, so an empty result always says why.
    #
    # The two early returns above carry one and this did not, so a parent
    # that is scored and has no design variants returned `lifts: []` with no
    # explanation at all. `tools/run_design.sh` then wrote no
    # `scan_profile.json` and exited 0, and F252 reads a missing profile as
    # "not yet testable" forever (F321).
    return {
        "status": ("computed" if lifts else
                   f"parent {parent_peptide_id} is scored and has no design "
                   "variants in this campaign"),
        "parent": parent_peptide_id,
        "parent_sequence": parent.get("peptide_sequence"),
        "lifts": [item.to_dict() for item in lifts],
        "computed": sum(1 for item in lifts if item.status == "computed"),
        "refused": sum(1 for item in lifts if item.status != "computed"),
    }
