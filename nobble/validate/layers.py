"""The three validation layers (spec 5). All gating.

A campaign that fails any of these publishes its failure rather than its hits.
One asymmetry matters and is implemented literally: **a poor ROC is not a gate
failure. Reporting no ROC, or reporting one without the matched negatives,
is.** The same logic governs the other two layers, so each returns a status
rather than a bare number, and "not computed" is always distinguishable from
"computed and bad".

1. Pose recovery: peptide backbone RMSD to the deposited crystal ternary, as a
   success-rate curve at 1, 2, 3 and 5 angstrom. The seven benchmark pairs are
   reported individually, by name.
2. Time split: entries deposited after the Boltz-2 training cutoff, run blind.
   Canonical degrons are memorised, so this is the only number that estimates
   prospective performance, and it is reported next to the retrospective one
   with both clearly labelled.
3. Matched-control ROC: Delta-ipTM on the Sievers degraded against non-degraded
   split, with a confidence interval.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble.score import poses

# Boltz-2's training cutoff. Depositions released after it cannot have been
# memorised, which is the only thing that makes the blind split meaningful.
# Carried as a date rather than a hardcoded accession list so the split
# re-derives itself whenever the campaign changes.
BOLTZ2_TRAINING_CUTOFF = "2021-09-30"

# Which deposited chain each benchmark member's prediction is compared against.
RECOVERY_TARGETS = {
    "bench01_GSPT1_CRBN": {"pdb_id": "5HXB", "substrate_chain": "X", "substrate_acc": "P15170",
                           "receptor_chain": "Z", "receptor_acc": "Q96SW2"},
    "bench02_BRD4_VHL": {"pdb_id": "5T35", "substrate_chain": "A", "substrate_acc": "O60885",
                         "receptor_chain": "D", "receptor_acc": "P40337"},
    "bench03_BRD4_CRBN": {"pdb_id": "6BNB", "substrate_chain": "C", "substrate_acc": "O60885",
                          "receptor_chain": "B", "receptor_acc": "Q96SW2"},
    "bench04_IKZF1_CRBN": {"pdb_id": "6H0F", "substrate_chain": "C", "substrate_acc": "Q13422",
                           "receptor_chain": "B", "receptor_acc": "Q96SW2"},
    "bench05_CSNK1A1_CRBN": {"pdb_id": "5FQD", "substrate_chain": "C", "substrate_acc": "P48729",
                             "receptor_chain": "B", "receptor_acc": "Q96SW2"},
    "bench06_RBM39_DCAF15": {"pdb_id": "6Q0W", "substrate_chain": "D", "substrate_acc": "Q14498",
                             "receptor_chain": "B", "receptor_acc": "Q66K64"},
    "bench07_CDK12_DDB1": {"pdb_id": "6TD3", "substrate_chain": "B", "substrate_acc": "Q9NYV4",
                           "receptor_chain": "A", "receptor_acc": "Q16531"},
}


# Resolved on (gene, E3) as well as the literal pair id. The targets are
# keyed "bench01_GSPT1_CRBN", and the corrected-construct campaign runs the
# same biology as "corr01_GSPT1_CRBN": the crystal to align against is the
# same one, and keying on the prefix meant pose recovery silently found no
# target there and reported "no predicted pose could be aligned". The F6
# comparison then could never conclude, however long the campaign ran, and
# nothing in the output pointed at the pair id as the reason.
_TARGETS_BY_GENE = {
    tuple(key.split("_")[1:3]): value for key, value in RECOVERY_TARGETS.items()
}


def recovery_target(pair_id: str | None) -> dict | None:
    """The deposited structure to align this pair against, if there is one."""
    if not pair_id:
        return None
    exact = RECOVERY_TARGETS.get(pair_id)
    if exact is not None:
        return exact
    parts = pair_id.split("_")
    if len(parts) >= 3:
        return _TARGETS_BY_GENE.get((parts[1], parts[2]))
    return None


@dataclass
class LayerResult:
    name: str
    status: str                    # computed | not_computed: <reason>
    summary: dict = field(default_factory=dict)
    detail: list = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def computed(self) -> bool:
        return self.status == "computed"

    def to_dict(self) -> dict:
        return asdict(self) | {"computed": self.computed}


def _results(campaign: Path) -> list[dict]:
    path = campaign / "results.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# --------------------------------------------------------------------------- #
# 1. Pose recovery
# --------------------------------------------------------------------------- #

def pose_recovery(campaign: Path) -> LayerResult:
    """RMSD of every predicted peptide to its deposited counterpart."""
    layer = LayerResult(name="pose_recovery", status="not_computed: no results")
    jobs = _results(campaign)
    if not jobs:
        return layer

    per_pair: dict[str, list[float]] = {}
    detail = []
    for job in jobs:
        target = recovery_target(job.get("pair_id"))
        if not target or job.get("complex_type") != "ternary":
            continue
        try:
            outcome = poses.recovery_against_crystal(
                job, target["pdb_id"], target["substrate_chain"],
                target["substrate_acc"], target["receptor_chain"], target["receptor_acc"],
            )
        except Exception as problem:            # noqa: BLE001
            detail.append({"job_id": job["job_id"], "error": f"{type(problem).__name__}: {problem}"})
            continue
        record = outcome.to_dict()
        detail.append(record)
        if outcome.rmsd is not None:
            per_pair.setdefault(job["pair_id"], []).append(outcome.rmsd)

    if not per_pair:
        layer.status = "not_computed: no predicted pose could be aligned to a deposited chain"
        layer.detail = detail[:20]
        return layer

    by_pair = {}
    for pair_id, values in sorted(per_pair.items()):
        ordered = sorted(values)
        by_pair[pair_id] = {
            "n": len(ordered),
            "best_rmsd": round(ordered[0], 3),
            "median_rmsd": round(ordered[len(ordered) // 2], 3),
            "worst_rmsd": round(ordered[-1], 3),
            "curve": poses.success_rate_curve(ordered),
        }

    everything = [value for values in per_pair.values() for value in values]
    layer.status = "computed"
    layer.summary = {
        "pairs_with_recovery": len(by_pair),
        "pairs_expected": len(RECOVERY_TARGETS),
        "poses_compared": len(everything),
        "overall_curve": poses.success_rate_curve(everything),
        "by_pair": by_pair,
        "frame": "superposed on the receptor, peptide backbone atoms only",
    }
    layer.detail = detail
    if len(by_pair) < len(RECOVERY_TARGETS):
        layer.notes.append(
            f"{len(RECOVERY_TARGETS) - len(by_pair)} benchmark pair(s) have no "
            "recovery number yet: their ternary jobs have not completed"
        )
    return layer


# --------------------------------------------------------------------------- #
# 2. Time split
# --------------------------------------------------------------------------- #

def time_split(campaign: Path) -> LayerResult:
    """Split recovery by whether the deposition predates the training cutoff.

    Canonical degrons are memorised by any model trained on the PDB, so the
    retrospective number flatters the method. Only depositions released after
    the cutoff estimate prospective performance, and both numbers are reported
    side by side with their labels, never averaged together.
    """
    layer = LayerResult(name="time_split", status="not_computed: no recovery numbers")
    recovery = pose_recovery(campaign)
    if not recovery.computed:
        layer.status = f"not_computed: pose recovery is {recovery.status}"
        return layer

    from nobble.curate import binman_store as store

    release = {
        row["pdb_id"]: row.get("release_date")
        for row in store.atlas_rows(
            "select pdb_id, release_date from entry where status = 'ok'"
        )
    }

    before, after, unknown = [], [], []
    for pair_id, stats in recovery.summary["by_pair"].items():
        target = recovery_target(pair_id)
        if not target:
            continue
        date = release.get(target["pdb_id"])
        entry = {"pair_id": pair_id, "pdb_id": target["pdb_id"],
                 "release_date": date, "median_rmsd": stats["median_rmsd"]}
        if not date:
            unknown.append(entry)
        elif date >= BOLTZ2_TRAINING_CUTOFF:
            after.append(entry)
        else:
            before.append(entry)

    layer.summary = {
        "training_cutoff": BOLTZ2_TRAINING_CUTOFF,
        "retrospective": {
            "label": "deposited before the cutoff: may be memorised",
            "n": len(before),
            "median_rmsd": round(
                sorted(item["median_rmsd"] for item in before)[len(before) // 2], 3
            ) if before else None,
            "members": before,
        },
        "prospective": {
            "label": "deposited after the cutoff: blind",
            "n": len(after),
            "median_rmsd": round(
                sorted(item["median_rmsd"] for item in after)[len(after) // 2], 3
            ) if after else None,
            "members": after,
        },
        "release_date_unknown": unknown,
    }
    if not after:
        layer.status = (
            "not_computed: no benchmark deposition was released after the "
            f"{BOLTZ2_TRAINING_CUTOFF} training cutoff, so this campaign has no "
            "blind set. The retrospective number stands alone and must not be "
            "read as prospective performance"
        )
        layer.notes.append(
            "The seven panel members are all canonical, long-published ternaries, "
            "which is exactly why they are good positive controls and exactly why "
            "they cannot estimate prospective performance. A blind number needs "
            "post-cutoff depositions from mgtbind_ternary that the campaign does "
            "not currently run."
        )
        return layer

    layer.status = "computed"
    return layer


# --------------------------------------------------------------------------- #
# 3. Matched-control ROC
# --------------------------------------------------------------------------- #

def _seed_balance(positive_rows: list[dict], negative_rows: list[dict]) -> dict:
    """Did both groups contribute the same number of seeds per pair?

    Returned rather than asserted: one lost job in a 2,360-job campaign
    should qualify the curve, not withhold it.
    """
    def profile(rows: list[dict]) -> dict:
        return {
            arm: dict(sorted(Counter(
                row.get(f"seeds_{arm}") for row in rows
            ).items(), key=lambda item: (item[0] is None, item[0])))
            for arm in ("ternary", "binary")
        }

    counts = {"positives": profile(positive_rows), "negatives": profile(negative_rows)}

    # Compare the seed counts each pair contributed, not how many pairs
    # contributed each. The groups are 24 degraded against 96 matched
    # negatives by design, so comparing the tallies would call every arm
    # uneven; what matters is whether a pair on one side was built like a
    # pair on the other.
    arms = ("ternary", "binary")
    distinct = {
        group: {arm: set(counts[group][arm]) for arm in arms}
        for group in ("positives", "negatives")
    }
    uniform = all(len(distinct[group][arm]) == 1
                  for group in ("positives", "negatives") for arm in arms)
    same = distinct["positives"] == distinct["negatives"]
    unknown = all(values == {None}
                  for group in ("positives", "negatives")
                  for values in distinct[group].values())
    balanced = bool(uniform and same and not unknown
                    and positive_rows and negative_rows)

    if not positive_rows or not negative_rows:
        # The curve is refused in this case anyway, but "uneven" would be a
        # claim about data that does not exist.
        return {"counts": counts, "balanced": False, "imbalanced": False,
                "verdict": "not assessable: one or both groups have no scored pairs"}
    if unknown:
        # Score files written before seeds_ternary/seeds_binary existed.
        return {"counts": counts, "balanced": False, "imbalanced": False,
                "verdict": ("not assessable: these scores carry no per-pair "
                            "seed counts, so comparability cannot be checked")}
    if balanced:
        ternary = next(iter(distinct["positives"]["ternary"]))
        binary = next(iter(distinct["positives"]["binary"]))
        verdict = (f"balanced: every pair on both sides contributed {ternary} "
                   f"ternary and {binary} binary seeds")
    elif not uniform:
        verdict = ("uneven within a group: some pairs contributed fewer seeds "
                   "than others, so their minima are not comparable")
    else:
        verdict = ("uneven between groups: the degraded and matched-negative "
                   "sides contributed different numbers of seeds")
    return {"counts": counts, "balanced": balanced,
            "imbalanced": not balanced, "verdict": verdict}


def _auc(positives: list[float], negatives: list[float]) -> float:
    """Mann-Whitney U as the ROC area, which handles ties correctly."""
    if not positives or not negatives:
        return float("nan")
    wins = 0.0
    for p in positives:
        for n in negatives:
            if p > n:
                wins += 1
            elif p == n:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _bootstrap_interval(positives: list[float], negatives: list[float],
                        rounds: int = 2000, seed: int = 20261103) -> tuple[float, float]:
    generator = random.Random(seed)
    values = []
    for _ in range(rounds):
        p = [generator.choice(positives) for _ in positives]
        n = [generator.choice(negatives) for _ in negatives]
        values.append(_auc(p, n))
    values.sort()
    return (round(values[int(0.025 * rounds)], 4), round(values[int(0.975 * rounds)], 4))


def matched_control_roc(campaign: Path, statistic: str = "delta_iptm") -> LayerResult:
    """Delta-ipTM on the Sievers degraded against non-degraded split."""
    layer = LayerResult(name="matched_control_roc", status="not_computed: no scores")
    scores_path = campaign / "scores.jsonl"
    if not scores_path.exists():
        return layer

    rows = [json.loads(line) for line in scores_path.read_text().splitlines() if line.strip()]

    # The Sievers arm only. The benchmark panel also carries the label
    # "degraded", and on label alone its seven pairs would join the positive
    # side of this curve. They are a different experiment: other E3 ligases,
    # PROTACs as well as glues, and no matched negative from the same screen.
    # They are also the panel chosen for having good co-crystals, so they
    # would raise the positive side and the AUC with it, which is the wrong
    # direction for a number to move by accident. Spec 5.3 scopes this curve
    # to the Sievers degraded against non-degraded split.
    arm = [row for row in rows if row.get("tier") == "sievers_zf"]
    excluded = len(rows) - len(arm)

    positive_rows = [row for row in arm
                     if row.get("peptide_label") == "degraded"
                     and isinstance(row.get(statistic), (int, float))]
    negative_rows = [row for row in arm
                     if row.get("peptide_label") == "not_degraded"
                     and isinstance(row.get(statistic), (int, float))]
    positives = [row[statistic] for row in positive_rows]
    negatives = [row[statistic] for row in negative_rows]

    # Delta-ipTM is a difference of minima, and a minimum is not robust to how
    # many seeds it was taken over: a minimum of ten draws sits below a minimum
    # of five for no reason to do with the interface. aggregate() already hard
    # partitions by sampling tier for exactly this reason, but that says nothing
    # about seeds lost within a tier, and a 2,360-job run is expected to lose
    # some: the fallback ladder records a failure and carries on by design.
    #
    # Across the two groups this is a bias, not noise. If the degraded pairs
    # finish more seeds than the matched negatives, their minima are pulled
    # down relative to the negatives' and the AUC moves, with nothing in the
    # curve to show it. So the seed counts are reported with the number, and
    # an imbalance is named. No threshold: the comparison is structural, and
    # the question is only whether every pair contributed alike.
    balance = _seed_balance(positive_rows, negative_rows)

    layer.summary = {
        "statistic": statistic,
        "positives": len(positives),
        "matched_negatives": len(negatives),
        "pairs_outside_the_arm_excluded": excluded,
        "source": "Sievers zinc-finger screen: negatives assayed in the same screen",
        "seed_counts": balance["counts"],
        "seed_balance": balance["verdict"],
    }

    # Spec 5 is explicit that reporting a curve without the matched negatives is
    # itself the failure. Refusing to compute here is the correct behaviour, not
    # a gap.
    if len(positives) < 3 or len(negatives) < 3:
        layer.status = (
            f"not_computed: {len(positives)} positive(s) and {len(negatives)} "
            "matched negative(s) scored. The Sievers arm runs after the benchmark "
            "panel; a curve drawn from benchmark pairs alone would have no matched "
            "negatives and spec 5 forbids reporting one"
        )
        return layer

    auc = _auc(positives, negatives)
    low, high = _bootstrap_interval(positives, negatives)
    layer.status = "computed"
    layer.summary |= {
        "auc": round(auc, 4),
        "ci95": [low, high],
        "interpretation": (
            "above chance" if low > 0.5
            else "not distinguishable from chance at 95 per cent confidence"
        ),
    }
    if balance["imbalanced"]:
        layer.summary["interpretation"] += (
            ". Read with the seed imbalance in mind: Delta-ipTM is a difference "
            "of minima, so groups that contributed different numbers of seeds "
            "are not strictly comparable"
        )
    return layer


def run(campaign: Path) -> dict:
    """All three layers. Returns statuses, never bare numbers."""
    layers = [pose_recovery(campaign), time_split(campaign), matched_control_roc(campaign)]
    report = {
        "campaign": campaign.name,
        "layers": {layer.name: layer.to_dict() for layer in layers},
        "computed": [layer.name for layer in layers if layer.computed],
        "not_computed": {
            layer.name: layer.status for layer in layers if not layer.computed
        },
    }
    (campaign / "validation.json").write_text(json.dumps(report, indent=2, default=str))
    return report
