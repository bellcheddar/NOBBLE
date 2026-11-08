"""The watchdog flagged a healthy job, and the number came from elsewhere (F343).

At 03:13:55Z on 2026-11-08 the tier-2 watchdog reported
`bench06_RBM39_DCAF15__ternary__conditioned__seed1__tier2` as overdue:
"210.1 min against 69.4 min expected". The job was alive, at 98 per cent of
a core, and went on working for another half hour.

The arithmetic is exact and the comment at the expectation already stated
it: the job's own tier-1 time of 902s times the measured refinement factor
of 4.614 is 4,162s, and the configured `overdue_multiple` of 3 puts the line
at 12,485s, which is 208.1 minutes. The job passed it.

**The factor is the problem.** It is pooled over *successful* refinements,
which F270 is right about: including bench06's own failures would calibrate
the watchdog on the pathology it exists to notice. But 129 of this
campaign's 149 refinements are under 200 tokens, so the pooled 4.614 is
effectively the smallest band's, and the measured bands run

    0-200     4.596
    200-400   6.107
    400-800   8.076
    800-1600  nothing

bench06 is 1,223 tokens. Its band has no successful refinement, so the
expectation was drawn from jobs three to six times smaller, where the trend
across the measured bands says the factor is biased low exactly there. The
same band's factor including failures is 10.524.

This file's own F74 comment names the error one path down, about the rate
rather than the factor: "a rate borrowed from a different size" needs
recording, because "a reader comparing an overdue verdict against the clock
needs to know the yardstick was not measured at that size". The factor path
had no such awareness and called 4.614 "the measured refinement factor"
without qualification.

So the expectation is declined rather than invented, and the report says so.
The hard per-job bound still applies, and F335 measured that at 4.1 times
the real duration, which is what a stall margin is for.

### The third time this hazard has come up

F320 proposed tightening this watchdog by the sample fraction and F329
withdrew it, because the tightened bound would have fallen below the real
duration. F331 proposed pricing the per-job budget on the measured factor
and F335 withdrew it, having priced the running job and found 141 seconds of
headroom. This one was already in the code and has now fired on healthy
work, which is the same hazard arriving by the route neither proposal took.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE = (ROOT / "nobble" / "execute" / "watchdog.py").read_text()


def test_the_lower_band_edge_is_taken_from_the_configured_bands():
    from nobble.execute import watchdog

    bands = [200.0, 400.0, 800.0, 1600.0, 3200.0]
    assert watchdog._band_lower_edge(150, bands) == 0.0
    assert watchdog._band_lower_edge(199, bands) == 0.0
    assert watchdog._band_lower_edge(200, bands) == 200.0
    assert watchdog._band_lower_edge(454, bands) == 400.0
    assert watchdog._band_lower_edge(1223, bands) == 800.0
    assert watchdog._band_lower_edge(5000, bands) == 3200.0


def test_the_bands_come_from_config_rather_than_the_test():
    """The edges above are the configured ones, not a parallel list."""
    from nobble import paths

    configured = [float(edge) for edge
                  in paths.thresholds()["throughput"]["token_bands"]]
    assert configured == [200.0, 400.0, 800.0, 1600.0, 3200.0], configured


def test_the_expectation_is_declined_for_a_size_that_has_never_completed():
    assert "band_low not in measured_band_edges" in SOURCE, (
        "the watchdog no longer checks whether a refinement factor was "
        "measured at this job's size, so it borrows one from smaller jobs"
    )
    assert "unmeasurable: no tier-2 job of this size" in SOURCE


def test_the_report_says_a_job_could_not_be_judged():
    """"none overdue" over an unjudgeable job reads as a clean verdict."""
    assert "unjudgeable" in SOURCE, (
        "the report no longer distinguishes a job judged and found fine "
        "from one that could not be judged, which is the shape the rest of "
        "this project spent a night removing"
    )
    assert "Bounded by the hard budget only" in SOURCE


def test_the_live_campaign_is_not_reported_overdue():
    """The regression, against the job that exposed it.

    Skips once bench06 has a completed tier-2 job of its size, because then
    the band has a factor and the expectation is measurable: the condition
    this is about will have gone, and the test should say so rather than
    pass on a different situation.
    """
    from nobble.execute import budget, watchdog

    campaign = sorted(ROOT.glob("campaigns/campaign_*"))
    if not campaign:
        pytest.skip("no campaign on this checkout")
    campaign = campaign[-1]
    if not (campaign / "state_tier2.jsonl").exists():
        pytest.skip("no tier-2 state on this checkout")

    observed = budget.measured_scaling(campaign, include_failed=False)
    measured = {float(row["min_tokens"])
                for row in (observed.get("by_band") or [])
                if row.get("factor") is not None}
    if 800.0 in measured:
        pytest.skip("the 800-1600 band now has a completed refinement, so "
                    "the expectation is measurable and F343's condition has "
                    "gone")

    report = watchdog.stall_report(campaign, tier=2)
    large = [job for job in report["running"]
             if (job.get("tokens") or 0) >= 800]
    if not large:
        pytest.skip("no job of the unmeasured size is running")
    assert report["overdue"] == [], (
        "a job whose size has never completed is reported overdue against "
        f"an expectation borrowed from smaller jobs: {report['overdue']}"
    )
    for job in large:
        assert job.get("expected_seconds") is None, job
        assert str(job.get("rate_basis", "")).startswith("unmeasurable"), job


def test_the_failure_exclusion_is_untouched():
    """F270 is why the factor has no data at this size, and it is right.

    Including bench06's failures would give the band a factor of 10.524
    drawn from the failures themselves, so a seventh identical failure
    would read as perfectly healthy. The fix for F343 must not reach for
    that.
    """
    assert "include_failed=False" in SOURCE, (
        "the watchdog now includes failed refinements in its factor, which "
        "calibrates it on the pathology it exists to notice (F270)"
    )
