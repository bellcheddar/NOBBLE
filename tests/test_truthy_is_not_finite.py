"""A NaN is truthy, so `if row.get("seconds")` admits one.

F74 found that `isinstance(value, (int, float))` admits a NaN, and F76 moved
the rule into `nobble/numeric.py` and swept the fourteen copies of that
idiom. The sweep looks for the type check. It does not look for a truthy
guard standing in for the same question, and two modules used one on measured
durations.

`write_throughput` filtered `if item.get("seconds") and item.get("tokens")`
and then took `rates[len(rates) // 2]` from a sorted list. One NaN rate
leaves `sorted()` with the whole list unsorted, so that index returns the NaN
or an arbitrary neighbour, and that median sizes the campaign and decides
Gate G1. The watchdog's comparable-job filter did the same thing and takes
its typical rate by the same index.

Neither is reachable from the runner, because `seconds` is a difference of
two `time.monotonic()` readings and `tokens` is an integer from the queue.
Both are now `finite`, which is what the project's own rule says, and which
is what the `tier1_worst_seconds` added for F100 already did ten lines away:
two rules for one question in adjacent code is what F76 was about (F130).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.execute import watchdog  # noqa: E402
from nobble.execute.runner import write_throughput  # noqa: E402
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

GOOD = {"job_id": "a", "pair_id": "p", "tier": "benchmark",
        "status": "done", "seconds": 100.0, "tokens": 200}


def test_a_nan_is_truthy_which_is_the_whole_problem():
    """The premise, stated so the guards below have something to be about."""
    assert bool(float("nan")) is True
    unsorted = sorted([0.1, float("nan"), 0.9])
    # Not sorted, and the middle element is not the median of anything.
    assert math.isnan(unsorted[1]), unsorted


def _campaign(tmp_path: Path, rows: list[dict]) -> Path:
    campaign = tmp_path / "campaign_nan"
    campaign.mkdir(exist_ok=True)
    (campaign / "results.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n")
    return campaign


def test_the_throughput_filter_drops_a_non_finite_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _campaign(tmp_path, [
        GOOD,
        {**GOOD, "job_id": "b", "seconds": float("nan")},
        {**GOOD, "job_id": "c", "tokens": float("nan")},
    ])
    payload = write_throughput(campaign)
    assert payload["jobs_timed"] == 1, payload
    assert payload["median_seconds_per_token"] == pytest.approx(0.5)


def test_the_throughput_filter_still_drops_a_zero(tmp_path, monkeypatch):
    """The truthy form rejected zero too, and that is worth keeping: a job
    recorded at zero seconds or zero tokens is not a measurement either."""
    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _campaign(tmp_path, [
        GOOD,
        {**GOOD, "job_id": "b", "seconds": 0.0},
        {**GOOD, "job_id": "c", "tokens": 0},
    ])
    assert write_throughput(campaign)["jobs_timed"] == 1


def test_the_median_is_the_middle_of_the_finite_rates(tmp_path, monkeypatch):
    """Three finite rates and a NaN: the median must be the middle of the
    three, which it cannot be if the NaN is in the sort."""
    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _campaign(tmp_path, [
        {**GOOD, "job_id": "a", "seconds": 100.0, "tokens": 1000},   # 0.1
        {**GOOD, "job_id": "b", "seconds": 500.0, "tokens": 1000},   # 0.5
        {**GOOD, "job_id": "c", "seconds": 900.0, "tokens": 1000},   # 0.9
        {**GOOD, "job_id": "d", "seconds": float("nan"), "tokens": 1000},
    ])
    payload = write_throughput(campaign)
    assert payload["jobs_timed"] == 3
    assert payload["median_seconds_per_token"] == pytest.approx(0.5)


def test_the_watchdog_uses_the_same_rule():
    source = (ROOT / "nobble" / "execute" / "watchdog.py").read_text()
    assert "from nobble.numeric import finite" in source
    assert 'row.get("seconds") and row.get("tokens")' not in source, (
        "the watchdog is back to a truthy guard on a measured duration"
    )


def test_the_runner_uses_the_same_rule():
    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert 'item.get("seconds") and item.get("tokens")' not in source
    assert "finite(item.get(\"seconds\"))" in source


def test_the_live_measurement_is_unchanged(tmp_path, monkeypatch):
    """Behaviour-preserving on finite data, which is the whole of the real
    data: 100 benchmark jobs at the median the README quotes.

    `paths.THROUGHPUT` is redirected, and that is not tidiness.
    `write_throughput` writes it, `data.throughput()` reads it, and the app
    shows it, so the first version of this test replaced the running
    campaign's measurement with the benchmark's every time the suite ran.
    `tools/mutate.py` lists `data/throughput.json` among the files it watches
    for exactly this and said so on the next mutation run.
    """
    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _newest("benchmark")
    if not (campaign / "results.jsonl").exists():
        pytest.skip("no benchmark campaign")
    payload = write_throughput(campaign)
    assert payload["jobs_timed"] == 100, payload["jobs_timed"]
    assert payload["median_seconds_per_token"] == pytest.approx(0.4551, abs=1e-4)


def test_the_numeric_sweep_covers_the_type_check_and_not_this():
    """Recorded rather than detected. A general "truthiness standing in for
    finiteness" sweep cannot distinguish `if rows:` from
    `if row.get("seconds"):` without knowing which fields are numeric, and
    F95 established that a sweep whose false positives outnumber its findings
    fifteen to two is not kept. These two instances are fixed and tested by
    name instead."""
    sweep = (ROOT / "tests" / "test_numeric_rule.py").read_text()
    assert "isinstance" in sweep
    assert "truthy" not in sweep.lower(), (
        "if the sweep now covers truthiness, this note is stale and the two "
        "named tests above can go"
    )


def test_no_test_leaves_the_live_throughput_rewritten():
    """The suite must not change state the app reads.

    `write_throughput` writes `paths.THROUGHPUT`, `data.throughput()` reads
    it and the Campaign page shows it. Two tests added today called it
    without redirecting the path: one replaced the running campaign's
    measurement with the benchmark's, which is the wrong campaign, and one
    remeasured the same campaign, which is merely a side effect.

    `tools/mutate.py` lists `data/throughput.json` among the files it
    fingerprints before and after a mutation, and said so on the next run.
    This asserts the property directly rather than relying on noticing it
    there (F131).
    """
    import re

    # This file is skipped, because it holds the pattern as a regex literal
    # and counting it finds itself: five calls against four redirects, the
    # fifth being the string on the next line. `test_house_style.py` has the
    # same idiom for the same reason, as `THIS_FILE`.
    this_file = Path(__file__).name
    checked = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if path.name == this_file:
            continue
        text = path.read_text()
        if "write_throughput(" not in text:
            continue
        calls = len(re.findall(r"write_throughput\(", text))
        # Both forms of redirect this suite uses.
        redirects = len(re.findall(r'setattr\(\s*paths[a-z_]*\s*,\s*"THROUGHPUT"',
                                   text))
        # Every call redirected, not all but one. The first version of this
        # allowed `redirects + 1`, which permits exactly the defect it is
        # here to catch.
        assert calls <= redirects, (
            f"{path.name}: {calls} write_throughput call(s) against "
            f"{redirects} redirect(s), so at least one writes the live file"
        )
        checked += 1
    assert checked >= 2, checked
