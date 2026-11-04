"""Tier 2: pose refinement on the top decile (spec 1.2 and Phase 2).

Tier 1 is deliberately cheap triage: three recycles, one diffusion sample,
potentials off. Tier 2 re-runs the survivors at ten recycles, twenty-five
diffusion samples and potentials on.

Selecting the top decile needs a ranking, and spec 4.8 fits the composite
weights rather than hand-setting them (D-NOB-006). When that fit has refused
for want of labelled pairs, ranking by the composite would mean ranking by
nothing, so selection falls back to the **bridge percentile**: spec 4.1 calls
it the primary signal and it is the one component that compares a prediction
to real interfaces rather than to the model's own confidence. Which key was
used is recorded on the selection, because a top decile is only interpretable
if you know what it was the top decile of.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble import paths
from nobble.numeric import finite

# Ranking keys in order of preference. The first one with values on enough
# pairs wins.
RANKING_PREFERENCE = ("nobble_score", "bridge_percentile", "delta_iptm_median")
# Arms whose pairs are controls rather than candidates.
CONTROL_ARMS = ("scramble",)
MINIMUM_RANKED = int(paths.thresholds()["tier2"]["minimum_ranked"])
# Twenty-five diffusion samples per job, so this decides how much compute
# the refinement costs. Was a default argument on two functions.
DECILE_FRACTION = float(paths.thresholds()["tier2"]["decile_fraction"])


@dataclass
class Selection:
    campaign: str
    ranking_key: str | None
    decile_fraction: float
    pairs_considered: int
    pairs_selected: int
    selected: list = field(default_factory=list)
    arms: dict = field(default_factory=dict)
    # Pairs kept out of the ranking because their pose only appears under
    # conditioning. Reported rather than dropped: one that would have topped
    # the decile is a finding (spec 4.7, F48).
    forced_excluded: list = field(default_factory=list)
    status: str = "pending"
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def choose_ranking_key(rows: list[dict]) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    for key in RANKING_PREFERENCE:
        ranked = [row for row in rows if finite(row.get(key))]
        if len(ranked) >= MINIMUM_RANKED:
            if key != RANKING_PREFERENCE[0]:
                notes.append(
                    f"ranked on {key} rather than the composite: the composite "
                    "weights are not fitted yet, and ranking on an unfitted "
                    "composite would be ranking on nothing"
                )
            return key, notes
        if ranked:
            notes.append(f"{key} has only {len(ranked)} value(s): too few to rank on")
    return None, notes


def select_top_decile(campaign: Path, fraction: float | None = None) -> Selection:
    if fraction is None:
        fraction = DECILE_FRACTION
    scores_path = campaign / "scores.jsonl"
    selection = Selection(
        campaign=campaign.name, ranking_key=None, decile_fraction=fraction,
        pairs_considered=0, pairs_selected=0,
    )
    if not scores_path.exists():
        selection.status = "not_selected: no scores"
        return selection

    rows = [json.loads(line) for line in scores_path.read_text().splitlines() if line.strip()]
    selection.pairs_considered = len(rows)

    key, notes = choose_ranking_key(rows)
    selection.notes.extend(notes)
    selection.ranking_key = key
    if key is None:
        selection.status = "not_selected: no component has enough values to rank on"
        return selection

    scorable = [row for row in rows if finite(row.get(key))]

    # Spec 4.7: "A pose that only appears under conditioning is flagged
    # `forced: true`. Forcing a binder into a site it did not choose reliably
    # produces the right neighbourhood and the wrong pose, so forced hits are
    # shown separately and never in the headline ranking."
    #
    # The flag was computed and displayed and nothing acted on it, so a forced
    # pair could take a place in the decile and twenty-five diffusion samples
    # with it: refining a pose the spec says is wrong. CDK12 is the live case,
    # its conditioned seeds at 0.75 to 0.85 against unconstrained at 0.25 to
    # 0.65, a disagreement of 0.494 (F44, F48).
    #
    # Ranked separately rather than dropped. A forced pair that would have
    # topped the decile is a result, and the arm reporting below exists for the
    # same reason: report it, do not let it vote.
    forced = [row for row in scorable if row.get("forced")]
    ranked = sorted((row for row in scorable if not row.get("forced")),
                    key=lambda row: row[key], reverse=True)

    # At least one pair, so a small campaign still refines something.
    take = max(1, math.ceil(len(ranked) * fraction))
    chosen = ranked[:take]

    if forced:
        forced_ranked = sorted(forced, key=lambda row: row[key], reverse=True)
        selection.forced_excluded = [
            {"pair_id": row["pair_id"], key: row[key],
             "conditioning_disagreement": row.get("conditioning_disagreement")}
            for row in forced_ranked
        ]
        would_have_entered = [
            row["pair_id"] for row in forced_ranked
            if not chosen or row[key] >= chosen[-1][key]
        ]
        selection.notes.append(
            f"{len(forced)} pair(s) excluded from the ranking as forced "
            f"(spec 4.7), of which {len(would_have_entered)} would have "
            f"entered the decile: {', '.join(would_have_entered[:5]) or 'none'}"
        )

    selection.selected = [
        {
            "pair_id": row["pair_id"],
            "rank": index + 1,
            key: row[key],
            "e3_gene": row.get("e3_gene"),
            "peptide_gene": row.get("peptide_gene"),
            "ligand_key": row.get("ligand_key"),
            # Which arm the pair came from. The ranking is deliberately blind
            # to this: a scramble that ranks top is a result, and excluding it
            # would hide it. But twenty-five diffusion samples per job is real
            # compute, and a reader should not have to cross-reference
            # scores.jsonl to find out that a third of the refinement was
            # spent on negative controls.
            "tier": row.get("tier"),
            "peptide_label": row.get("peptide_label"),
        }
        for index, row in enumerate(chosen)
    ]
    selection.pairs_selected = len(chosen)
    selection.arms = dict(sorted(Counter(
        str(row.get("tier")) for row in chosen
    ).items()))
    selection.status = "selected"
    # A mixed decile is ordinary and needs no comment. Controls ranking into
    # it is the thing worth saying, and a decile made entirely of controls is
    # the strongest version of it: the first condition tried here fired on the
    # mixed case and stayed silent on that one.
    controls = sum(count for arm, count in selection.arms.items()
                   if arm in CONTROL_ARMS)
    if controls:
        shape = ", ".join(f"{count} {arm}" for arm, count in selection.arms.items())
        selection.notes.append(
            f"{controls} of {len(chosen)} selected pair(s) are controls "
            f"({shape}). The ranking is deliberately blind to the arm, so a "
            "control ranking high is a result rather than a fault, but the "
            "refinement budget is shared and this is where it went"
        )
    return selection


def tier1_worst_seconds(campaign: Path) -> dict[str, float]:
    """Worst completed tier-1 wall clock per pair, from the campaign's own
    results. Worst rather than median: the budget is an abandonment
    threshold, and sizing it from a typical job abandons the slow ones.
    """
    worst: dict[str, float] = {}
    results = campaign / "results.jsonl"
    if not results.exists():
        return worst
    for line in results.read_text().splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("status") != "done":
            continue
        seconds = record.get("seconds")
        pair = record.get("pair_id")
        if not pair or not finite(seconds):
            continue
        worst[pair] = max(worst.get(pair, 0.0), float(seconds))
    return worst


def scaling_bound(settings: dict | None = None) -> float:
    """An upper bound on how much more a tier-2 job costs than a tier-1 one.

    Boltz runs the trunk once per recycle and the structure module once per
    diffusion sample, so the two settings scale different parts of the work
    and the true cost is a weighted sum. The split is unknown without
    instrumenting a run, so this applies both ratios to the whole tier-1
    time and adds them, which double-counts deliberately: the result is a
    bound rather than an estimate. The allowance then covers potentials,
    which are off at tier 1 and on at tier 2 and so appear in no ratio.

    Every term comes from config. Nothing here is a literal.
    """
    settings = settings or paths.tuning()["campaign"]
    samples = (int(settings["tier2_diffusion_samples"])
               / int(settings["tier1_diffusion_samples"]))
    recycles = int(settings["tier2_recycles"]) / int(settings["tier1_recycles"])
    return (samples + recycles) * float(settings["tier2_potentials_allowance"])


def job_budget(worst_tier1: float | None, settings: dict | None = None) -> dict:
    """Seconds to allow one refinement job, and the reasoning as data.

    The configured cap is a floor. A pair whose measured tier-1 cost implies
    more than the floor gets more, because abandoning a refinement that was
    on course is the expensive failure: the compute is spent either way and
    only the result is lost.

    This is not hypothetical. On the campaign that selected the first tier-2
    pair, six of seven measured pairs had between 4.6 and 10 times the
    headroom they needed, and `bench06_RBM39_DCAF15` had 0.83: the DCAF15
    assembly is 1,223 tokens by construction and its worst tier-1 job took
    918s, so its bound is 7.2 hours against a 6.0 hour cap. The selected
    pair happened to be a small one. Had the decile fallen the other way,
    ten jobs would each have run for six hours and been killed while
    working (F100).
    """
    settings = settings or paths.tuning()["campaign"]
    floor = (int(settings["job_timeout_seconds"])
             * int(settings["tier2_timeout_multiple"]))
    bound = scaling_bound(settings)
    implied = math.ceil(worst_tier1 * bound) if finite(worst_tier1) else None
    return {
        "seconds": max(floor, implied) if implied is not None else floor,
        "floor_seconds": floor,
        "implied_seconds": implied,
        "worst_tier1_seconds": worst_tier1 if finite(worst_tier1) else None,
        "scaling_bound": round(bound, 2),
        "basis": "measured tier-1 cost" if implied and implied > floor
                 else "configured floor",
    }


def build_tier2_queue(campaign: Path, selection: Selection) -> dict:
    """Emit a tier-2 queue reusing the tier-1 YAMLs, which do not change.

    Only the sampling settings differ between tiers, and those are command-line
    arguments rather than YAML content, so the inputs are reused verbatim. That
    also guarantees tier 2 is refining the same job rather than a subtly
    different one.
    """
    source_queue = campaign / "queue.jsonl"
    if not source_queue.exists():
        return {"status": "no tier-1 queue to refine"}

    chosen = {item["pair_id"] for item in selection.selected}
    jobs = [
        json.loads(line) for line in source_queue.read_text().splitlines() if line.strip()
    ]
    refine = [
        job for job in jobs
        if job["pair_id"] in chosen and job.get("complex_type") == "ternary"
    ]

    settings = paths.tuning()["campaign"]
    worst = tier1_worst_seconds(campaign)
    budgets = {}

    target = campaign / "queue_tier2.jsonl"
    with target.open("w") as handle:
        for job in refine:
            record = dict(job)
            record["job_id"] = job["job_id"] + "__tier2"
            record["tier_setting"] = 2
            # Sized from this pair's own measured tier-1 cost rather than
            # from a global cap, so the largest construct is not abandoned
            # on a factor guessed for the smallest (F100).
            budget = job_budget(worst.get(job["pair_id"]), settings)
            record["timeout_seconds"] = budget["seconds"]
            budgets[job["pair_id"]] = budget
            handle.write(json.dumps(record) + "\n")
    return {
        "status": "built",
        "queue": str(target),
        "jobs": len(refine),
        "pairs": sorted(chosen),
        "settings": {
            "recycles": settings["tier2_recycles"],
            "diffusion_samples": settings["tier2_diffusion_samples"],
            "potentials": settings["tier2_potentials"],
        },
        "budgets": budgets,
        "note": (
            "Ternary jobs only, because spec 1.2 gives tier 2 one purpose: "
            "pose refinement on the top decile. It is not a second, better "
            "measurement of Delta-ipTM, and it must not be read as one. "
            "Delta-ipTM is a difference of two minima over seeds, so it is "
            "only interpretable when both arms were sampled the same way: "
            "refining the ternary arm to 25 diffusion samples while the "
            "binary arm stays at 1 would push the ternary minimum down on "
            "sample count alone. Scoring enforces this rather than trusting "
            "it, by partitioning on tier_setting, and tier 2 writes to its "
            "own results file so tier 1 stays immutable."
        ),
    }


def run(campaign: Path, fraction: float | None = None) -> dict:
    selection = select_top_decile(campaign, fraction)
    report = {"selection": selection.to_dict()}
    if selection.status == "selected":
        report["queue"] = build_tier2_queue(campaign, selection)
    (campaign / "tier2.json").write_text(json.dumps(report, indent=2, default=str))
    return report


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Select the top decile and build the tier-2 refinement queue."
    )
    parser.add_argument("campaign", nargs="?", default=None)
    parser.add_argument("--fraction", type=float, default=DECILE_FRACTION,
                        help="decile fraction (default 0.1)")
    args = parser.parse_args()

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("benchmark")
    if campaign is None:
        print("no campaign found: assemble one first", file=sys.stderr)
        return 2

    report = run(Path(campaign), fraction=args.fraction)
    print(json.dumps(report, indent=2, default=str))
    # A selection that refused is not a failure of this step: it is the
    # correct answer when nothing has enough values to rank on yet.
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
