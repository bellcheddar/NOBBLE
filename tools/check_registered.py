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

    # Both classes present, rather than a minimum count. An AUC needs at
    # least one of each and a count would be a cutoff deciding when the
    # prediction becomes scoreable, which is the sort of number that belongs
    # in config or nowhere.
    labels = {row[0] for row in paired}
    if labels != set(layers.ROC_LABELS):
        verdict.update(status="not yet testable",
                       detail=f"{len(paired)} refined Sievers pair(s) carry "
                              f"both tiers' delta, covering {sorted(labels)}: "
                              "an AUC needs both classes")
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


def f268_refinement_size_limit(campaign: Path) -> dict:
    """Does bench06's refinement fail because of its size or its constraint?"""
    verdict = {"finding": "F268",
               "claim": "every bench06 refinement fails, whatever its "
                        "conditioning",
               "falsifier": "an unconstrained bench06 tier-2 job writes a "
                            "confidence JSON"}
    state = campaign / "state_tier2.jsonl"
    if not state.exists():
        verdict.update(status="not yet testable",
                       detail="no state_tier2.jsonl: refinement has not run")
        return verdict
    attempts: dict[str, list[str]] = {}
    for row in _rows(state):
        job_id = str(row.get("job_id") or "")
        if not job_id.startswith(F268_PAIR + "__"):
            continue
        status = str(row.get("status"))
        if status == "running":
            continue
        attempts.setdefault(job_id, []).append(status)

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

    Judged on unconstrained jobs only, matching F268, and only on attempts
    whose recorded sample count is below the tier's: an attempt at the full
    count failing again says nothing about this.
    """
    verdict = {"finding": "F306",
               "claim": "bench06 refines when its sample count is reduced to "
                        "fit the measured budget, so F268 is wrong",
               "falsifier": "every unconstrained bench06 tier-2 attempt at a "
                            "reduced sample count fails with no confidence "
                            "JSON"}
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
    for row in _rows(state):
        job_id = str(row.get("job_id") or "")
        if (not job_id.startswith(F268_PAIR + "__")
                or "__unconstrained__" not in job_id):
            continue
        status = str(row.get("status"))
        if status == "running":
            continue
        count = samples.get(job_id)
        if count is None or int(count) >= asked:
            continue
        reduced.setdefault(job_id, []).append(status)

    if not reduced:
        verdict.update(
            status="not yet testable",
            detail=f"no unconstrained bench06 attempt has run at fewer than "
                   f"{asked} samples yet")
        return verdict

    succeeded = sorted(job for job, states in reduced.items()
                       if "done" in states)
    if succeeded:
        verdict.update(
            status="supported", reduced_attempts=len(reduced),
            done=succeeded,
            detail=(f"{len(succeeded)} of {len(reduced)} unconstrained "
                    "attempt(s) at a reduced sample count completed, so the "
                    "sample count was the cause and F268 is wrong"))
        return verdict
    verdict.update(
        status="WRONG", reduced_attempts=len(reduced),
        detail=(f"all {len(reduced)} unconstrained attempt(s) at a reduced "
                "sample count still failed, so F298's size story does not "
                "explain the failure and needs replacing"))
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
