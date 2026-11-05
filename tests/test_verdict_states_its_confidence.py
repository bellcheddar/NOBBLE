"""Every verdict carries its confidence level, including the good one (F198).

`_verdict` turns a bootstrap interval into one of three sentences. Two of
them said "at N per cent confidence" and the third, the one for a separation
above chance, said "above chance" and nothing else.

The interval is the same object in all three cases, so the asymmetry was not
about evidence. It read as a positive result stated more plainly than a
negative one: the headline claim of the project without its qualifier, and
both unfavourable outcomes with theirs. For a file that elsewhere refuses to
draw a curve without matched negatives and insists that below chance "is a
result rather than an absence of one", that was out of character.

These tests hold the property rather than the three strings, because the
wording will change and the property should not.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate.layers import _verdict, confidence_level  # noqa: E402

# Intervals that land in each of the three branches, by construction:
# wholly above 0.5, wholly below, and straddling it.
INTERVALS = ((0.62, 0.91), (0.55, 0.60), (0.12, 0.38), (0.30, 0.49),
             (0.41, 0.73), (0.49, 0.51))


def test_every_verdict_states_the_confidence_level():
    level = f"{confidence_level():g} per cent confidence"
    bare = [f"{low}-{high}" for low, high in INTERVALS
            if level not in _verdict(low, high)]
    assert not bare, (
        f"verdict(s) for {bare} state no confidence level, so one outcome is "
        "reported more plainly than another from the same interval"
    )


def test_the_three_branches_are_all_reachable():
    """Otherwise the test above could pass by never seeing a branch."""
    verdicts = {_verdict(low, high).split(" at ")[0] for low, high in INTERVALS}
    assert verdicts == {"above chance", "below chance",
                        "not distinguishable from chance"}, sorted(verdicts)


def test_an_interval_straddling_half_is_never_called_above_chance():
    """The caution that matters: 0.5 inside the interval is not a separation."""
    for low, high in ((0.49, 0.51), (0.41, 0.73), (0.5, 0.9), (0.2, 0.8)):
        verdict = _verdict(low, high)
        assert not verdict.startswith("above chance"), (
            f"[{low}, {high}] contains or touches 0.5 and was called "
            f"{verdict!r}"
        )


def test_below_chance_still_says_it_is_a_result():
    """F198 must not have flattened the three cases into one sentence."""
    verdict = _verdict(0.12, 0.38)
    assert "opposite direction" in verdict
    assert "rather than an absence of one" in verdict
