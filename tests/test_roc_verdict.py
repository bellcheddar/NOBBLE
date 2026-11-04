"""An inverted result is a result, and the verdict could not say so.

The matched-control ROC reported one of two things: "above chance" when the
bootstrap's lower bound cleared 0.5, and otherwise "not distinguishable from
chance". There are three outcomes. An interval entirely below 0.5 means the
statistic separates the two classes in the opposite direction to the
prediction, and calling that indistinguishable from chance is false: it is
distinguishable, and inverted.

For Delta-ipTM it would mean the matched negatives gaining more interface
confidence from the glue than the degraded fingers do. Spec 4.3 asks for that
case by name: "If it does not [hold], that is a real result about co-folding
models and ternary cooperativity, and the app should report it as such rather
than hiding it." Spec 5 adds that a poor ROC is not a gate failure while
failing to report one is.

The project already knows how to say it. D-NOB-024 reports BINMAN's lysine
reach window as "at or below chance and slightly inverted" on the strength of
an AUC of 0.42 to 0.48. The headline curve had no way to reach the same
conclusion about itself (F120).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import layers  # noqa: E402


def test_an_interval_above_a_half_is_above_chance():
    assert layers._verdict(0.68, 0.92) == "above chance"
    assert layers._verdict(0.51, 0.99) == "above chance"


def test_an_interval_below_a_half_says_so_and_says_what_it_means():
    verdict = layers._verdict(0.08, 0.24)
    assert verdict.startswith("below chance"), verdict
    assert "opposite direction" in verdict
    assert "a result rather than an absence of one" in verdict
    assert "not distinguishable" not in verdict


def test_an_interval_spanning_a_half_is_not_distinguishable():
    assert "not distinguishable" in layers._verdict(0.42, 0.61)
    assert "not distinguishable" in layers._verdict(0.49, 0.51)


def test_the_boundaries_go_to_the_cautious_branch():
    """Strict inequalities on both sides, so an interval touching 0.5 claims
    nothing. `low == 0.5` is not above chance and `high == 0.5` is not below
    it."""
    assert "not distinguishable" in layers._verdict(0.5, 0.9)
    assert "not distinguishable" in layers._verdict(0.1, 0.5)
    assert "not distinguishable" in layers._verdict(0.5, 0.5)


def test_every_branch_carries_the_configured_level():
    """Except "above chance", which states no level because it is a claim
    about the interval rather than about a test at one."""
    assert f"{layers.confidence_level():g} per cent" in layers._verdict(0.1, 0.2)
    assert f"{layers.confidence_level():g} per cent" in layers._verdict(0.4, 0.6)


def test_the_three_cases_are_exhaustive_and_distinct():
    """The property the two-branch version lacked: every interval gets
    exactly one of three answers, and no two intervals from different cases
    get the same one."""
    cases = {
        "above": [(0.55, 0.9), (0.501, 1.0)],
        "below": [(0.0, 0.49), (0.1, 0.4999)],
        "unclear": [(0.4, 0.6), (0.5, 0.5), (0.2, 0.8)],
    }
    seen = {}
    for name, intervals in cases.items():
        for low, high in intervals:
            verdict = layers._verdict(low, high)
            seen.setdefault(name, set()).add(verdict)
    assert len(seen) == 3
    assert len(seen["above"]) == 1 and len(seen["unclear"]) == 1
    # The three answers share no text that would let one be read as another.
    heads = {name: sorted(values)[0].split(":")[0] for name, values in seen.items()}
    assert len(set(heads.values())) == 3, heads


def test_the_verdict_is_a_function_rather_than_an_inline_conditional():
    """`low > 0.5` else "not distinguishable" reads as exhaustive and is not,
    which is how the third case went missing. A named function with three
    returns does not read that way."""
    source = (ROOT / "nobble" / "validate" / "layers.py").read_text()
    assert "def _verdict(" in source
    assert '"above chance" if low > 0.5' not in source


def test_the_layer_uses_it():
    source = (ROOT / "nobble" / "validate" / "layers.py").read_text()
    assert '"interpretation": _verdict(low, high)' in source


def test_the_live_layer_still_reports_something_sensible():
    """End to end, on whichever campaigns exist. The curve is not computed
    yet, so this checks the layer does not raise and says why."""
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None:
        pytest.skip("no campaign on this checkout")
    result = layers.matched_control_roc(campaign)
    assert result.status, result
    if result.status == "computed":
        assert result.summary["interpretation"]
    else:
        assert "not_computed" in result.status
