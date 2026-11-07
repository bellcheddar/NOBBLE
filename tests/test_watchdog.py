"""A stalled campaign must be distinguishable from a working one.

This exists because of a reasoning error, not a code failure (F20). A job
that had been running 13 minutes was read as having run 5h13m, because the
elapsed time was worked out by hand from `stat` local time against `date -u`
on a machine five hours off UTC. The job was healthy and was killed.

The campaign already records `started_at` as a Unix timestamp. These tests
pin that the answer is computed from it, in one frame, with a bound that
comes from the runner's own configuration rather than from a guess.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.execute import runner, watchdog  # noqa: E402

TOKENS = 1287
RATE = 0.826                      # s/token, as the real campaign ran
TYPICAL = TOKENS * RATE           # about 1,063 s


def _campaign(tmp_path: Path, running_started_at: float) -> Path:
    """A campaign with one finished job and one still running."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text(
        json.dumps({"job_id": "done1", "tokens": TOKENS, "pair_id": "p"}) + "\n"
        + json.dumps({"job_id": "live1", "tokens": TOKENS, "pair_id": "p"}) + "\n"
    )
    (campaign / "state.jsonl").write_text(
        json.dumps({"job_id": "done1", "status": "done",
                    "seconds": TYPICAL, "tokens": TOKENS}) + "\n"
        + json.dumps({"job_id": "live1", "status": "running",
                      "started_at": running_started_at}) + "\n"
    )
    return campaign


def test_a_job_running_a_normal_length_of_time_is_not_flagged():
    """The exact case I got wrong: 13 minutes into a 17.7 minute job."""
    now = 1_793_772_308.0
    campaign = _campaign(Path(__import__("tempfile").mkdtemp()), now - 13 * 60)
    report = watchdog.stall_report(campaign, now=now)
    assert report["stalled"] == []
    assert report["overdue"] == []
    assert len(report["running"]) == 1
    assert report["running"][0]["elapsed_seconds"] == 780.0


def test_a_job_past_the_runners_own_bound_is_stalled(tmp_path):
    now = 1_793_772_308.0
    bound = watchdog.hard_bound_seconds()
    campaign = _campaign(tmp_path, now - (bound + 60))
    report = watchdog.stall_report(campaign, now=now)
    assert [job["job_id"] for job in report["stalled"]] == ["live1"]


def test_the_bound_comes_from_the_runner_not_from_a_constant():
    """If the runner's timeout changes, the bound must follow.

    This test used to multiply by `RETRIES + 1`, which was the runner's
    arithmetic until F100 made the budget cover the job rather than each
    attempt. Keeping it pinned the stale model: the bound was twice what the
    runner can allow, so a hung runner went uncalled for an extra hour and a
    half at tier 1 and six at tier 2.
    """
    settings = runner.settings_from_config(tier=1)
    budget = settings["job_timeout_seconds"]
    bound = watchdog.hard_bound_seconds()
    assert bound > budget + runner.KILL_GRACE_SECONDS, bound
    # The margin is the only thing above the runner's own allowance, so the
    # bound must not reach a second attempt's worth.
    assert bound < budget * (runner.RETRIES + 1), (
        f"the bound {bound} still allows a second full attempt, which the "
        "runner's per-job budget does not")
    # tier 2 jobs get a longer timeout, so a longer bound
    assert watchdog.hard_bound_seconds(tier=2) > watchdog.hard_bound_seconds(tier=1)


def test_a_jobs_own_timeout_override_sets_its_bound():
    """The runner reads `job.get("timeout_seconds") or settings[...]`.

    A bound taken from the tier default alone does not follow the runner: the
    main campaign's tier-2 rows carry 39,000 seconds against a tier default
    of 21,600, so the default bound would call such a job stalled at 22,320
    while the runner was still legitimately inside its allowance.
    """
    default = watchdog.hard_bound_seconds(tier=2)
    overridden = watchdog.hard_bound_seconds(tier=2, job_timeout_seconds=39000)
    assert overridden > default, (overridden, default)
    assert overridden > 39000, overridden


def test_a_merely_slow_job_is_overdue_rather_than_stalled(tmp_path):
    """Advisory, not a verdict: Boltz timings vary."""
    now = 1_793_772_308.0
    campaign = _campaign(tmp_path, now - 4 * TYPICAL)
    report = watchdog.stall_report(campaign, now=now)
    assert [job["job_id"] for job in report["overdue"]] == ["live1"]
    assert report["stalled"] == []


def test_elapsed_is_computed_from_the_epoch_not_from_formatted_time(tmp_path):
    """The actual lesson of F20, pinned.

    An epoch timestamp has no timezone, so the same stamp must give the same
    elapsed time whatever TZ the process happens to be running under. The
    5-hour error came from mixing two formatted clocks; this cannot.
    """
    import os
    import time as time_module

    now = 1_793_772_308.0
    campaign = _campaign(tmp_path, now - 780)
    answers = []
    original = os.environ.get("TZ")
    try:
        for zone in ("UTC", "EST5EDT", "Asia/Tokyo"):
            os.environ["TZ"] = zone
            time_module.tzset()
            answers.append(
                watchdog.stall_report(campaign, now=now)["running"][0]["elapsed_seconds"]
            )
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time_module.tzset()

    assert answers == [780.0, 780.0, 780.0], answers


def test_one_pathological_job_does_not_blunt_the_yardstick(tmp_path):
    """The scale is a median, as it is everywhere else in the runner.

    The first version of this took the slowest completed job as the
    yardstick. One job whose recorded time included a killed attempt then
    nearly doubled the overdue threshold for every job after it, which is
    exactly the failure runner.throughput() already avoids by using a
    median rather than a mean.
    """
    now = 1_793_772_308.0
    campaign = tmp_path / "campaign_y"
    campaign.mkdir()
    queue, state = [], []
    # Nine normal jobs and one that took twice as long.
    for index in range(9):
        queue.append({"job_id": f"d{index}", "tokens": TOKENS, "pair_id": "p"})
        state.append({"job_id": f"d{index}", "status": "done",
                      "seconds": TYPICAL, "tokens": TOKENS})
    queue.append({"job_id": "slow", "tokens": TOKENS, "pair_id": "p"})
    state.append({"job_id": "slow", "status": "done",
                  "seconds": TYPICAL * 2, "tokens": TOKENS})
    # A job running well past three normal jobs' worth of time.
    queue.append({"job_id": "live1", "tokens": TOKENS, "pair_id": "p"})
    state.append({"job_id": "live1", "status": "running",
                  "started_at": now - 3.5 * TYPICAL})

    (campaign / "queue.jsonl").write_text(
        "\n".join(json.dumps(r) for r in queue) + "\n")
    (campaign / "state.jsonl").write_text(
        "\n".join(json.dumps(r) for r in state) + "\n")

    report = watchdog.stall_report(campaign, now=now)
    assert [job["job_id"] for job in report["overdue"]] == ["live1"], (
        "the outlier raised the threshold and hid a genuinely overdue job"
    )


def _tier2_campaign(tmp_path: Path, elapsed: float, now: float,
                    *, small_tokens: int = 150, big_tokens: int = 1223,
                    tier1_seconds: float = 902.0) -> Path:
    """A tier-2 queue whose running job is far larger than anything finished.

    Which is the real shape: of 149 finished tier-2 jobs the largest was 454
    tokens and the running one is 1,223 (F233).
    """
    from nobble.execute import budget

    campaign = tmp_path / "campaign_t2"
    campaign.mkdir()
    big = f"pairBig__ternary__unconstrained__seed1{budget.TIER2_SUFFIX}"
    small = f"pairSmall__ternary__unconstrained__seed1{budget.TIER2_SUFFIX}"
    (campaign / "queue_tier2.jsonl").write_text(
        json.dumps({"job_id": small, "tokens": small_tokens, "pair_id": "pairSmall"}) + "\n"
        + json.dumps({"job_id": big, "tokens": big_tokens, "pair_id": "pairBig"}) + "\n"
    )
    # A finished small refinement, giving both a rate and a factor.
    (campaign / "state_tier2.jsonl").write_text(
        json.dumps({"job_id": small, "status": "done",
                    "seconds": small_tokens * 2.237, "tokens": small_tokens}) + "\n"
        + json.dumps({"job_id": big, "status": "running",
                      "started_at": now - elapsed}) + "\n"
    )
    (campaign / "results_tier2.jsonl").write_text(
        json.dumps({"job_id": small, "status": "done",
                    "seconds": small_tokens * 2.237}) + "\n")
    # Tier-1 times for both, so the factor is measurable and the big job has
    # a time of its own.
    (campaign / "results.jsonl").write_text(
        json.dumps({"job_id": small.removesuffix(budget.TIER2_SUFFIX),
                    "status": "done", "seconds": small_tokens * 2.237 / 4.614}) + "\n"
        + json.dumps({"job_id": big.removesuffix(budget.TIER2_SUFFIX),
                      "status": "done", "seconds": tier1_seconds}) + "\n")
    return campaign, big


def test_a_large_refinement_is_priced_from_its_own_tier_one_time(tmp_path):
    """A tier-2 job is the same input at different settings.

    So its tier-1 time measures that exact molecule, where a per-token rate
    measures other jobs of other sizes. On the job this was found with, tier 1
    took 902s and the measured factor 4.614 gives 4,162s, against an attempt
    that really ran about 5,040s; the flat median said 2,736s.
    """
    now = 1_793_772_308.0
    campaign, big = _tier2_campaign(tmp_path, elapsed=6_600.0, now=now)
    report = watchdog.stall_report(campaign, tier=2, now=now)

    assert [job["job_id"] for job in report["running"]] == [big]
    assert report["overdue"] == [], report["overdue"]
    assert report["stalled"] == []


def test_the_flat_median_would_have_flagged_it(tmp_path):
    """The premise. If both yardsticks agreed, this would change nothing.

    At 2.237 s/token a 1,223-token job is expected at 2,736s and overdue at
    three times that, 8,208s. The job below is past that line and inside the
    scaled one, so the two verdicts differ and the scaled one is the one that
    matches what the job really takes.
    """
    now = 1_793_772_308.0
    campaign, _ = _tier2_campaign(tmp_path, elapsed=9_000.0, now=now)
    multiple = float(paths.thresholds()["watchdog"]["overdue_multiple"])
    flat_line = multiple * 2.237 * 1223
    assert 9_000.0 > flat_line, flat_line

    report = watchdog.stall_report(campaign, tier=2, now=now)
    assert report["overdue"] == [], (
        "the flat per-token rate is still deciding the verdict")


def test_a_refinement_with_no_tier_one_time_says_what_it_fell_back_to(tmp_path):
    """Unknown yardstick, stated. A rate borrowed from a different size is
    the thing being corrected, so a reader checking an overdue verdict
    against the clock has to be told."""
    now = 1_793_772_308.0
    # Past the overdue line for the fallback rate (8,208s) and inside the
    # stall bound (22,320s), because stalled is asked first and would never
    # reach the branch under test.
    campaign, big = _tier2_campaign(tmp_path, elapsed=10_000.0, now=now)
    # Remove the big job's tier-1 row, leaving the small one so a factor
    # is still measurable.
    rows = [line for line in (campaign / "results.jsonl").read_text().splitlines()
            if "pairBig" not in line]
    (campaign / "results.jsonl").write_text("\n".join(rows) + "\n")

    report = watchdog.stall_report(campaign, tier=2, now=now)
    assert report["overdue"], report
    basis = report["overdue"][0]["rate_basis"]
    assert "no rate measured at this size" in basis, basis
