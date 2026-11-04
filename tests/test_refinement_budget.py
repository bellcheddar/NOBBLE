"""A refinement must not be killed while it is working.

Tier 2 is ten jobs at the end of a fifty-hour campaign. The cap on each was
`job_timeout_seconds * tier2_timeout_multiple`, and the multiple was a guess:
tier 2 had never run, so nothing had measured what ten recycles and
twenty-five diffusion samples cost against three and one.

It can be bounded instead of guessed, from the campaign's own tier-1
timings. On the campaign that selected the first tier-2 pair, six of seven
measured pairs had 4.6 to 10 times the headroom they needed and
`bench06_RBM39_DCAF15` had 0.83: the DCAF15 assembly is 1,223 tokens by
construction, its worst tier-1 job took 918s, and its bound is 7.2 hours
against a 6.0 hour cap. The decile happened to select a 454-token pair. Had
it fallen the other way, ten jobs would each have run six hours and been
killed on course (F100).

Each queued refinement now carries a budget sized from its own pair's
measured tier-1 cost, with the configured cap as a floor, and the budget is
per job rather than per attempt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.execute import tier2  # noqa: E402


def _settings() -> dict:
    return paths.tuning()["campaign"]


def test_the_bound_is_built_from_config_and_not_from_literals():
    settings = _settings()
    expected = (
        int(settings["tier2_diffusion_samples"]) / int(settings["tier1_diffusion_samples"])
        + int(settings["tier2_recycles"]) / int(settings["tier1_recycles"])
    ) * float(settings["tier2_potentials_allowance"])
    assert tier2.scaling_bound() == pytest.approx(expected)
    assert tier2.scaling_bound() > 1, "tier 2 cannot be cheaper than tier 1"


def test_the_bound_double_counts_on_purpose():
    """It applies both ratios to the whole tier-1 time, so it is above the
    weighted sum whatever the unknown split between trunk and diffusion."""
    settings = dict(_settings())
    samples = int(settings["tier2_diffusion_samples"]) / int(settings["tier1_diffusion_samples"])
    recycles = int(settings["tier2_recycles"]) / int(settings["tier1_recycles"])
    allowance = float(settings["tier2_potentials_allowance"])
    for trunk_share in (0.0, 0.25, 0.5, 0.75, 1.0):
        weighted = (trunk_share * recycles + (1 - trunk_share) * samples) * allowance
        assert weighted <= tier2.scaling_bound() + 1e-9, trunk_share


def test_a_small_pair_keeps_the_configured_floor():
    settings = _settings()
    floor = int(settings["job_timeout_seconds"]) * int(settings["tier2_timeout_multiple"])
    budget = tier2.job_budget(166.44, settings)
    assert budget["seconds"] == floor
    assert budget["basis"] == "configured floor"


def test_the_heaviest_construct_gets_more_than_the_floor():
    """The case that would have been abandoned. The DCAF15 assembly is a
    declared exception to the token cap, so this is not an outlier to be
    tuned away: it is in the benchmark by design."""
    settings = _settings()
    floor = int(settings["job_timeout_seconds"]) * int(settings["tier2_timeout_multiple"])
    budget = tier2.job_budget(917.63, settings)
    assert budget["seconds"] > floor
    assert budget["basis"] == "measured tier-1 cost"
    assert budget["seconds"] >= 917.63 * tier2.scaling_bound()


def test_a_pair_with_no_measured_tier_one_falls_back_to_the_floor():
    settings = _settings()
    floor = int(settings["job_timeout_seconds"]) * int(settings["tier2_timeout_multiple"])
    for absent in (None, float("nan")):
        budget = tier2.job_budget(absent, settings)
        assert budget["seconds"] == floor, absent
        assert budget["implied_seconds"] is None
        assert budget["worst_tier1_seconds"] is None


def test_the_budget_never_falls_below_the_floor_at_any_measured_cost():
    settings = _settings()
    floor = int(settings["job_timeout_seconds"]) * int(settings["tier2_timeout_multiple"])
    for seconds in (0.0, 1.0, 60.0, 166.0, 918.0, 5400.0):
        assert tier2.job_budget(seconds, settings)["seconds"] >= floor, seconds


def test_worst_rather_than_median_tier_one_cost(tmp_path):
    """Sizing from a typical job abandons the slow ones, which are exactly
    the jobs a generous budget is for."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    rows = [
        {"pair_id": "p", "status": "done", "seconds": 100.0},
        {"pair_id": "p", "status": "done", "seconds": 900.0},
        {"pair_id": "p", "status": "failed: timeout", "seconds": 5400.0},
        {"pair_id": "q", "status": "done", "seconds": 50.0},
        {"pair_id": "q", "status": "done", "seconds": float("nan")},
    ]
    (campaign / "results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")

    worst = tier2.tier1_worst_seconds(campaign)
    assert worst["p"] == 900.0, "a failed job's wall clock is not a cost to size from"
    assert worst["q"] == 50.0, "a non-finite duration must not become the budget"


def test_a_torn_results_line_does_not_lose_the_budget(tmp_path):
    campaign = tmp_path / "campaign_y"
    campaign.mkdir()
    (campaign / "results.jsonl").write_text(
        json.dumps({"pair_id": "p", "status": "done", "seconds": 300.0}) + "\n"
        + '{"pair_id": "p", "status": "do\n')
    assert tier2.tier1_worst_seconds(campaign) == {"p": 300.0}


def test_a_missing_results_file_is_not_an_error(tmp_path):
    campaign = tmp_path / "campaign_z"
    campaign.mkdir()
    assert tier2.tier1_worst_seconds(campaign) == {}


def test_the_runner_reads_the_budget_the_queue_carries():
    """The wiring, not the arithmetic (F40). A budget computed and never
    read is the shape of F79 and F91."""
    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert 'job.get("timeout_seconds")' in source, (
        "the runner ignores the budget the tier-2 queue writes"
    )


def test_the_budget_is_per_job_and_not_per_attempt():
    """A timeout used to spend the cap twice. Re-running an identical
    command on identical input after a timeout is the one retry certain to
    end the same way, so the retry now draws on what is left: a crash
    retries, an exhausted budget does not."""
    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert "remaining = budget - (time.monotonic() - started)" in source
    assert "boltz_environment(), remaining," in source, (
        "the attempt still gets a full cap rather than the remaining budget"
    )
    assert 'settings["job_timeout_seconds"],\n        )' not in source


def test_the_queue_builder_writes_a_budget_for_every_job(tmp_path, monkeypatch):
    """End to end on a synthetic campaign, because the real one has not
    reached tier 2."""
    campaign = tmp_path / "campaign_build"
    campaign.mkdir()
    jobs = [
        {"job_id": "a__ternary__conditioned__seed1", "pair_id": "heavy",
         "complex_type": "ternary", "tokens": 1223, "seed": 1, "yaml": "a.yaml"},
        {"job_id": "b__ternary__conditioned__seed1", "pair_id": "light",
         "complex_type": "ternary", "tokens": 454, "seed": 1, "yaml": "b.yaml"},
        {"job_id": "c__binary__conditioned__seed1", "pair_id": "heavy",
         "complex_type": "binary", "tokens": 1223, "seed": 1, "yaml": "c.yaml"},
    ]
    (campaign / "queue.jsonl").write_text(
        "\n".join(json.dumps(j) for j in jobs) + "\n")
    (campaign / "results.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"pair_id": "heavy", "status": "done", "seconds": 917.63},
        {"pair_id": "light", "status": "done", "seconds": 166.44},
    ]) + "\n")

    class Selection:
        selected = [{"pair_id": "heavy"}, {"pair_id": "light"}]

    report = tier2.build_tier2_queue(campaign, Selection())
    assert report["status"] == "built"
    queued = [json.loads(line) for line
              in (campaign / "queue_tier2.jsonl").read_text().splitlines() if line.strip()]

    assert len(queued) == 2, "binary jobs must not be refined"
    assert all(job["timeout_seconds"] > 0 for job in queued)
    by_pair = {job["pair_id"]: job["timeout_seconds"] for job in queued}
    assert by_pair["heavy"] > by_pair["light"], (
        "the heavier pair must not get the lighter pair's budget"
    )
    assert set(report["budgets"]) == {"heavy", "light"}
    assert report["budgets"]["heavy"]["basis"] == "measured tier-1 cost"


def test_a_crash_still_retries_and_gets_what_is_left_of_the_budget():
    """The other half of the rule. A crash is not evidence that the budget
    was the problem, so it retries; the retry gets the remainder rather than
    a fresh cap, which is what stopped a job from spending its cap twice."""
    from nobble.execute import runner

    calls = []

    def fake_run_boltz(command, env, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            return "exited", 1, "", "CUDA-ish transient failure"
        return "exited", 1, "", "again"

    original = runner._run_boltz
    runner._run_boltz = fake_run_boltz
    try:
        outcome = runner.run_job(
            {"job_id": "j", "seed": 1, "yaml": "x.yaml", "tokens": 10,
             "timeout_seconds": 120},
            Path("/tmp"), {"recycles": 3, "diffusion_samples": 1,
                           "potentials": False, "device": "mps",
                           "job_timeout_seconds": 5400},
        )
    finally:
        runner._run_boltz = original

    assert len(calls) == 2, "a crash should still get its one retry"
    assert calls[1] <= calls[0], "the retry got a fresh cap rather than the remainder"
    assert outcome.attempts == 2
    assert outcome.status.startswith("failed:")


def test_a_timeout_is_not_retried():
    """An identical command on an identical input, killed for taking too
    long, is killed again. That retry used to cost a second full cap: at the
    old tier-2 setting, twelve hours per job across ten jobs."""
    from nobble.execute import runner

    calls = []

    def fake_run_boltz(command, env, timeout):
        calls.append(timeout)
        return "timeout", None, "", ""

    original = runner._run_boltz
    runner._run_boltz = fake_run_boltz
    try:
        outcome = runner.run_job(
            {"job_id": "j", "seed": 1, "yaml": "x.yaml", "tokens": 10,
             "timeout_seconds": 90},
            Path("/tmp"), {"recycles": 3, "diffusion_samples": 1,
                           "potentials": False, "device": "mps",
                           "job_timeout_seconds": 5400},
        )
    finally:
        runner._run_boltz = original

    assert len(calls) == 1, f"the timeout was retried: {calls}"
    assert outcome.attempts == 1
    assert "total budget of 90s" in outcome.detail, outcome.detail


def test_the_queue_budget_overrides_the_tier_cap_in_the_runner():
    """A budget in the queue that the runner silently ignored would be the
    shape of F79 and F91: computed, written, never read."""
    from nobble.execute import runner

    seen = []

    def fake_run_boltz(command, env, timeout):
        seen.append(timeout)
        return "exited", 0, "", ""

    original = runner._run_boltz
    runner._run_boltz = fake_run_boltz
    try:
        runner.run_job(
            {"job_id": "j", "seed": 1, "yaml": "x.yaml", "tokens": 10,
             "timeout_seconds": 39000},
            Path("/tmp"), {"recycles": 10, "diffusion_samples": 25,
                           "potentials": True, "device": "mps",
                           "job_timeout_seconds": 5400},
        )
    finally:
        runner._run_boltz = original

    assert seen and seen[0] == pytest.approx(39000, abs=5), (
        f"the runner used {seen} rather than the queue's 39000s budget"
    )
