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
import math
import random
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble import paths
from nobble.score import poses
from nobble.numeric import finite, finite_values, median_of

ROC_MINIMUM_PER_SIDE = int(paths.thresholds()["validation"]["roc_minimum_per_side"])

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
    return paths.read_jsonl(campaign / "results.jsonl", tolerate_torn=True)


# --------------------------------------------------------------------------- #
# 1. Pose recovery
# --------------------------------------------------------------------------- #

def _footprints(best_job: dict[str, tuple]) -> dict:
    """Where each pair's best pose sits, beside how far it is.

    An RMSD is equally consistent with the model never finding the degron
    site and with it finding the site and laying the chain along it in the
    wrong register (F227). Computed here rather than left to a tool run by
    hand, because this is the layer whose failure holds publication and the
    decomposition is part of what the failure is. Each pair's lowest-RMSD
    pose; `tools/pose_site.py --every-pose` reads them all.

    A pair whose footprint cannot be computed carries its reason rather than
    being dropped: the summary says what was measured and what was not, for
    the same reason `unmeasurable` is counted apart from `pending` below.

    **One status this cannot set.** `tools/pose_site.py` also marks a pair
    `confounded` when its poses were folded from a superseded input (F219),
    read from `tools/stale_featurisation`. A library module under `nobble/`
    importing from `tools/` is the dependency the wrong way round, so that
    flag stays with the tool and with `deploy/build_atlas.py`, which consults
    the same comparison. The gap is contained rather than open: the build
    refuses the whole campaign while any featurisation disagrees, so a
    footprint written here for a confounded pair cannot reach the atlas. A
    reader of `validation.json` alone should still check
    `tools/stale_featurisation.py`, which is what `tools/provenance.py` now
    prints (F222).
    """
    out = {}
    for pair_id, (_rmsd, job, target) in sorted(best_job.items()):
        try:
            record = poses.footprint(job, target)
        except Exception as problem:            # noqa: BLE001
            out[pair_id] = {"status": f"{type(problem).__name__}: {problem}"}
            continue
        out[pair_id] = {key: value for key, value in record.items()
                        if key not in ("pair_id", "job_id")}
    return out


def pose_recovery(campaign: Path) -> LayerResult:
    """RMSD of every predicted peptide to its deposited counterpart."""
    layer = LayerResult(name="pose_recovery", status="not_computed: no results")
    jobs = _results(campaign)
    if not jobs:
        return layer

    per_pair: dict[str, list[float]] = {}
    best_job: dict[str, tuple] = {}
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
        if finite(outcome.rmsd):
            per_pair.setdefault(job["pair_id"], []).append(outcome.rmsd)
            incumbent = best_job.get(job["pair_id"])
            if incumbent is None or outcome.rmsd < incumbent[0]:
                best_job[job["pair_id"]] = (outcome.rmsd, job, target)

    if not per_pair:
        layer.status = "not_computed: no predicted pose could be aligned to a deposited chain"
        layer.detail = detail[:20]
        return layer

    by_pair = {}
    # Pairs that aligned but whose every RMSD was non-finite. A different
    # thing from a pair whose jobs have not run, and the note below used to
    # offer only the second explanation for both (F85).
    unmeasurable: list[str] = []
    for pair_id, values in sorted(per_pair.items()):
        # sorted() on a list containing a NaN leaves the other elements
        # unsorted too, so ordered[0] and ordered[-1] are not the best and
        # worst of anything. Filtered before sorting rather than trusted.
        ordered = sorted(finite_values(values))
        if not ordered:
            unmeasurable.append(pair_id)
            continue
        by_pair[pair_id] = {
            "n": len(ordered),
            "best_rmsd": round(ordered[0], 3),
            "median_rmsd": round(median_of(ordered), 3),
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
        "footprint": _footprints(best_job),
    }
    layer.detail = detail
    if len(by_pair) < len(RECOVERY_TARGETS):
        # Two reasons, counted apart. F78 made an unmeasurable RMSD drop its
        # pair from by_pair, which gave this note a second cause while it
        # still asserted the first, so a pair whose geometry could not be
        # measured was reported as one whose jobs had not run.
        missing = len(RECOVERY_TARGETS) - len(by_pair)
        pending = missing - len(unmeasurable)
        if pending > 0:
            layer.notes.append(
                f"{pending} benchmark pair(s) have no recovery number yet: "
                "their ternary jobs have not completed"
            )
        if unmeasurable:
            layer.notes.append(
                f"{len(unmeasurable)} benchmark pair(s) aligned but produced "
                "no measurable RMSD, so they carry no recovery number: "
                + ", ".join(sorted(unmeasurable))
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
                median_of(item["median_rmsd"] for item in before), 3
            ) if before else None,
            "members": before,
        },
        "prospective": {
            "label": "deposited after the cutoff: blind",
            "n": len(after),
            "median_rmsd": round(
                median_of(item["median_rmsd"] for item in after), 3
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


def _finite(value) -> bool:
    """A real number, which `isinstance(value, (int, float))` is not.

    NaN is a float, and a bool is an int. A NaN passing a type check into
    this curve loses every comparison in the estimator, because NaN is
    neither greater than nor equal to anything, so it is counted as a
    unanimous loss: one NaN among three positives moves the AUC from 1.0 to
    0.667. Python's json writes NaN as a bare `NaN` literal and reads it
    back, so a non-finite value can round-trip through scores.jsonl without
    anything objecting (F74).
    """
    from nobble.numeric import finite

    return finite(value)


def _auc(positives: list[float], negatives: list[float]) -> float:
    """Mann-Whitney U as the ROC area, which handles ties correctly.

    NaN on an empty side, because this layer reports the curve's absence
    rather than raising, and a raise on non-finite input, which is the
    floor under the caller's filter: a biased AUC is indistinguishable from
    a real one. The arithmetic is shared with the weight fitter (F77).
    """
    from nobble.numeric import mann_whitney_auc

    if not positives or not negatives:
        return float("nan")
    return mann_whitney_auc(positives, negatives)


def confidence_level() -> float:
    """The configured interval, as a percentage, for reporting.

    One source for the number the layer computes and the number it prints.
    They were 0.025 and 0.975 inside an expression and "95 per cent" inside a
    string, agreeing with `significance_alpha` by coincidence (F119).
    """
    alpha = float(paths.thresholds()["scoring"]["significance_alpha"])
    return round(100.0 * (1.0 - alpha), 4)


def _bootstrap_interval(positives: list[float], negatives: list[float],
                        rounds: int | None = None,
                        seed: int = 20261103) -> tuple[float, float]:
    """Percentile bootstrap on the AUC, stratified by class.

    Each class is resampled to its own size, which keeps the 24 against 96
    imbalance the arm actually has rather than balancing it away. The bounds
    are the alpha/2 and 1 - alpha/2 order statistics, with alpha read from
    config: the two percentile literals used to be arithmetic inside this
    return statement, which is where the cutoff sweep does not look.
    """
    scoring = paths.thresholds()["scoring"]
    alpha = float(scoring["significance_alpha"])
    if rounds is None:
        rounds = int(scoring["bootstrap_rounds"])

    generator = random.Random(seed)
    values = []
    for _ in range(rounds):
        p = [generator.choice(positives) for _ in positives]
        n = [generator.choice(negatives) for _ in negatives]
        values.append(_auc(p, n))
    values.sort()
    low = min(int((alpha / 2.0) * rounds), rounds - 1)
    high = min(int((1.0 - alpha / 2.0) * rounds), rounds - 1)
    return (round(values[low], 4), round(values[high], 4))


# The tier the matched-control curve is computed over. Named because
# anything reasoning about when the curve becomes available has to apply the
# same exclusion, and a second copy of the string is how two answers to that
# question come to differ: the first estimate of when the curve arrives
# counted every pair carrying the labels, including the seven benchmark
# ones this layer deliberately leaves out, and was optimistic by roughly a
# factor of two (F73).
ROC_ARM = "sievers_zf"
ROC_LABELS = ("degraded", "not_degraded")


def _verdict(low: float, high: float) -> str:
    """What a bootstrap interval says about an AUC, in three cases.

    Written as a function rather than a conditional expression because the
    middle case is the one that used to swallow the third: `low > 0.5` else
    "not distinguishable" reads as exhaustive and is not.
    """
    level = f"{confidence_level():g} per cent confidence"
    if low > 0.5:
        # The level is stated here too, and that is the whole of F198. This
        # branch returned a bare "above chance" while both others carried
        # "at N per cent confidence", so the project's headline claim was
        # the one outcome reported without its qualifier and the two
        # unfavourable ones carried it. Reading a positive result as more
        # certain than a negative one, from the same interval, is the
        # opposite of what this file is careful about everywhere else.
        return f"above chance at {level}"
    if high < 0.5:
        return (
            f"below chance at {level}: the statistic separates the two "
            "classes in the opposite direction to the prediction, which is a "
            "result rather than an absence of one"
        )
    return f"not distinguishable from chance at {level}"


def _arm_expected(campaign: Path) -> tuple[dict[str, int], bool]:
    """Distinct ROC-arm pairs per label in the campaign's queue.

    The queue carries `tier` and `peptide_label` on every job, so the arm's
    intended composition is exact rather than inferred. Counted over pair ids
    because the curve has one point per pair, not per job.

    An unreadable or absent queue gives an empty mapping, which reads as "not
    known" downstream rather than as zero: a zero denominator would make any
    coverage look complete, which is the failure this exists to prevent.
    """
    queue = Path(campaign) / "queue.jsonl"
    if not queue.exists():
        return {}, False
    seen: dict[str, set[str]] = {}
    try:
        rows = paths.read_jsonl(queue, tolerate_torn=True)
    except OSError:
        return {}, False
    for row in rows:
        if row.get("tier") != ROC_ARM:
            continue
        label = row.get("peptide_label")
        if label not in ROC_LABELS:
            continue
        seen.setdefault(label, set()).add(row.get("pair_id"))
    return {label: len(pairs) for label, pairs in seen.items()}, True


def _arm_absent_statistic(arm: list[dict], statistic: str) -> dict[str, int]:
    """Arm rows that were scored and carry no value for this statistic.

    A different thing from a pair that has not been scored, and worse. For
    `delta_iptm` it is always zero. For `bridge_percentile` it is the pairs
    in which no seed bridged, so there is no percentile to take: those pairs
    are missing from the curve *because of the outcome being measured*, which
    is a selection on the dependent variable rather than an incomplete run
    (F280).
    """
    out: dict[str, int] = {}
    for row in arm:
        label = row.get("peptide_label")
        if label not in ROC_LABELS:
            continue
        if row.get(statistic) is None:
            out[label] = out.get(label, 0) + 1
    return out


def _arm_coverage(positives: int, negatives: int,
                  expected: dict[str, int],
                  queue_was_read: bool = False,
                  absent: dict[str, int] | None = None,
                  statistic: str = "") -> str:
    """One line saying how much of the arm the curve was drawn from.

    `queue_was_read` separates two cases that an empty `expected` cannot.
    Run against the corrected campaign, whose queue is perfectly readable and
    holds seven whole-domain pairs and no Sievers ones, the line read "the
    campaign's queue could not be read", which sends a reader looking for a
    missing file. That is F266's `unavailable` against `not_applicable`
    distinction, in the code written for F259 the same morning (F278).

    Passed as its own argument rather than carried in `expected`, which is a
    mapping of per-label counts: a boolean in there leaked into callers that
    iterate the labels, and the test asserting the mapping equals
    `{"degraded": 3, "not_degraded": 3}` failed at once.
    """
    want_pos = expected.get("degraded")
    want_neg = expected.get("not_degraded")
    if not want_pos or not want_neg:
        if queue_was_read:
            return ("not_applicable: the campaign's queue holds no pairs of "
                    f"the {ROC_ARM} arm, so there is no arm size to compare "
                    "against")
        return ("unknown: the campaign's queue could not be read, so the "
                "arm's intended size is not available to compare against")
    if positives >= want_pos and negatives >= want_neg:
        return (f"complete: all {want_pos} positive(s) and {want_neg} matched "
                "negative(s) of the arm are on the curve")
    line = (f"partial: {positives} of {want_pos} positive(s) and {negatives} "
            f"of {want_neg} matched negative(s). The interval widens with a "
            "smaller sample")
    missing_value = sum((absent or {}).values())
    if missing_value:
        # The reason decides how bad it is, so the reason is stated. An
        # unscored pair is an incomplete run; a scored pair with no value for
        # this statistic is absent because of what was measured, and for
        # `bridge_percentile` that means the pairs where nothing bridged.
        return (line + f", and {missing_value} of the missing pair(s) were "
                f"scored and carry no {statistic or 'value'}: those are "
                "absent because of the outcome, not because the run is "
                "unfinished, so the curve is over pairs selected on the "
                "quantity it measures")
    return (line + ", and the pairs not yet scored are not a random subset "
            "of the arm: they are whatever the runner reached last")


def matched_control_roc(campaign: Path, statistic: str = "delta_iptm") -> LayerResult:
    """Delta-ipTM on the Sievers degraded against non-degraded split."""
    layer = LayerResult(name="matched_control_roc", status="not_computed: no scores")
    scores_path = campaign / "scores.jsonl"
    if not scores_path.exists():
        return layer

    rows = paths.read_jsonl(scores_path, tolerate_torn=True)

    # The Sievers arm only. The benchmark panel also carries the label
    # "degraded", and on label alone its seven pairs would join the positive
    # side of this curve. They are a different experiment: other E3 ligases,
    # PROTACs as well as glues, and no matched negative from the same screen.
    # They are also the panel chosen for having good co-crystals, so they
    # would raise the positive side and the AUC with it, which is the wrong
    # direction for a number to move by accident. Spec 5.3 scopes this curve
    # to the Sievers degraded against non-degraded split.
    arm = [row for row in rows if row.get("tier") == ROC_ARM]
    excluded = len(rows) - len(arm)

    positive_rows = [row for row in arm
                     if row.get("peptide_label") == "degraded"
                     and _finite(row.get(statistic))]
    negative_rows = [row for row in arm
                     if row.get("peptide_label") == "not_degraded"
                     and _finite(row.get(statistic))]
    # Dropped for being non-finite rather than absent, counted separately
    # because a silent change of denominator is its own problem: a reader
    # comparing the positive count against the campaign needs to see that a
    # pair was scored and then excluded (F74).
    non_finite = sum(
        1 for row in arm
        if row.get("peptide_label") in ROC_LABELS
        and row.get(statistic) is not None
        and not _finite(row.get(statistic)))
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

    # What the arm should hold, from the campaign's own queue. Without it the
    # counts below have no denominator: 24 positives and 96 negatives is the
    # whole arm, and 6 and 24 would print in the same shape with nothing to
    # say that three quarters of it had not been scored. A curve over a
    # partial arm is still a real estimate with a wider interval, unlike
    # F258's vacuous confirmation, so this reports coverage rather than
    # refusing to compute.
    expected, queue_was_read = _arm_expected(campaign)

    layer.summary = {
        "statistic": statistic,
        "positives": len(positives),
        "matched_negatives": len(negatives),
        "positives_expected": expected.get("degraded"),
        "matched_negatives_expected": expected.get("not_degraded"),
        "coverage": _arm_coverage(len(positives), len(negatives), expected,
                                  queue_was_read,
                                  _arm_absent_statistic(arm, statistic),
                                  statistic),
        "scored_without_the_statistic": _arm_absent_statistic(arm, statistic),
        "pairs_outside_the_arm_excluded": excluded,
        "non_finite_dropped": non_finite,
        "source": "Sievers zinc-finger screen: negatives assayed in the same screen",
        "seed_counts": balance["counts"],
        "seed_balance": balance["verdict"],
        # Spec 5.3 asks for two tests here, not one: "Delta-ipTM on the
        # Sievers degraded versus non-degraded split, with the Slabicki
        # graded labels as a secondary continuous test". The binary split is
        # below. The graded one cannot be run: BINMAN cites Slabicki 2025 in
        # its bibliography and never acquired the per-compound degradation
        # data, so there is no continuous label to correlate against.
        #
        # Said here rather than left out, on the same principle as the
        # furniture veto (D-NOB-010): a reader comparing this output with
        # the specification should find the missing half named, not absent
        # (F52).
        "secondary_graded_test": (
            "not_computed: slabicki_graded_labels_unavailable. Spec 5.3 "
            "specifies a secondary continuous test against Slabicki's graded "
            "degradation labels. BINMAN cites the paper and did not acquire "
            "the per-compound data, so the split below is binary only"
        ),
    }

    # Spec 5 is explicit that reporting a curve without the matched negatives is
    # itself the failure. Refusing to compute here is the correct behaviour, not
    # a gap.
    if len(positives) < ROC_MINIMUM_PER_SIDE or len(negatives) < ROC_MINIMUM_PER_SIDE:
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
        # The key keeps its conventional name; `confidence_level` states the
        # level actually used, so the two cannot disagree if alpha changes.
        "ci95": [low, high],
        "confidence_level": confidence_level(),
        # Three outcomes, not two. An interval entirely below 0.5 is not
        # "indistinguishable from chance": it is the statistic separating the
        # two classes in the opposite direction to the prediction, which for
        # Delta-ipTM would mean the matched negatives gaining more interface
        # confidence from the glue than the degraded fingers do. Spec 4.3
        # asks for exactly that case to be reported, "a real result about
        # co-folding models and ternary cooperativity [...] rather than
        # hiding it", and D-NOB-024 already reports BINMAN's reach window as
        # "at or below chance and slightly inverted". This branch could not
        # say it (F120).
        "interpretation": _verdict(low, high),
    }
    if balance["imbalanced"]:
        layer.summary["interpretation"] += (
            ". Read with the seed imbalance in mind: Delta-ipTM is a difference "
            "of minima, so groups that contributed different numbers of seeds "
            "are not strictly comparable"
        )
    return layer


# The statistic spec 5.3 names, and the others that have been put to the same
# labels. Listed here so the count is a fact in the code rather than something
# a reader has to reconstruct: four statistics on one label set is four
# chances, and only the first is in the specification (F280).
ROC_COMPANIONS = ("delta_iptm_median", "bridge_formation_rate",
                  "bridge_percentile")


def roc_companions(campaign: Path) -> list[dict]:
    """The same curve on each companion statistic, for the record.

    Not a search for a better number. F280 fixed the reading before any of
    these were computed: an interval containing 0.5 leaves the null standing
    across everything tried, and one excluding it is a lead needing its
    multiplicity stated and replication on labels not yet used. All four
    contain 0.5.

    Carried into `validation.json` so the app can show that the null is not
    merely the primary statistic's, which is the stronger and more useful
    statement. Each row keeps its own coverage line, because
    `bridge_percentile` is absent for pairs in which nothing bridged and so
    runs on a subset selected on the outcome it measures.
    """
    out = []
    for statistic in ROC_COMPANIONS:
        layer = matched_control_roc(campaign, statistic=statistic)
        summary = layer.summary or {}
        out.append({
            "statistic": statistic,
            "computed": layer.computed,
            "status": layer.status,
            "auc": summary.get("auc"),
            "ci95": summary.get("ci95"),
            "positives": summary.get("positives"),
            "matched_negatives": summary.get("matched_negatives"),
            "coverage": summary.get("coverage"),
            "interpretation": summary.get("interpretation"),
        })
    return out


def run(campaign: Path) -> dict:
    """All three layers. Returns statuses, never bare numbers."""
    primary = matched_control_roc(campaign)
    if primary.computed:
        # Attached to the primary curve rather than stored beside it, so a
        # reader of the ROC layer cannot miss that three more statistics were
        # tried on the same labels.
        primary.summary["companions"] = roc_companions(campaign)
        primary.summary["statistics_tried"] = 1 + len(ROC_COMPANIONS)
    layers = [pose_recovery(campaign), time_split(campaign), primary]
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
