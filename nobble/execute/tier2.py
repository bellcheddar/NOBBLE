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
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble import paths

# Ranking keys in order of preference. The first one with values on enough
# pairs wins.
RANKING_PREFERENCE = ("nobble_score", "bridge_percentile", "delta_iptm_median")
MINIMUM_RANKED = 3


@dataclass
class Selection:
    campaign: str
    ranking_key: str | None
    decile_fraction: float
    pairs_considered: int
    pairs_selected: int
    selected: list = field(default_factory=list)
    status: str = "pending"
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def choose_ranking_key(rows: list[dict]) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    for key in RANKING_PREFERENCE:
        ranked = [row for row in rows if isinstance(row.get(key), (int, float))]
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


def select_top_decile(campaign: Path, fraction: float = 0.1) -> Selection:
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

    ranked = sorted(
        (row for row in rows if isinstance(row.get(key), (int, float))),
        key=lambda row: row[key], reverse=True,
    )
    # At least one pair, so a small campaign still refines something.
    take = max(1, math.ceil(len(ranked) * fraction))
    chosen = ranked[:take]

    selection.selected = [
        {
            "pair_id": row["pair_id"],
            "rank": index + 1,
            key: row[key],
            "e3_gene": row.get("e3_gene"),
            "peptide_gene": row.get("peptide_gene"),
            "ligand_key": row.get("ligand_key"),
        }
        for index, row in enumerate(chosen)
    ]
    selection.pairs_selected = len(chosen)
    selection.status = "selected"
    return selection


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

    target = campaign / "queue_tier2.jsonl"
    with target.open("w") as handle:
        for job in refine:
            record = dict(job)
            record["job_id"] = job["job_id"] + "__tier2"
            record["tier_setting"] = 2
            handle.write(json.dumps(record) + "\n")

    settings = paths.tuning()["campaign"]
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


def run(campaign: Path, fraction: float = 0.1) -> dict:
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
    parser.add_argument("--fraction", type=float, default=0.1,
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
