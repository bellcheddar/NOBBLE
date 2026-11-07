"""One measurement, two purposes, opposite requirements about failures.

`budget.measured_scaling` gives the factor by which refinement multiplies a
tier-1 job's time. Two callers want it. `tier2_projection` prices a queue, and
F257 widened the measurement to include failed refinements because a job that
ran two and a half hours and wrote nothing cost two and a half hours.
`watchdog` asks whether a running job is behaving like a healthy one.

The second must not see the failures. On this campaign the only jobs in the
800 to 1,600 token band are bench06's own four failed refinements, at ratios
10.46 to 10.58. An expectation drawn from that band is the duration of the
failure itself, so a fifth identical failure would sit comfortably inside it
and never read as overdue: the watchdog calibrated on the pathology it exists
to notice (F270).

So `include_failed` is a parameter rather than a policy, and the two callers
pass what their question needs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import budget


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _campaign(root: Path) -> Path:
    """Small jobs that refined cleanly, and one large one that only failed."""
    directory = root / "campaign_two_purposes"
    directory.mkdir()
    tier1, tier2, state = [], [], []
    for index in range(6):
        job = f"small{index}__ternary__conditioned__seed1"
        tier1.append({"job_id": job, "status": "done", "seconds": 100.0,
                      "tokens": 150, "complex_type": "ternary"})
        tier2.append({"job_id": job + budget.TIER2_SUFFIX, "status": "done",
                      "seconds": 400.0, "tokens": 150})
        state.append({"job_id": job + budget.TIER2_SUFFIX, "status": "done",
                      "seconds": 400.0, "tokens": 150})
    for index in range(3):
        job = f"big{index}__ternary__conditioned__seed1"
        tier1.append({"job_id": job, "status": "done", "seconds": 100.0,
                      "tokens": 1200, "complex_type": "ternary"})
        state.append({"job_id": job + budget.TIER2_SUFFIX,
                      "status": "failed: exit 0 but no confidence JSON "
                                "written", "seconds": 1000.0, "tokens": 1200})
    _write(directory / "results.jsonl", tier1)
    _write(directory / "results_tier2.jsonl", tier2)
    _write(directory / "state_tier2.jsonl", state)
    return directory


def test_pricing_sees_the_failures(tmp_path):
    observed = budget.measured_scaling(_campaign(tmp_path))
    bands = {band["min_tokens"]: band for band in observed["by_band"]}
    assert bands[800]["jobs"] == 3, observed
    assert bands[800]["factor"] == 10.0, observed


def test_stall_detection_does_not(tmp_path):
    observed = budget.measured_scaling(_campaign(tmp_path), include_failed=False)
    bands = {band["min_tokens"]: band for band in observed["by_band"]}
    assert 800 not in bands, observed
    assert observed["factor"] == 4.0, observed


def test_the_expectation_for_a_large_job_is_not_its_own_failure(tmp_path):
    """The whole point, stated as the number it decides.

    With the failures in, a 1,200-token job is expected to take what the
    failures took, so a repeat of the failure is never overdue. Without them,
    the expectation falls back to the pooled factor of the jobs that worked.
    """
    directory = _campaign(tmp_path)
    priced = budget.measured_scaling(directory)
    judged = budget.measured_scaling(directory, include_failed=False)
    assert budget.band_factors(priced, 1200)[0] == 10.0
    assert budget.band_factors(judged, 1200)[0] == 4.0


def test_an_unmeasured_band_falls_back_rather_than_to_nothing(tmp_path):
    """Excluding the failures must not leave the factor undefined.

    If it did, the watchdog would lose its tier-2 yardstick entirely and
    fall back to a rate per token, which is the thing F235 replaced.
    """
    judged = budget.measured_scaling(_campaign(tmp_path), include_failed=False)
    assert judged["factor"] is not None, judged
    factor, low, high = budget.band_factors(judged, 1200)
    assert factor == judged["factor"], (factor, judged["factor"])
    assert low <= factor <= high, (low, factor, high)


def test_the_watchdog_asks_for_successes_only():
    """Structural, because the default is the other answer.

    `measured_scaling(campaign)` includes failures, so a caller that forgets
    the argument gets the pricing answer silently.
    """
    source = (ROOT / "nobble" / "execute" / "watchdog.py").read_text()
    assert "include_failed=False" in source, (
        "the watchdog takes the pricing factor, which on this campaign is "
        "drawn from bench06's own failures")


def test_the_projection_still_asks_for_everything():
    """And the other caller must not be 'fixed' to match it.

    A projection that ignored failed time would understate a queue whose
    large jobs fail, which is F255's defect arriving by a different route.
    """
    source = (ROOT / "nobble" / "execute" / "budget.py").read_text()
    block = source[source.index("def tier2_projection"):]
    assert "include_failed=False" not in block[:3000], (
        "tier2_projection excludes failed refinements, so it underprices a "
        "queue whose large jobs fail")
