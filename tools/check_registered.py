#!/usr/bin/env python3
"""Score the predictions registered in F251, F252 and F253, mechanically.

F13 recorded two predictions with explicit falsifiers before their pairs ran,
and `tools/check_prediction.py` scores them rather than leaving them to be
read, because "a scorer that cannot return wrong is not scoring anything"
(F18). Three more were registered in this session, for data that did not yet
exist: refinement's effect on discrimination, the design scan's most
sensitive position, and Tier B's bridging. Without a scorer they would be
read after the fact, which is what F13's mechanism exists to prevent.

Separate from `check_prediction.py` rather than added to it: that tool is
keyed on genes and compares two campaigns, and these three are different
shapes. Same discipline, one tool per prediction family.

The thresholds below are transcribed from the FINDINGS entries and are part
of the predictions. Moving them into config would make the verdicts tunable
once the results are known, which is the opposite of the point: see the
`TOOLS_ALLOWED` note in `tests/test_no_hardcoded_cutoffs.py`.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# F251: paired tier-1 against tier-2 AUC over the refined Sievers pairs.
F251_MOVE = 0.10
# F252: window positions by CRBN contact count, measured from the deposition.
F252_SUPPORTED = (5, 6, 7)
F252_REFUTED = (1, 2, 12, 13, 14, 15)
# F253: a Tier B hit, paired against the pair's own scramble. Stated as a
# rate, not a seed count: Tier B runs five ternary seeds per arm and the first
# version of this asked for eight of ten, which could never fire.
F253_POSITIVE_RATE = 0.8
F253_SCRAMBLE_RATE = 0.2


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def f251_refinement_discrimination(campaign: Path) -> dict:
    """Withdrawn: tier 2 has no Delta-ipTM to compare (F251, F254).

    Reported rather than deleted, and reported as withdrawn rather than as
    pending. Left as "not yet testable" it would have waited for
    `scores_tier2.jsonl` and then skipped every row for a null delta,
    reporting a missing measurement as an unfinished stage for as long as
    anyone looked.
    """
    return {"finding": "F251",
            "claim": "refinement does not improve discrimination (noise)",
            "falsifier": f"paired AUC moves by more than {F251_MOVE}",
            "status": "withdrawn",
            "detail": "tier 2 is ternary-only, so Delta-ipTM has no binary "
                      "term there, and assembling one across tiers is the "
                      "bias D-NOB-032 forbids. Replaced by F254"}


def f254_refinement_bridging(campaign: Path) -> dict:
    """Does refining the poses change the bridge formation rate?"""
    from nobble.validate import layers

    verdict = {"finding": "F254",
               "claim": "refinement does not change bridge formation (noise)",
               "falsifier": f"the median rate moves by more than {F251_MOVE}"}
    tier2 = _rows(campaign / "scores_tier2.jsonl")
    if not tier2:
        verdict.update(status="not yet testable",
                       detail="no scores_tier2.jsonl: the tier-2 stage has "
                              "not been scored")
        return verdict

    tier1 = {row["pair_id"]: row for row in _rows(campaign / "scores.jsonl")}
    paired = []
    for row in tier2:
        base = tier1.get(row.get("pair_id"))
        if not base or base.get("tier") != layers.ROC_ARM:
            continue
        label = base.get("peptide_label")
        if label not in layers.ROC_LABELS:
            continue
        before = base.get("bridge_formation_rate")
        after = row.get("bridge_formation_rate")
        if before is None or after is None:
            continue
        paired.append((label, before, after))

    # Both classes present, rather than a minimum count. A count would be a
    # cutoff deciding when the prediction becomes scoreable, which is the
    # sort of number that belongs in config or nowhere.
    #
    # The message here named the delta rather than the bridge rate, and the
    # comment said an AUC needs one of each (F347). Neither is what this
    # gate reads. It
    # compares `bridge_formation_rate` between tiers and takes a median, and
    # `delta_iptm` is structurally absent at tier 2 because only ternary
    # jobs are refined, so a reader of that message had to go and find out
    # whether the prediction could resolve at all. It can: 12 of the 23
    # pairs queued for refinement are Sievers pairs and both labels are
    # present, 4 degraded and 8 not. A gate that names the wrong quantity
    # costs the next reader the same hour.
    labels = {row[0] for row in paired}
    if labels != set(layers.ROC_LABELS):
        verdict.update(status="not yet testable",
                       detail=f"{len(paired)} refined Sievers pair(s) carry a "
                              f"bridge formation rate at both tiers, covering "
                              f"{sorted(labels)}: this needs both classes. "
                              f"{len(tier2)} pair(s) are scored at tier 2")
        return verdict

    import statistics

    before = statistics.median(row[1] for row in paired)
    after = statistics.median(row[2] for row in paired)
    move = after - before
    verdict.update(
        status=("WRONG" if abs(move) > F251_MOVE else "supported"),
        pairs=len(paired),
        tier1_rate=round(before, 4), tier2_rate=round(after, 4),
        move=round(move, 4),
        detail=("median bridge rate over the refined Sievers pairs, each "
                "against its own tier-1 rate. A rate over seeds is not pushed "
                "in a fixed direction by deeper sampling, unlike the minimum "
                "F251 tried to compare"))
    return verdict


def f252_design_scan_position(campaign: Path | None) -> dict:
    """Is the most sensitive scan position one that touches CRBN?"""
    verdict = {"finding": "F252",
               "claim": f"most_sensitive falls in {F252_SUPPORTED}",
               "falsifier": f"it falls in {F252_REFUTED}, which touch CRBN "
                            "not at all"}
    if campaign is None:
        verdict.update(status="not yet testable",
                       detail="no design campaign on disk")
        return verdict
    profile = campaign / "scan_profile.json"
    if not profile.exists():
        verdict.update(status="not yet testable",
                       detail=f"no scan_profile.json in {campaign.name}: the "
                              "scan has not run and been scored")
        return verdict
    payload = json.loads(profile.read_text())
    most = (payload.get("most_sensitive") or {})
    position = most.get("position")
    if position is None:
        verdict.update(status="not yet testable",
                       detail="the profile names no most_sensitive position")
        return verdict
    verdict.update(
        position=position, substitution=most.get("substitution"),
        lift=most.get("lift"),
        status=("supported" if position in F252_SUPPORTED
                else "WRONG" if position in F252_REFUTED
                else "unclear"),
        detail=("positions 5, 6 and 7 carry four or more CRBN contacts in the "
                "deposition; 1, 2 and 12 to 15 carry none"))
    return verdict


def f253_tier_b_bridging(campaign: Path | None) -> dict:
    """Does any Tier B pair bridge where its own scramble does not?"""
    verdict = {"finding": "F253",
               "claim": "no pair clears the bridging line",
               "falsifier": (f"a positive's bridge rate is >= "
                             f"{F253_POSITIVE_RATE} while its own scramble's "
                             f"is <= {F253_SCRAMBLE_RATE}")}
    if campaign is None:
        verdict.update(status="not yet testable",
                       detail="no Tier B campaign on disk")
        return verdict
    rows = _rows(campaign / "scores.jsonl")
    if not rows:
        verdict.update(status="not yet testable",
                       detail=f"{campaign.name} has no scores.jsonl: the arm "
                              "has not run and been scored")
        return verdict

    with_bridge = {row["pair_id"]: row.get("bridge_formation_rate")
                   for row in rows}
    hits, unpaired = [], 0
    for pair_id, count in sorted(with_bridge.items()):
        if not pair_id.startswith("tb_pos_") or count is None:
            continue
        scramble = with_bridge.get("tb_neg_" + pair_id[len("tb_pos_"):])
        if scramble is None:
            unpaired += 1
            continue
        if count >= F253_POSITIVE_RATE and scramble <= F253_SCRAMBLE_RATE:
            hits.append({"pair_id": pair_id, "positive_rate": count,
                         "scramble_rate": scramble})
    compared = sum(1 for p in with_bridge if p.startswith("tb_pos_"))
    # The denominator is the queue, not what happens to be scored. The arm is
    # run with `|| true` and the runner stops on Gate G5, so a partial
    # scores.jsonl is a normal outcome, and "no pair clears the line" is
    # vacuously true of an empty set. One row was enough for this to report
    # `supported`, which is F251's error in a new place: a prediction
    # confirmed by the absence of the data that could refute it.
    expected = len({row["pair_id"] for row in _rows(campaign / "queue.jsonl")
                    if str(row.get("pair_id")).startswith("tb_pos_")})

    # Asymmetric on purpose. A single hit refutes the claim whatever the
    # coverage, because the claim is that no pair clears the line and here is
    # one that does. Confirming it needs every pair, because the next one
    # scored could be the counterexample. Refutation takes one case,
    # confirmation takes the set.
    if hits:
        verdict.update(status="WRONG", hits=hits, positives_compared=compared,
                       positives_expected=expected, unpaired=unpaired,
                       detail=("a positive clears the line while its own "
                               "scramble does not, which refutes the claim "
                               "whatever else is still to be scored"))
        return verdict
    if expected and compared < expected:
        verdict.update(
            status="not yet testable", hits=hits, positives_compared=compared,
            positives_expected=expected, unpaired=unpaired,
            detail=(f"{compared} of {expected} positives scored: no pair "
                    "clearing the line is vacuously true of a partial arm, "
                    "and the unscored pairs are where a counterexample would "
                    "be"))
        return verdict
    verdict.update(
        status="supported", hits=hits, positives_compared=compared,
        positives_expected=expected, unpaired=unpaired,
        detail=("each positive against its own scramble, which controls "
                "composition where the arm does not. A single hit carries its "
                f"denominator: {expected or compared} positives is "
                f"{expected or compared} chances"))
    return verdict


F268_PAIR = "bench06_RBM39_DCAF15"

# Statuses that are not an outcome, so not an attempt (F330).
#
# `running` has not finished. `abandoned` is what the runner writes when it
# closes out a job a previous runner left behind, which is what happens to
# whatever was on the GPU when a chain is killed: an attempt that did not
# happen. Both belong outside any count of what refinement does, and both
# predictions here count attempts.
NOT_AN_OUTCOME = ("running", "abandoned")


def f268_refinement_size_limit(campaign: Path) -> dict:
    """Does bench06's refinement fail because of its size or its constraint?"""
    verdict = {"finding": "F268",
               "claim": "every bench06 refinement fails, whatever its "
                        "conditioning",
               "falsifier": "a bench06 tier-2 job writes a confidence "
                            "JSON, at either conditioning"}
    state = campaign / "state_tier2.jsonl"
    if not state.exists():
        verdict.update(status="not yet testable",
                       detail="no state_tier2.jsonl: refinement has not run")
        return verdict
    # An abandoned job is not an attempt (F330).
    #
    # The runner writes `abandoned` with no `seconds` when it closes out a
    # job a previous runner left running, which is what happens to whatever
    # was on the GPU when a chain is killed. On 2026-11-08 that made F268
    # report "2 of 5 unconstrained refinement(s) have been attempted" when
    # one of the two was a job I killed: an outcome that did not happen,
    # counted as evidence about what happens.
    #
    # F268's claim is that every bench06 refinement fails. Counting a kill
    # among the failures would let it be scored "supported" on four real
    # failures and one abandonment, which is the denominator rule this
    # project states in `geometry.MEASUREMENT_FAILURES`, in F33 and in F293:
    # a count needs the total it is out of, and an unmeasurable outcome
    # belongs outside it. The job stays in the queue and will run, so the
    # count becomes right by itself.
    attempts: dict[str, list[str]] = {}
    not_attempted: dict[str, list[str]] = {}
    for row in _rows(state):
        job_id = str(row.get("job_id") or "")
        if not job_id.startswith(F268_PAIR + "__"):
            continue
        status = str(row.get("status"))
        if status in NOT_AN_OUTCOME:
            if status != "running":
                not_attempted.setdefault(job_id, []).append(status)
            continue
        attempts.setdefault(job_id, []).append(status)

    verdict["abandoned_not_counted"] = sorted(not_attempted)
    unconstrained = {job: states for job, states in attempts.items()
                     if "__unconstrained__" in job}
    conditioned = {job: states for job, states in attempts.items()
                   if "__conditioned__" in job}
    succeeded = sorted(job for job, states in unconstrained.items()
                       if "done" in states)
    if succeeded:
        verdict.update(
            status="WRONG", unconstrained_done=succeeded,
            conditioned_attempted=len(conditioned),
            detail=("an unconstrained refinement completed, so the failure "
                    "is specific to the pocket constraint rather than to the "
                    "1,223-token size, and the pair is refinable without "
                    "conditioning"))
        return verdict
    # The claim is "whatever its conditioning", and this scored only the
    # unconstrained arm (F333). A conditioned success contradicts the claim
    # as registered, and the job in flight when this was noticed was the
    # conditioned one, so the scorer would have reported "not yet testable"
    # over the evidence that settles it.
    #
    # Added in the falsifying direction only. The bar for "supported" below
    # is still the five queued unconstrained jobs, which is what F258
    # registered, so this change can only ever make my own claim easier to
    # refute and never easier to affirm.
    #
    # The conclusion a conditioned success licenses is not the one above.
    # An unconstrained success would mean the constraint was the cause. A
    # conditioned success means neither size nor constraint was, because
    # this job carries both: it leaves the sample count, which is F306.
    conditioned_done = sorted(job for job, states in conditioned.items()
                              if "done" in states)
    if conditioned_done:
        verdict.update(
            status="WRONG", conditioned_done=conditioned_done,
            unconstrained_attempted=len(unconstrained),
            detail=("a conditioned refinement completed, and the claim is "
                    "that every bench06 refinement fails whatever its "
                    "conditioning. This job carries both the 1,223-token "
                    "size and the pocket constraint, so neither is the "
                    "cause and what remains is the sample count: see F306"))
        return verdict
    # The denominator is the queue, as F258 established: five unconstrained
    # jobs are queued, and "none succeeded" over nothing is not a result.
    queued = len({row["job_id"] for row in _rows(campaign / "queue_tier2.jsonl")
                  if str(row.get("job_id", "")).startswith(F268_PAIR + "__")
                  and "__unconstrained__" in str(row.get("job_id"))})
    if len(unconstrained) < queued:
        verdict.update(
            status="not yet testable", unconstrained_attempted=len(unconstrained),
            unconstrained_queued=queued,
            conditioned_attempted=len(conditioned),
            detail=(f"{len(unconstrained)} of {queued} unconstrained "
                    "refinement(s) have been attempted; the ones still to run "
                    "are where a success would be"))
        return verdict
    verdict.update(
        status="supported", unconstrained_attempted=len(unconstrained),
        unconstrained_queued=queued, conditioned_attempted=len(conditioned),
        detail=("no bench06 refinement completed at either conditioning, so "
                "the limit follows the 1,223-token size rather than the "
                "pocket constraint: the largest refinement that has ever "
                "succeeded is 454 tokens, and bench06's tier-1 jobs at the "
                "same size all succeeded"))
    return verdict


def f306_reduced_sampling_succeeds(campaign: Path) -> dict:
    """Does bench06 refine once its sample count fits the measured budget?

    This is F298's diagnosis in falsifiable form, and it predicts that F268
    is wrong. F268 claims every bench06 refinement fails whatever its
    conditioning; F298 measured that every tier-2 success is at most 454
    tokens and every failure is 1,223, that the same 1,223-token jobs all
    complete at tier-1 settings, and that a failed job writes no predictions
    directory at all. If the sample count is the cause, reducing it to nine
    should produce a confidence JSON.

    Registered because it is the strongest form of the claim and because it
    is about to be tested either way. If every reduced attempt still fails,
    the size story is wrong and needs replacing rather than defending: the
    evidence for it is a correlation across 155 jobs with no overlap, which
    is strong and is not a mechanism, since the process that produced those
    records discarded its own stderr.

    Judged on attempts at either conditioning, and only on those whose
    recorded sample count is below the tier's: an attempt at the full count
    failing again says nothing about this.

    It was unconstrained-only, "matching F268", and F268 was itself scoring
    a narrower thing than it claimed (F333). The claim here is about
    bench06, which is a pair rather than an arm, and the arms differ in
    their constraint and not in their token count, which is what this is
    about. The widening is symmetric: this reports `supported` on the first
    success and `WRONG` on the first failure, so admitting the conditioned
    arm admits evidence in both directions equally.
    """
    verdict = {"finding": "F306",
               "claim": "bench06 refines when its sample count is reduced to "
                        "fit the measured budget, so F268 is wrong",
               "falsifier": "every bench06 tier-2 attempt at a reduced "
                            "sample count fails with no confidence JSON, at "
                            "either conditioning"}
    state = campaign / "state_tier2.jsonl"
    results = campaign / "results_tier2.jsonl"
    if not state.exists():
        verdict.update(status="not yet testable",
                       detail="no state_tier2.jsonl: refinement has not run")
        return verdict

    asked = int(paths.tuning()["campaign"]["tier2_diffusion_samples"])
    # The sample count is recorded on the result, not on the state row, so
    # the two files are joined on job id. A job with no recorded count ran
    # before F298 and is not an attempt at a reduced count.
    samples = {str(row.get("job_id")): row.get("diffusion_samples")
               for row in _rows(results)} if results.exists() else {}

    reduced: dict[str, list[str]] = {}
    abandoned: list[str] = []
    for row in _rows(state):
        job_id = str(row.get("job_id") or "")
        if not job_id.startswith(F268_PAIR + "__"):
            continue
        status = str(row.get("status"))
        # The same exclusion F330 made for F268, here for the same reason
        # and with the opposite consequence. An abandoned reduced attempt
        # counted as a failure would score *this* prediction WRONG on a job
        # that was killed rather than one that failed, so the hole scores
        # against me where F268's scored for me. I wrote this function
        # hours before F330 and gave it two exclusions against evidence
        # arriving early, and none against evidence that never arrived.
        if status in NOT_AN_OUTCOME:
            if status != "running":
                abandoned.append(job_id)
            continue
        count = samples.get(job_id)
        if count is None or int(count) >= asked:
            continue
        reduced.setdefault(job_id, []).append(status)

    verdict["abandoned_not_counted"] = sorted(abandoned)
    if not reduced:
        verdict.update(
            status="not yet testable",
            detail=f"no bench06 attempt has run at fewer than "
                   f"{asked} samples yet, at either conditioning")
        return verdict

    succeeded = sorted(job for job, states in reduced.items()
                       if "done" in states)
    if succeeded:
        verdict.update(
            status="supported", reduced_attempts=len(reduced),
            done=succeeded,
            detail=(f"{len(succeeded)} of {len(reduced)} attempt(s) at a "
                    "reduced sample count completed, so the sample count "
                    "was the cause and F268 is wrong"))
        return verdict
    verdict.update(
        status="WRONG", reduced_attempts=len(reduced),
        detail=(f"all {len(reduced)} attempt(s) at a reduced sample count "
                "still failed, so F298's size story does not explain the "
                "failure and needs replacing"))
    return verdict


# F334's registered baseline. Six bench06 tier-2 attempts had a recorded
# duration when this was written, all 1,223 tokens at 25 diffusion samples,
# 10 recycling steps and potentials on: 9,440, 9,468, 9,492, 9,534, 9,536 and
# 9,602 seconds. Mean 9,512, span 162, which is plus or minus 0.9 per cent
# about the mean across six runs on different days.
#
# Written here rather than in config for the reason this module's docstring
# gives: a prediction's numbers are part of the prediction, and a band in
# `thresholds.toml` is a band that can be widened once the duration is known.
# The six are listed so the mean can be checked rather than taken.
F334_BASELINE_SECONDS = 9512.0
F334_BAND = 0.03


def _reduced_samples(campaign: Path, job_id: str) -> int | None:
    """The samples the runner would give this queued job, or None.

    Imported rather than reimplemented. `runner.sampling_for` is the
    decision and `runner.settings_from_config` is the shape it expects, and
    a second copy of `budget // tokens` here would be one number serving
    two meanings, which is F181. The import is cheap: the runner's
    module-level imports are the standard library, so this costs no torch.
    """
    try:
        from nobble.execute.runner import sampling_for, settings_from_config
    except Exception:                                   # noqa: BLE001
        return None
    for row in _rows(campaign / "queue_tier2.jsonl"):
        if str(row.get("job_id")) != job_id:
            continue
        try:
            samples, _note = sampling_for(row, settings_from_config(tier=2))
        except Exception:                               # noqa: BLE001
            return None
        return int(samples)
    return None


def f334_sampling_buys_no_time(campaign: Path) -> dict:
    """Does cutting the diffusion samples from 25 to nine shorten the job?

    F298 reduced the sample count to make a 1,223-token job fit a budget
    denominated in `tokens x samples`. F325 predicted the reduced job would
    take 9/25 of the full-sample time. F328 falsified the top of that window
    from the job while it ran. This is the end of that line: the claim is
    that the sample count contributes nothing measurable at all, so the
    reduced job lands in the same band as the six full-sample attempts.

    The content is the upper bound. If it runs materially past 9,800
    seconds then something other than the sample count differs between this
    attempt and the six, and F334 says plainly that I do not know what.
    """
    verdict = {"finding": "F334",
               "claim": "cutting the diffusion samples from 25 to nine does "
                        "not shorten the job: it lands within 3 per cent of "
                        "the six-run full-sample mean of 9,512s",
               "falsifier": "a reduced-sample bench06 attempt finishes "
                            "outside 9,227 to 9,797 seconds"}
    state = campaign / "state_tier2.jsonl"
    results = campaign / "results_tier2.jsonl"
    if not state.exists():
        verdict.update(status="not yet testable",
                       detail="no state_tier2.jsonl: refinement has not run")
        return verdict

    asked = int(paths.tuning()["campaign"]["tier2_diffusion_samples"])
    samples = {str(row.get("job_id")): row.get("diffusion_samples")
               for row in _rows(results)} if results.exists() else {}

    low = F334_BASELINE_SECONDS * (1.0 - F334_BAND)
    high = F334_BASELINE_SECONDS * (1.0 + F334_BAND)

    # A running job can only exceed a bound, never fall back below one it
    # has already passed, so its elapsed time can falsify this and can
    # never support it. That asymmetry is what makes reading it safe, and
    # reading it is what stops the scorer saying "not yet testable" about a
    # duration that is already decided: on 2026-11-08 the job passed 9,797
    # seconds still running, which is this claim refuted, and the verdict
    # said undecided because no `seconds` had been written yet. "Undecided"
    # and "decided against me" had the same shape, which is F321 to F324 in
    # the one place where the thing being scored is a prediction of mine.
    #
    # `started_at` is wall clock and `seconds` is the runner's monotonic
    # measure. They start a few milliseconds apart: `started_at` is written
    # immediately before `run_job`, which clears the output directory and
    # then takes its own clock. Checked rather than assumed, because the
    # whole comparison rests on it.
    # The *last* record for each job, not every row that ever said running
    # (F345). `state_tier2.jsonl` is append-only, so a job that ran, failed
    # and was re-run keeps its old `running` row for ever. Scanning every
    # such row made the six 2026-11-06 failures read as still running with
    # `started_at` from two days ago, so all six counted as past the band
    # and the verdict said "7 reduced attempt(s)" where there was one.
    #
    # The conclusion was unaffected, because the one real attempt is
    # outside the band on its own, which is exactly why this needed
    # catching: a wrong count beside a right verdict is the kind of number
    # nobody re-reads. Same shape as F330, which was this file reading an
    # append-only file without asking which record was current.
    latest: dict[str, dict] = {}
    for row in _rows(state):
        job_id = str(row.get("job_id") or "")
        if job_id:
            latest[job_id] = row

    running_over: dict[str, float] = {}
    for job_id, row in latest.items():
        if (str(row.get("status")) != "running"
                or not job_id.startswith(F268_PAIR + "__")):
            continue
        began = row.get("started_at")
        count = samples.get(job_id)
        if count is None:
            # A running job has no results row: `results_tier2.jsonl` is
            # written on success. Its sample count comes from the runner's
            # own decision function against the queue row, rather than from
            # arithmetic repeated here, so the scorer cannot disagree with
            # what the runner actually did.
            count = _reduced_samples(campaign, job_id)
        if began is None or count is None or int(count) >= asked:
            continue
        elapsed = time.time() - float(began)
        if elapsed > high:
            running_over[job_id] = elapsed

    measured: dict[str, float] = {}
    for row in _rows(state):
        job_id = str(row.get("job_id") or "")
        if not job_id.startswith(F268_PAIR + "__"):
            continue
        # A duration is a duration whether the job succeeded or failed:
        # this is about the clock, not the confidence JSON, which is what
        # makes it scoreable either way. `running` and `abandoned` carry no
        # `seconds` and so cannot contribute, which is the F330 exclusion
        # arriving for free rather than by a rule.
        seconds = row.get("seconds")
        if seconds is None:
            continue
        count = samples.get(job_id)
        if count is None or int(count) >= asked:
            continue
        measured[job_id] = float(seconds)

    if not measured:
        if running_over:
            job, elapsed = sorted(running_over.items())[0]
            verdict.update(
                status="WRONG", running_past_the_band={job: round(elapsed)},
                detail=(f"{job} is still running at {elapsed:.0f}s, past the "
                        f"{high:.0f}s top of the band, so the claim is "
                        "refuted whatever it does next: a running job can "
                        "only go further past a bound"))
            return verdict
        verdict.update(
            status="not yet testable",
            detail=(f"no bench06 attempt at fewer than {asked} samples has a "
                    "recorded duration yet"))
        return verdict

    outside = {job: seconds for job, seconds in measured.items()
               if not low <= seconds <= high}
    outside.update(running_over)
    verdict["reduced_durations"] = {job: round(seconds, 1)
                                    for job, seconds in sorted(measured.items())}
    verdict["band_seconds"] = [round(low, 1), round(high, 1)]
    if outside:
        verdict.update(
            status="WRONG", outside_band=sorted(outside),
            detail=(f"{len(outside)} reduced attempt(s) finished outside "
                    f"{low:.0f} to {high:.0f}s, so the sample count is not "
                    "neutral to the duration after all and something else "
                    "differs between this attempt and the six"))
        return verdict
    verdict.update(
        status="supported", reduced_attempts=len(measured),
        detail=(f"{len(measured)} reduced attempt(s) landed inside "
                f"{low:.0f} to {high:.0f}s, so a 64 per cent cut in samples "
                "bought no measurable time and `tokens x samples` prices a "
                "tier-2 job in units that do not track its cost: see F331"))
    return verdict


# F346's registered figures. Job 1 of the ten bench06 refinements completed
# at 13,440.12s with nine diffusion samples. The band is plus or minus five
# per cent, which is three times the worst within-size spread observed among
# jobs that *complete*: by token size with n at least five, the coefficient
# of variation runs 0.33 to 1.66 per cent, worst at 144 tokens, and
# 5 / 1.66 is 3.0. Deliberately generous, because n is one at this size.
#
# This said "five times" first, which is 5 divided by 1 rather than by 1.66.
# A multiple of a measured spread is itself a number and gets the same
# treatment as any other: computed, not asserted.
#
# The reference class is the point. F334 took its band from six jobs that
# stopped early and applied it to one that completes, which is the wrong
# population. These nine are the same pair at other seeds, so a spread
# measured over same-size completing jobs is the right yardstick for them.
F346_REFERENCE_SECONDS = 13440.12
F346_BAND = 0.05


def f346_the_rest_of_bench06_refines(campaign: Path) -> dict:
    """Does the first success generalise to the other nine seeds?

    F306 is supported on one job. That is enough to refute F268, because
    F268 claimed every refinement fails and one did not, but it is not
    enough to establish that bench06 refines at nine samples: one success
    among ten attempts would be a fluke dressed as a mechanism.

    So the nine remaining attempts are registered as a test rather than
    left to accumulate as confirmation. The claim is that every one of
    them completes, which is the strong form, and that each lands within
    five per cent of the first.

    The duration half is secondary and the completion half is what matters.
    A job that completes in 15,000 seconds still refutes nothing about the
    mechanism; a job that exits 0 with no confidence JSON refutes all of it.
    """
    verdict = {"finding": "F346",
               "claim": "every remaining bench06 refinement at nine samples "
                        "completes, each within 5 per cent of the first's "
                        "13,440s",
               "falsifier": "any bench06 refinement at a reduced sample "
                            "count writes no confidence JSON, or lands "
                            "outside 12,768 to 14,112 seconds"}
    state = campaign / "state_tier2.jsonl"
    queue = campaign / "queue_tier2.jsonl"
    if not state.exists():
        verdict.update(status="not yet testable",
                       detail="no state_tier2.jsonl: refinement has not run")
        return verdict

    asked = int(paths.tuning()["campaign"]["tier2_diffusion_samples"])
    queued = sorted({str(row.get("job_id")) for row in _rows(queue)
                     if str(row.get("job_id", "")).startswith(F268_PAIR + "__")})

    # The last record for each job, because the file is append-only and a
    # re-run leaves its old rows behind (F345).
    latest: dict[str, dict] = {}
    for row in _rows(state):
        job_id = str(row.get("job_id") or "")
        if job_id:
            latest[job_id] = row

    # What a job *ran* at, which for a settled job is only ever what its
    # record says. `_reduced_samples` reports what the runner would give a
    # job today, which is right for one that has not run and wrong for one
    # that has: the six 2026-11-06 failures ran at 25 samples and today's
    # budget would give them nine, so projecting their count reported this
    # prediction WRONG on four attempts that were never reduced.
    #
    # The rule is F306's, stated there and now used here too: a settled job
    # with no recorded count ran before F298 and is not an attempt at a
    # reduced count. The six carry `diffusion_samples: None` and the one
    # success carries 9.
    # Three cases, and the middle one is the trap. A job whose last record
    # is a pre-F298 failure has *not* had its reduced attempt: the chain
    # re-runs everything that is not `done`, so it is pending, not failed at
    # nine samples. Counting those four as failures reported this prediction
    # WRONG before its first real attempt had a sibling.
    reducible, ran_reduced = [], {}
    for job in queued:
        row = latest.get(job)
        if row is not None and str(row.get("status")) == "done":
            count = row.get("diffusion_samples")
            if count is None or int(count) >= asked:
                # Completed at the full count, so not this claim's business.
                continue
            reducible.append(job)
            ran_reduced[job] = row
            continue
        # No record, running, abandoned, or a failure that will be re-run.
        if (_reduced_samples(campaign, job) or asked) < asked:
            reducible.append(job)

    low = F346_REFERENCE_SECONDS * (1.0 - F346_BAND)
    high = F346_REFERENCE_SECONDS * (1.0 + F346_BAND)

    done, failed, outside, pending = {}, [], {}, []
    for job in reducible:
        row = ran_reduced.get(job)
        if row is None:
            # Pending. A failure with no recorded count is pending too: it
            # ran before the reduction and the chain re-runs it.
            current = latest.get(job)
            if (current is not None
                    and str(current.get("status")) not in NOT_AN_OUTCOME
                    and str(current.get("status")) != "done"
                    and current.get("diffusion_samples") is not None
                    and int(current["diffusion_samples"]) < asked):
                # A real reduced attempt that failed, which is the falsifier.
                failed.append(job)
                continue
            pending.append(job)
            continue
        seconds = row.get("seconds")
        done[job] = round(float(seconds), 1) if seconds is not None else None
        if seconds is not None and not low <= float(seconds) <= high:
            outside[job] = round(float(seconds), 1)

    verdict.update(reducible=len(reducible), completed=len(done),
                   pending=len(pending), band_seconds=[round(low, 1),
                                                       round(high, 1)])
    if failed:
        verdict.update(
            status="WRONG", failed=sorted(failed),
            detail=(f"{len(failed)} of {len(reducible)} reduced attempt(s) "
                    "wrote no confidence JSON, so the first success does not "
                    "generalise and F306's support was one job"))
        return verdict
    if outside:
        verdict.update(
            status="WRONG", outside_band=outside,
            detail=(f"{len(outside)} completed attempt(s) landed outside "
                    f"{low:.0f} to {high:.0f}s, so a reduced bench06 "
                    "refinement does not have one duration: "
                    f"{sorted(outside.items())[:3]}"))
        return verdict
    if pending:
        verdict.update(
            status="not yet testable",
            detail=(f"{len(done)} of {len(reducible)} reduced attempt(s) have "
                    f"completed and {len(pending)} have not run; the claim is "
                    "about all of them"))
        return verdict
    verdict.update(
        status="supported",
        detail=(f"all {len(done)} reduced bench06 refinement(s) completed, "
                f"each within {low:.0f} to {high:.0f}s, so the first success "
                "was the mechanism rather than a fluke"))
    return verdict


def main(argv: list[str] | None = None) -> int:
    import argparse
    import glob

    parser = argparse.ArgumentParser(description="Score F251, F252 and F253.")
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--brief", action="store_true",
                        help="one line per prediction, for tools/status.sh")
    args = parser.parse_args(argv)

    main_campaign = Path(args.campaign) if args.campaign else None
    if main_campaign is None:
        found = sorted(glob.glob("campaigns/campaign_*"))
        main_campaign = Path(found[-1]) if found else None
    design = sorted(glob.glob("campaigns/design_*"))
    tier_b = sorted(glob.glob("campaigns/tier_b_*"))

    results = [
        f251_refinement_discrimination(main_campaign) if main_campaign
        else {"finding": "F251", "status": "withdrawn",
              "claim": "see F254", "detail": "no campaign on disk"},
        f254_refinement_bridging(main_campaign) if main_campaign
        else {"finding": "F254", "status": "not yet testable",
              "claim": "refinement does not change bridge formation",
              "detail": "no campaign on disk"},
        f252_design_scan_position(Path(design[-1]) if design else None),
        f253_tier_b_bridging(Path(tier_b[-1]) if tier_b else None),
        f268_refinement_size_limit(main_campaign) if main_campaign
        else {"finding": "F268", "status": "not yet testable",
              "claim": "every bench06 refinement fails, whatever its "
                       "conditioning",
              "detail": "no campaign on disk"},
        f306_reduced_sampling_succeeds(main_campaign) if main_campaign
        else {"finding": "F306", "status": "not yet testable",
              "claim": "bench06 refines when its sample count is reduced",
              "detail": "no campaign on disk"},
        f334_sampling_buys_no_time(main_campaign) if main_campaign
        else {"finding": "F334", "status": "not yet testable",
              "claim": "cutting the diffusion samples does not shorten the "
                       "job",
              "detail": "no campaign on disk"},
        f346_the_rest_of_bench06_refines(main_campaign) if main_campaign
        else {"finding": "F346", "status": "not yet testable",
              "claim": "every remaining bench06 refinement completes",
              "detail": "no campaign on disk"},
    ]
    scored = [r for r in results if r["status"] in ("supported", "WRONG",
                                                    "unclear")]
    wrong = [r for r in scored if r["status"] == "WRONG"]
    if args.brief:
        # A status command is scanned, not read. The claim and the falsifier
        # are the same every time once they are registered, so they stay in
        # the full output and the summary carries only what changes.
        print(f"   {len(results)} recorded, {len(scored)} testable, "
              f"{len(wrong)} wrong")
        for row in results:
            note = row["status"]
            if row["status"] == "not yet testable":
                note += f": {row['detail'].split(':')[0]}"
            print(f"   {row['finding']:6} {note}")
        return 1 if wrong else 0

    print(f"registered predictions: {len(results)} recorded, {len(scored)} "
          f"testable, {len(wrong)} wrong\n")
    for row in results:
        print(f"  {row['finding']}  {row['status']}")
        print(f"      claim:     {row['claim']}" if "claim" in row else "")
        if "falsifier" in row:
            print(f"      falsifier: {row['falsifier']}")
        for key in ("pairs", "tier1_rate", "tier2_rate", "move", "position",
                    "substitution", "lift", "hits", "positives_compared",
                    "unpaired"):
            if key in row:
                print(f"      {key}: {json.dumps(row[key])}")
        print(f"      {row['detail']}\n")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
