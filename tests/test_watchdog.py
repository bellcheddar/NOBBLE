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
    """If the runner's timeout or retries change, the bound must follow."""
    settings = runner.settings_from_config(tier=1)
    expected = (settings["job_timeout_seconds"] * (runner.RETRIES + 1)
                + runner.KILL_GRACE_SECONDS)
    assert watchdog.hard_bound_seconds() > expected
    # tier 2 jobs get a longer timeout, so a longer bound
    assert watchdog.hard_bound_seconds(tier=2) > watchdog.hard_bound_seconds(tier=1)


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
