"""A truncated run has to keep the falsifiable test, not lose it.

`projected_hours` says overrunning the 48-hour target is "a scheduling fact
the priority ordering absorbs: the run yields the benchmark panel, then the
Sievers split, and loses discovery off the tail". Gate G1's reasoning rests
on that, so it is worth more than a sentence.

Two things have to hold. The tiers have to be emitted in that order, which
is easy to see. And the Sievers block has to interleave its labels, which is
not: the matched-control ROC needs degraded *and* not_degraded pairs, so a
block that ran all 24 degraded pairs first and all 96 not_degraded after
would satisfy the tier ordering and still leave a truncated run with one
side of the comparison and no curve.

They hold. The block runs at a constant four not_degraded to one degraded,
so the curve becomes computable 6.1% into the campaign and reaches its full
24 degraded pairs at 63%. The remaining 37% deepens the negative side and
runs the scramble control, which is what "discovery off the tail" means.

Ordering is a scheduling decision, and a future change made for throughput
would not obviously be touching the headline result (F65).
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute.campaign import latest  # noqa: E402
from nobble.validate import layers  # noqa: E402

# The order the spec's priority argument depends on.
TIER_ORDER = ["benchmark", "sievers_zf", "scramble"]
LABELS = ("degraded", "not_degraded")


def _queue():
    campaign = latest("campaign")
    if campaign is None or not (campaign / "queue.jsonl").exists():
        pytest.skip("no main campaign assembled")
    return [json.loads(line) for line
            in (campaign / "queue.jsonl").read_text().splitlines()
            if line.strip()]


def _completion_index(queue, per_side):
    """Job index by which `per_side` pairs are complete on both labels."""
    need = collections.Counter(job["pair_id"] for job in queue)
    label = {job["pair_id"]: job.get("peptide_label") for job in queue}
    have, complete = collections.Counter(), collections.Counter()
    for index, job in enumerate(queue, start=1):
        pair = job["pair_id"]
        have[pair] += 1
        if have[pair] == need[pair] and label[pair] in LABELS:
            complete[label[pair]] += 1
            if all(complete[name] >= per_side for name in LABELS):
                return index
    return None


def test_the_tiers_are_emitted_in_priority_order():
    queue = _queue()
    spans = {}
    for index, job in enumerate(queue):
        tier = job.get("tier")
        spans.setdefault(tier, [index, index])[1] = index
    present = [tier for tier in TIER_ORDER if tier in spans]
    assert present == [t for t in TIER_ORDER if t in spans]
    for earlier, later in zip(present, present[1:]):
        assert spans[earlier][1] < spans[later][0], (
            f"{earlier} and {later} are interleaved, so truncating the run "
            f"loses part of {earlier}: {spans}"
        )


# How far a quarter of the block may drift from the overall label share
# before the labels count as clustered rather than interleaved.
CLUSTERING_TOLERANCE = 0.15


def _clustering(block: list[dict]) -> list[str]:
    """Quarters of the block whose label mix departs from the whole.

    A pure function over a list of jobs, so the same check runs against the
    real queue and against a deliberately clustered copy of it. The first
    version of this was mutation-checked by rewriting the live campaign's
    queue.jsonl and restoring it, with the runner reading that file: it
    came back byte-identical and the campaign was unharmed, but a check
    should not be able to touch a running campaign to prove itself. This is
    the same verification with nothing on disk involved (F65).
    """
    totals = collections.Counter(job.get("peptide_label") for job in block)
    if not set(LABELS) <= set(totals):
        return [f"one side is missing entirely: {dict(totals)}"]
    quarter = len(block) // 4
    if quarter == 0:
        return []
    overall = totals["degraded"] / sum(totals[name] for name in LABELS)
    problems = []
    # By quarter rather than by job, because a pair's fifteen jobs are
    # necessarily adjacent and no per-job window could be balanced.
    for start in range(0, 4 * quarter, quarter):
        window = collections.Counter(
            job.get("peptide_label") for job in block[start:start + quarter])
        seen = sum(window[name] for name in LABELS)
        if not seen or not (window["degraded"] and window["not_degraded"]):
            problems.append(f"quarter at {start} holds one label: {dict(window)}")
            continue
        share = window["degraded"] / seen
        if abs(share - overall) >= CLUSTERING_TOLERANCE:
            problems.append(
                f"quarter at {start} is {share:.2f} degraded against "
                f"{overall:.2f} overall")
    return problems


def _sievers_block():
    block = [job for job in _queue() if job.get("tier") == "sievers_zf"]
    if not block:
        pytest.skip("no Sievers arm in this campaign")
    return block


def test_the_sievers_block_interleaves_its_labels():
    """The property the tier ordering does not give you. All the positives
    first would pass the test above and still leave a truncated run with
    no comparison to make."""
    assert _clustering(_sievers_block()) == []


def test_the_interleaving_check_rejects_a_clustered_block():
    """The negative control. Without it, a check that never fires is
    indistinguishable from a check that cannot: the real queue passing says
    nothing about whether a clustered one would be caught."""
    block = _sievers_block()
    clustered = sorted(
        block, key=lambda job: 0 if job.get("peptide_label") == "degraded" else 1)
    problems = _clustering(clustered)
    assert problems, (
        "every positive placed first and the check still passed, so it is "
        "not testing the ordering"
    )


def test_the_interleaving_check_rejects_a_one_sided_block():
    block = [job for job in _sievers_block()
             if job.get("peptide_label") == "not_degraded"]
    assert _clustering(block), "a block with no positives was accepted"


def test_the_curve_is_computable_early_in_the_campaign():
    """The number Gate G1's reasoning needs. The floor is 3 pairs a side
    and it is reached 6.1% in, so a run cut short at any point past the
    benchmark panel still yields the project's falsifiable test."""
    queue = _queue()
    index = _completion_index(queue, layers.ROC_MINIMUM_PER_SIDE)
    assert index is not None, "the campaign never reaches the ROC floor"
    assert index / len(queue) < 0.25, (
        f"the ROC floor is only reached at job {index} of {len(queue)}, "
        f"{index / len(queue) * 100:.0f}% in, so a truncated run loses the "
        "headline result"
    )


def test_the_curve_reaches_full_power_before_the_tail():
    """Computable is not the same as powered, and conflating them would
    overstate what a short run buys. All 24 degraded pairs are complete at
    63%, and the rest of the campaign deepens the negative side and runs
    the scramble control."""
    queue = _queue()
    degraded_pairs = len({job["pair_id"] for job in queue
                          if job.get("peptide_label") == "degraded"})
    if degraded_pairs < 10:
        pytest.skip("too few degraded pairs to speak of power")
    index = _completion_index(queue, 10)
    assert index is not None
    assert index / len(queue) < 0.5, (
        f"10 pairs a side is only reached {index / len(queue) * 100:.0f}% in"
    )


def test_the_floor_comes_from_the_validation_layer():
    """Not a literal here. The layer reads it from the configuration, and
    this test asserting its own copy would be the F54 divergence again."""
    from nobble import paths

    assert layers.ROC_MINIMUM_PER_SIDE == int(
        paths.thresholds()["validation"]["roc_minimum_per_side"])
