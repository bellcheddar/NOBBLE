"""What the campaign has spent, and what a tier-2 queue would add (F135).

Gate G1 is judged against `max_compute_hours`, and the projection it was
judged on priced tier 1 only. `curate.diversity.projected_hours` sizes a
selection of pairs at the measured tier-1 rate, which is the right question
when deciding how large a library to select. Nothing asked the same question
about refinement.

Refinement is not a rounding error on top of tier 1. It re-runs the ternary
jobs of the top decile at 25 diffusion samples and 10 recycles against tier
1's 1 and 3, so each job costs several times to tens of times what it cost
the first time, and a decile of a 158-pair campaign is 160 jobs. `tier2.py`
mentions no budget and no gate: each job is given a timeout, which bounds one
job and not the queue, and 160 jobs at a six-hour timeout is 960 hours of
permitted wall clock against a 96-hour gate.

Nothing had gone wrong, because tier 2 has never run. The chain runs it as
soon as tier 1 finishes.

The projection here is a range rather than a number, for the reason
`tier2.scaling_bound` gives: Boltz runs the trunk once per recycle and the
structure module once per diffusion sample, and the split between them is
unknown without instrumenting a run. So tier-2 cost is

    trunk * (r2/r1) + structure * (d2/d1),   trunk + structure = tier1

which is smallest when all of tier 1's time is trunk and largest when all of
it is the structure module. Those two extremes are the range, and on this
campaign's decile they are 31 hours and 235 hours against 73 hours left. One
of those fits and one is three times over.

The gate is judged on the high end, because a budget judged on its optimistic
end is how a budget is overrun. That is deliberately pessimistic and it is
also temporary: the range exists only because tier 2 has never run, and the
first completed refinement collapses it to a measured factor. So the gate
says which end it used and what would collapse it, and a campaign with one
tier-2 result is priced on arithmetic rather than on a bound.
"""
from __future__ import annotations

import json
from pathlib import Path

from nobble import paths
from nobble.numeric import finite

# How a tier-2 job id is built from the tier-1 one it refines. Defined here
# and in `tier2.build_tier2_queue`, and the pairing in `measured_scaling`
# silently finds nothing if the two disagree, so it is pinned by a test.
TIER2_SUFFIX = "__tier2"


def _seconds_of(path: Path, keep) -> tuple[float, int]:
    """Summed `seconds` over the records of `path` that `keep` accepts.

    Torn lines are skipped rather than tolerated into a total, since a
    half-written record has no usable `seconds`. `finite`, not truthiness:
    a NaN is truthy and would poison the sum.
    """
    seconds = 0.0
    jobs = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not keep(record):
            continue
        value = record.get("seconds")
        if not finite(value) or value <= 0:
            continue
        seconds += float(value)
        jobs += 1
    return seconds, jobs


def hours_spent(root: Path | None = None) -> dict:
    """Wall clock already spent, summed over every campaign beside this one.

    Measured rather than projected, and over both tiers.

    Over failures as well as successes, which it did not do. `results.jsonl`
    is appended only when `outcome.status == "done"`, so this read only
    successful work, and a gate whose whole purpose is to catch overspend
    could not see time spent on anything that failed. bench06's refinement
    exits 0 without writing a confidence JSON after about two and a half
    hours a job, ten jobs of it, and all 26 hours of that registered here as
    zero while `remaining = max_hours - spent` reported them as still
    available (F255).

    The failed time comes from the state files, where `outcome.to_dict()` is
    written for every outcome including the failures, with `seconds` intact.
    Only non-`done` records are taken from there: a success appears in both
    files, so summing all of state on top of results would count every
    finished job twice. `running` records carry no `seconds` at all and so
    contribute nothing, which is right, since a job still going has no
    settled cost; `abandoned` records are written without one too, so the
    wall clock of a killed runner is still missing and is the one case this
    cannot account for.
    """
    root = Path(root) if root is not None else paths.CAMPAIGNS
    per_campaign: dict[str, float] = {}
    succeeded_seconds = 0.0
    failed_seconds = 0.0
    jobs = 0
    failed_jobs = 0
    if root.exists():
        for results in sorted(root.glob("*/results*.jsonl")):
            seconds, counted = _seconds_of(results, lambda record: True)
            succeeded_seconds += seconds
            jobs += counted
            key = results.parent.name
            per_campaign[key] = per_campaign.get(key, 0.0) + seconds
        for state in sorted(root.glob("*/state*.jsonl")):
            # `startswith`, because a failure's status carries its reason:
            # "failed: exit 0 but no confidence JSON written", not "failed".
            # An equality test against "done" is the only safe shape here,
            # and the first draft of this measurement compared the other
            # side against "failed" and summed nothing at all.
            seconds, counted = _seconds_of(
                state, lambda record: str(record.get("status")) != "done")
            failed_seconds += seconds
            failed_jobs += counted
            key = state.parent.name
            per_campaign[key] = per_campaign.get(key, 0.0) + seconds
    total = succeeded_seconds + failed_seconds
    return {
        "hours": round(total / 3600.0, 2),
        "jobs": jobs,
        "succeeded_hours": round(succeeded_seconds / 3600.0, 2),
        "failed_hours": round(failed_seconds / 3600.0, 2),
        "failed_jobs": failed_jobs,
        "by_campaign": {k: round(v / 3600.0, 2)
                        for k, v in sorted(per_campaign.items())},
    }


def measured_scaling(campaign: Path, include_failed: bool = True) -> dict:
    """The observed tier-2 over tier-1 factor, if any refinement has run.

    Paired by job id, because the tier-2 job id is the tier-1 one with a
    suffix and the two are the same input at different settings. Pairing by
    pair id instead would divide one pair's refinement by another seed's
    tier-1 time.

    The median over pairs rather than the mean: this sizes a queue, and one
    job that hit a swap storm should not move the factor the whole queue is
    priced at.
    """
    campaign = Path(campaign)
    tier1: dict[str, float] = {}
    tier2: dict[str, tuple[float, int | None]] = {}
    for line in _lines(campaign / "results.jsonl"):
        if line.get("status") != "done":
            continue
        seconds = line.get("seconds")
        if not finite(seconds) or seconds <= 0:
            continue
        tier1[line["job_id"]] = float(seconds)

    # Successes and failures both. A refinement that ran for two and a half
    # hours and wrote no confidence JSON cost two and a half hours, and this
    # factor prices cost. Reading `results_tier2.jsonl` alone excluded them,
    # and they are not a random sample of the queue: they are its largest
    # jobs, so their absence pushed the factor down exactly where it was
    # already too low (F257, and F255 for why the seconds are in the state
    # file in the first place).
    for name in ("results_tier2.jsonl", "state_tier2.jsonl"):
        for line in _lines(campaign / name):
            status = str(line.get("status"))
            if status == "running" or status == "abandoned":
                continue
            # `include_failed` is the difference between pricing a queue and
            # judging whether a running job is healthy, and the two want
            # opposite answers. Pricing wants the failures: a refinement that
            # ran two and a half hours and wrote nothing cost two and a half
            # hours. A stall detector must not have them, because the only
            # jobs in the 800 to 1,600 token band are bench06's own four
            # failures, so an expectation taken from that band would be
            # bench06's failed attempts, and a fifth identical failure would
            # look perfectly healthy: the watchdog calibrated on the
            # pathology it exists to notice (F270).
            if not include_failed and status != "done":
                continue
            seconds = line.get("seconds")
            tokens = line.get("tokens")
            if not finite(seconds) or seconds <= 0:
                continue
            # A record with no token count still prices: it joins the pooled
            # median and is left out of the bands only. Requiring tokens here
            # dropped such a record entirely, which made banding subtract
            # information from the pooled factor it is meant to refine, and
            # two fixtures with no `tokens` field went from a factor of 2.0
            # to none at all.
            tier2.setdefault(line["job_id"],
                             (float(seconds),
                              int(tokens) if finite(tokens) else None))

    ratios: list[float] = []
    banded: dict[tuple[int, int], list[float]] = {}
    edges = [int(edge) for edge in
             paths.thresholds()["throughput"]["token_bands"]]
    failed = 0
    for job_id, (seconds, tokens) in sorted(tier2.items()):
        base = tier1.get(job_id.removesuffix(TIER2_SUFFIX))
        if not base:
            continue
        ratio = seconds / base
        ratios.append(ratio)
        if tokens is not None:
            banded.setdefault(_token_band(tokens, edges), []).append(ratio)
    if not ratios:
        return {"factor": None, "jobs": 0, "by_band": [],
                "basis": "no refinement has run, so the factor is bounded "
                         "rather than measured"}
    ratios.sort()
    by_band = []
    for (low, high), observed in sorted(banded.items()):
        observed.sort()
        by_band.append({
            "min_tokens": low,
            "max_tokens": high or None,
            "jobs": len(observed),
            "factor": round(observed[len(observed) // 2], 3),
            "observed_min": round(observed[0], 3),
            "observed_max": round(observed[-1], 3),
        })
    return {
        "factor": round(ratios[len(ratios) // 2], 3),
        "jobs": len(ratios),
        "observed_min": round(ratios[0], 3),
        "observed_max": round(ratios[-1], 3),
        "by_band": by_band,
        "basis": f"median of {len(ratios)} refinement(s) against their own "
                 "tier-1 job, banded by job size because the ratio is not "
                 "constant across it",
    }


def _lines(path: Path):
    """Parsed JSONL records, skipping torn lines rather than failing on one."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _token_band(tokens: int, edges: list[int]) -> tuple[int, int]:
    """The band a job of this size falls in, high exclusive, 0 for the top.

    The same rule as `runner.token_band`, repeated here rather than imported
    because `runner` imports this module and the cycle is not worth a
    deferred import for eight lines. A test holds the two in step.
    """
    low = 0
    for edge in edges:
        if tokens < edge:
            return (low, edge)
        low = edge
    return (low, 0)


def band_factors(observed: dict, tokens: int) -> tuple[float, float, float]:
    """The (median, min, max) tier-2 factor for a job of this size.

    The band's own figures where its band has been measured, and the pooled
    ones where it has not. One pooled factor prices every job as if it were
    the commonest size: 129 of the main campaign's 149 refinements are under
    200 tokens, so the pooled 4.614 is effectively the smallest band's, and
    the ratio runs 4.60, 6.11, 8.21 and 10.5 as jobs grow (F257).
    """
    edges = [int(edge) for edge in
             paths.thresholds()["throughput"]["token_bands"]]
    low, high = _token_band(int(tokens), edges)
    for band in observed.get("by_band") or []:
        if band["min_tokens"] == low and (band["max_tokens"] or 0) == (high or 0):
            return (band["factor"], band["observed_min"], band["observed_max"])
    return (observed["factor"], observed.get("observed_min", observed["factor"]),
            observed.get("observed_max", observed["factor"]))


def scaling_range(settings: dict | None = None,
                  campaign: Path | None = None) -> tuple[float, float]:
    """Smallest and largest factor by which a tier-2 job can exceed tier 1.

    The recycle ratio if all of tier 1's time is the trunk, the diffusion
    ratio if all of it is the structure module. Both come from config.

    Collapses to the measured factor once a refinement has run, because then
    the split is no longer unknown.
    """
    if campaign is not None:
        observed = measured_scaling(campaign)
        if observed["factor"] is not None:
            return (observed["factor"], observed["factor"])
    settings = settings or paths.tuning()["campaign"]
    recycles = (int(settings["tier2_recycles"])
                / int(settings["tier1_recycles"]))
    samples = (int(settings["tier2_diffusion_samples"])
               / int(settings["tier1_diffusion_samples"]))
    return (min(recycles, samples), max(recycles, samples))


def tier2_projection(campaign: Path, pair_ids: list[str] | None = None,
                     settings: dict | None = None) -> dict:
    """Hours a tier-2 queue would cost, as a range, from measured tier-1 time.

    Priced from the campaign's own completed tier-1 results for the jobs that
    would be refined, so a pair whose construct is large is priced as large.
    A pair with no completed tier-1 ternary job cannot be priced and is
    counted in `unpriced` rather than assumed cheap.
    """
    campaign = Path(campaign)
    settings = settings or paths.tuning()["campaign"]
    low, high = scaling_range(settings, campaign)
    observed = measured_scaling(campaign)

    results = campaign / "results.jsonl"
    measured: dict[str, tuple[float, int]] = {}
    if results.exists():
        for record in _lines(results):
            if record.get("status") != "done":
                continue
            seconds = record.get("seconds")
            if not finite(seconds) or seconds <= 0:
                continue
            # Only the ternary jobs are refined, so only they are priced.
            if record.get("complex_type") != "ternary":
                continue
            measured[record["job_id"]] = (float(seconds),
                                          int(record.get("tokens") or 0))

    queue = campaign / "queue.jsonl"
    refine: list[str] = []
    if queue.exists():
        for job in paths.read_jsonl(queue):
            if job.get("complex_type") != "ternary":
                continue
            if pair_ids is not None and job.get("pair_id") not in pair_ids:
                continue
            refine.append(job["job_id"])

    priced = [measured[job] for job in refine if job in measured]
    unpriced = len(refine) - len(priced)
    tier1_seconds = sum(seconds for seconds, _ in priced)

    # Each job at its own band's factor, rather than the whole total at one
    # pooled factor. The ratio rises with job size, 4.60 to 10.5 across the
    # bands, and the pooled median is effectively the smallest band's because
    # that band holds most of the jobs. Pricing a large-job remainder at it
    # underpriced this campaign's by about 26 hours (F257), which is F45's
    # lesson about flat rates in the one instrument it had not reached.
    low_seconds = 0.0
    high_seconds = 0.0
    mid_seconds = 0.0
    for seconds, tokens in priced:
        factor, band_low, band_high = band_factors(observed, tokens)
        if factor is None:
            low_seconds += seconds * low
            high_seconds += seconds * high
            mid_seconds += seconds * (low + high) / 2.0
            continue
        low_seconds += seconds * band_low
        high_seconds += seconds * band_high
        mid_seconds += seconds * factor

    # An unpriced job is charged the mean of the priced ones rather than
    # nothing. Pessimism is the wrong word for it: charging nothing is a
    # projection that gets cheaper the less of the campaign has run.
    if priced and unpriced:
        tier1_seconds += unpriced * (tier1_seconds / len(priced))
        low_seconds += unpriced * (low_seconds / len(priced))
        high_seconds += unpriced * (high_seconds / len(priced))
        mid_seconds += unpriced * (mid_seconds / len(priced))
    # And when there is nothing to take a mean of, the answer is not zero.
    #
    # With no completed ternary job the sum above is 0, the guard above does
    # not fire because `priced` is empty, and this returned 0.0 hours and a
    # gate that fits. `test_an_unpriced_job_is_not_a_free_job` was written
    # for exactly this and exercised only the partial case, three of four
    # unpriced, so it passed while the all-unpriced case charged nothing
    # (F161). Reachable from `status.sh`, which prices any campaign
    # including one that started a minute ago.
    priceable = bool(priced) or not refine

    return {
        "jobs": len(refine),
        "priced_jobs": len(priced),
        "unpriced_jobs": unpriced,
        "priceable": priceable,
        "tier1_hours_for_those_jobs": round(tier1_seconds / 3600.0, 2),
        # The effective aggregate ratio, so the reported factor and the
        # reported hours still agree with each other once the per-job
        # factors differ.
        "scaling_low": round(low_seconds / tier1_seconds, 2)
                       if tier1_seconds else round(low, 2),
        "scaling_high": round(high_seconds / tier1_seconds, 2)
                        if tier1_seconds else round(high, 2),
        "hours_low": round(low_seconds / 3600.0, 2),
        "hours_mid": round(mid_seconds / 3600.0, 2),
        "hours_high": round(high_seconds / 3600.0, 2),
        "measured_scaling": observed,
        "basis": (
            "measured tier-1 seconds for the ternary jobs that would be "
            "refined, times " + (
                f"each job's own band factor, pooled median "
                f"{observed['factor']} over "
                f"{len(observed.get('by_band') or [])} band(s)"
                if observed["factor"] is not None else
                "the recycle ratio for the low end and the diffusion-sample "
                "ratio for the high end"
            )
        ),
    }


def gate_g1(campaign: Path, pair_ids: list[str] | None = None) -> dict:
    """Does refinement fit inside what is left of max_compute_hours?

    Judged on the high end, so a refusal means the cheapest reading of the
    cost still does not fit. The line below says so and `judged_on` reports
    it as "upper bound", or "measured factor" once a refinement has run and
    the two ends are the same number.

    This docstring said "the low end" while the code read `hours_high`,
    which is the opposite claim about a Gate. Nothing downstream read the
    docstring, so nothing was wrong except what a reader would have believed
    about when G1 opens; the test below now pins the end the code uses, so
    the two cannot part again.
    """
    tuning = paths.tuning()["campaign"]
    max_hours = float(tuning["max_compute_hours"])
    # Accounted over the directory this campaign lives in, not over
    # `paths.CAMPAIGNS`. They are the same thing for a real campaign, and
    # for a fixture they are not: a gate that reads the live spend answers a
    # different question every time the running campaign finishes a job,
    # which makes a test of it a test of the campaign's progress (F131).
    spent = hours_spent(Path(campaign).parent)
    projection = tier2_projection(campaign, pair_ids, tuning)
    remaining = max_hours - spent["hours"]
    # The high end, because the question is whether starting this is safe.
    # Once a refinement has run the two ends are the same number.
    fits = projection["hours_high"] <= remaining
    collapsed = projection["measured_scaling"]["factor"] is not None

    # Nothing priced is not the same as nothing to pay. A queue with jobs in
    # it and no measurement behind any of them cannot be said to fit, and
    # saying so is different from saying the gate is open: the gate is about
    # a cost that exceeds the budget, and this is a cost nobody knows.
    if not projection["priceable"]:
        return {
            "max_compute_hours": max_hours,
            "hours_spent": spent["hours"],
            "hours_remaining": round(remaining, 2),
            "tier2": projection,
            "fits": False,
            "gate_g1_open": False,
            "judged_on": "nothing measured",
            "verdict": (
                f"cannot price {projection['jobs']} refinement job(s): no "
                "tier-1 ternary job of this campaign has completed, so there "
                "is no measured cost to scale. This is not a gate and not a "
                "fit; it is a refusal to guess"
            ),
            "spent_by_campaign": spent["by_campaign"],
        }
    return {
        "max_compute_hours": max_hours,
        "hours_spent": spent["hours"],
        "hours_remaining": round(remaining, 2),
        "tier2": projection,
        "fits": fits,
        "gate_g1_open": not fits,
        "judged_on": "measured factor" if collapsed else "upper bound",
        "verdict": (
            # "exceeds" here too. This branch is the measured case of a
            # cost that does not fit, and it was the only one of the four
            # that stated no conclusion: "refinement costs 150.0 h against
            # 67.7 h remaining of the 96 h budget", leaving the reader to
            # do the comparison. It is also the branch that opens Gate G1,
            # and it read almost identically to the passing verdict, where
            # the distinguishing words were "or less" (F201).
            (f"refinement costs {projection['hours_high']} h, which exceeds "
             f"the {round(remaining, 2)} h remaining of the {max_hours} h "
             "budget"
             if collapsed else
             f"refinement costs {projection['hours_low']} to "
             f"{projection['hours_high']} h, and the upper end exceeds the "
             f"{round(remaining, 2)} h remaining of the {max_hours} h budget. "
             "One completed refinement replaces the range with a measured "
             "factor")
            if not fits else
            f"refinement costs {projection['hours_high']} h or less against "
            f"{round(remaining, 2)} h remaining"
        ),
        "spent_by_campaign": spent["by_campaign"],
    }


def affordable_pairs(campaign: Path, ranked: list[str]) -> dict:
    """The longest prefix of a ranking whose refinement fits the budget.

    Automatic scope reduction, which is what Gate G1 is defined against: the
    gate opens when the minimum viable set does not fit, not when the
    requested set does not. Pairs are dropped from the bottom of the ranking,
    never seeds from a pair: Delta-ipTM is a difference of minima over seeds,
    so a pair refined with fewer seeds than its own tier-1 arm is not a
    cheaper measurement of the same thing.
    """
    # Whether the requested set can be priced at all, asked of the requested
    # set. Taking it from `last` below asks it of whatever prefix proved
    # affordable, and the first of those is the empty prefix, which has no
    # jobs and so is trivially priceable: the flag came back False for a
    # campaign that cannot be priced at all (F161).
    requested = tier2_projection(campaign, list(ranked))

    affordable: list[str] = []
    last = gate_g1(campaign, [])
    for pair in ranked:
        trial = affordable + [pair]
        report = gate_g1(campaign, trial)
        if not report["fits"]:
            break
        affordable, last = trial, report

    # "Costs too much" and "cost unknown" are different answers and only the
    # first is a gate. Treating them alike opened Gate G1 on a campaign that
    # had simply not finished a job yet, which in unattended mode stops the
    # build and asks for a decision nobody can make from the evidence
    # (F161).
    unpriceable = bool(ranked) and not requested["priceable"]
    return {
        "requested": list(ranked),
        "affordable": affordable,
        "dropped": [p for p in ranked if p not in affordable],
        "report": last,
        "unpriceable": unpriceable,
        # Nothing affordable is the gate. One pair refined is a result; zero
        # is a question for whoever owns the budget. Unless the reason
        # nothing is affordable is that nothing has been measured, which is
        # a question for the clock.
        "gate_g1_open": not affordable and bool(ranked) and not unpriceable,
    }
