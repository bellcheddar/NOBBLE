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
from nobble.execute import budget
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
    # Pairs added to the refinement because they have a deposited structure,
    # not because they ranked. Kept in their own list rather than appended to
    # `selected` so that `pairs_selected`, `arms` and the decile reporting
    # keep meaning "the top decile" (F212).
    recovery_controls: list = field(default_factory=list)
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

    rows = paths.read_jsonl(scores_path, tolerate_torn=True)
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
    selection.recovery_controls = recovery_controls_for(
        rows, {item["pair_id"] for item in selection.selected}
    )
    if selection.recovery_controls:
        selection.notes.append(
            f"{len(selection.recovery_controls)} pair(s) with a deposited "
            "structure added to the refinement as recovery controls, outside "
            "the decile and outside pairs_selected: "
            + ", ".join(item["pair_id"] for item in selection.recovery_controls)
            + ". Without them a refinement produces no RMSD against ground "
            "truth and cannot be told from a refinement that changed nothing"
        )
    else:
        # Said rather than left to inference. An empty list here means the
        # campaign holds no pair with a crystal, which is a property of the
        # campaign worth reading off the selection.
        selection.notes.append(
            "no pair in this campaign has a deposited structure, so the "
            "refinement carries no recovery control and its effect on pose "
            "accuracy cannot be measured"
        )

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


def recovery_controls_for(rows: list[dict], already: set[str]) -> list[dict]:
    """Pairs with a deposited structure, which make the refinement measurable.

    A refinement selected purely by rank can contain no pair with ground
    truth, and this campaign's did: the top decile took sixteen pairs by
    `nobble_score` and not one of them had a crystal to compare against. So
    the one rung of the fallback ladder that might have rescued a failed
    pose-recovery control could not be tested with the compute it was
    already spending (F212).

    Carried as controls rather than as candidates. They do not enter the
    ranking, they are not counted in `pairs_selected`, and reduction never
    drops them: a refinement that cannot be measured is not a cheaper
    refinement, it is an unfalsifiable one.
    """
    # Imported here rather than at module scope: the table lives with the
    # validation layer that consumes it, and that module pulls in gemmi
    # through nobble.score.poses, which this module otherwise does not need.
    from nobble.validate.layers import recovery_target

    controls = []
    for row in rows:
        pair_id = row.get("pair_id")
        if not pair_id or pair_id in already:
            continue
        target = recovery_target(pair_id)
        if target is None:
            continue
        if any(item["pair_id"] == pair_id for item in controls):
            continue
        controls.append({
            "pair_id": pair_id,
            "role": "recovery_control",
            "pdb_id": target["pdb_id"],
            "e3_gene": row.get("e3_gene"),
            "peptide_gene": row.get("peptide_gene"),
            "tier": row.get("tier"),
        })
    return sorted(controls, key=lambda item: item["pair_id"])


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
    control_ids = {item["pair_id"] for item in selection.recovery_controls}
    wanted = chosen | control_ids
    jobs = paths.read_jsonl(source_queue)
    # Needed by the ordering below as well as by the per-pair timeout.
    worst = tier1_worst_seconds(campaign)
    refine = [
        job for job in jobs
        if job["pair_id"] in wanted and job.get("complex_type") == "ternary"
    ]
    # Controls first, and within the controls cheapest first. The runner
    # walks the queue in order, and the question the controls answer ("does
    # refinement move the poses towards the crystal") decides whether the
    # decile is worth refining at all, so ordering it behind the decile would
    # answer it last (F212).
    #
    # Cheapest first because the controls are a panel and the answer wanted
    # from them is "on how many pairs does refinement help", which is served
    # by breadth. On this campaign one control costs 11.66 h of the 18.80 h
    # the panel costs in total, and running it in pair-id order would spend
    # most of a day before the last two pairs reported. Sorted on each pair's
    # own measured tier-1 cost, so the ordering is the measurement's rather
    # than a guess at which construct is large.
    pair_cost = {
        pair_id: (worst.get(pair_id) if worst.get(pair_id) is not None
                  else float("inf"))
        for pair_id in wanted
    }
    refine.sort(key=lambda job: (job["pair_id"] not in control_ids,
                                 pair_cost[job["pair_id"]],
                                 job["pair_id"], job["job_id"]))

    settings = paths.tuning()["campaign"]
    budgets = {}

    target = campaign / "queue_tier2.jsonl"
    with target.open("w") as handle:
        for job in refine:
            record = dict(job)
            record["job_id"] = job["job_id"] + "__tier2"
            record["tier_setting"] = 2
            record["tier2_role"] = (
                "recovery_control" if job["pair_id"] in control_ids else "decile"
            )
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
        "pairs": sorted(wanted),
        "decile_pairs": sorted(chosen),
        "recovery_control_pairs": sorted(control_ids),
        "jobs_by_role": {
            "decile": sum(1 for job in refine
                          if job["pair_id"] not in control_ids),
            "recovery_control": sum(1 for job in refine
                                    if job["pair_id"] in control_ids),
        },
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
    """Select, price against the budget, reduce if needed, then queue.

    The pricing step is new (F135). Refinement re-runs the decile's ternary
    jobs at 25 diffusion samples against tier 1's 1, so it is not a rounding
    error on tier 1, and nothing here compared it to `max_compute_hours`: the
    per-job timeout bounds one job, and a hundred and fifty jobs at a
    six-hour timeout is nine hundred hours against a ninety-six hour gate.
    Priced on this campaign's decile it is 31 to 235 hours against 73 left.

    Reduction drops pairs from the bottom of the ranking. Gate G1 opens only
    if nothing is affordable, which is what the gate is defined against: the
    minimum viable set, after automatic scope reduction.
    """
    # Any previous queue goes before anything is selected, so that after
    # this call the queue exists if and only if this call wrote one. It did
    # not, and the file is written only on the path that reaches the end:
    # every refusal returned with a days-old queue still on disk. One was,
    # ten jobs for bench02_BRD4_VHL written on 3 November, and a refusal
    # here would have had the refiner spend GPU hours on that selection
    # while the log read as a fresh decile (F193).
    #
    # Here rather than in `main()` because it is a property every caller
    # should get: "the queue reflects this selection" is not something a
    # shell script should have to arrange.
    stale = campaign / "queue_tier2.jsonl"
    stale.unlink(missing_ok=True)

    selection = select_top_decile(campaign, fraction)
    report = {"selection": selection.to_dict()}
    if selection.status == "selected":
        ranked = [item["pair_id"] for item in selection.selected]
        control_ids = [item["pair_id"] for item in selection.recovery_controls]
        # Controls at the front, because `affordable_pairs` drops from the
        # back. Pricing the decile alone understated the cost by whatever the
        # controls add, and reduction would otherwise have dropped the pairs
        # the refinement is measured by before the pairs it is measuring.
        affordable = budget.affordable_pairs(campaign, control_ids + ranked)
        report["budget"] = affordable
        if affordable.get("unpriceable"):
            # Not a gate: a refusal to spend an unknown amount. Distinct
            # from G1, which is a cost that exceeds the budget (F161).
            selection.status = "refused: refinement cannot be priced"
            selection.notes.append(affordable["report"]["verdict"])
            report["selection"] = selection.to_dict()
            (campaign / "tier2.json").write_text(
                json.dumps(report, indent=2, default=str))
            return report
        if affordable["gate_g1_open"]:
            selection.status = "refused: gate G1"
            selection.notes.append(
                "GATE G1 OPEN: " + affordable["report"]["verdict"]
            )
            report["selection"] = selection.to_dict()
            (campaign / "tier2.json").write_text(
                json.dumps(report, indent=2, default=str))
            return report
        if affordable["dropped"]:
            keep = set(affordable["affordable"])
            dropped_controls = [pair_id for pair_id in control_ids
                                if pair_id not in keep]
            if dropped_controls:
                # Reduction reached past the decile and into the controls, so
                # what is left cannot be measured. That is the minimum viable
                # set being unaffordable, which is what G1 is defined against.
                selection.status = "refused: gate G1"
                selection.notes.append(
                    "GATE G1 OPEN: reduction could not fit even the "
                    f"{len(control_ids)} recovery control(s) "
                    f"({', '.join(control_ids)}), so any refinement that fits "
                    "produces no RMSD against a deposited structure. "
                    + affordable["report"]["verdict"]
                )
                report["selection"] = selection.to_dict()
                (campaign / "tier2.json").write_text(
                    json.dumps(report, indent=2, default=str))
                return report
            selection.selected = [item for item in selection.selected
                                  if item["pair_id"] in keep]
            selection.pairs_selected = len(selection.selected)
            selection.notes.append(
                f"reduced from {len(ranked)} pair(s) to "
                f"{len(selection.selected)} to fit the compute budget: "
                + affordable["report"]["verdict"]
                + ". Dropped from the bottom of the ranking, never seeds "
                "from a pair, because a pair refined with fewer seeds than "
                "its own tier-1 arm is not a cheaper measurement of the "
                "same thing. Re-running this step after the first "
                "refinement completes prices the rest on a measured factor "
                "rather than a bound, and may afford more"
            )
            report["selection"] = selection.to_dict()
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

    # Whether a queue was written, as one line a shell can read. The exit
    # code cannot carry this: 0 covers a selection, a refusal with nothing
    # rankable, and an unpriceable refusal alike, and only the first writes
    # a queue. `tools/tier2.sh` keyed on exit 3 alone and would refine on
    # the other two (F193).
    #
    # A sentinel prefix rather than the last line, for the reason
    # `hwprobe.mps_state` and `software.versions` use one: a pixi
    # environment can print a warning and the last line of stdout is not
    # reliably the answer.
    queue = Path(campaign) / "queue_tier2.jsonl"
    written = queue.exists() and queue.stat().st_size > 0
    print("TIER2_QUEUE=" + (str(queue) if written else "none"))
    # 3 for an open gate, matching `curate.library.main`. tools/tier2.sh
    # keys on it to skip refinement: without that the refiner runs next with
    # no queue to read, which is harmless and reads in the log as though the
    # refinement had been done.
    if report.get("budget", {}).get("gate_g1_open"):
        print("GATE G1 OPEN: " + report["budget"]["report"]["verdict"],
              file=sys.stderr)
        return 3
    # A selection that refused is not a failure of this step: it is the
    # correct answer when nothing has enough values to rank on yet.
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
