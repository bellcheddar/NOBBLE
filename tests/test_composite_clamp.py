"""An unmeasurable component ranked as the best possible one.

Spec 4.8's composite puts every component on 0 to 1 so a weight means the
same thing across them, with `max(0.0, min(1.0, value))`.

`min(1.0, nan)` returns 1.0, because `nan < 1.0` is false and `min` keeps
what it has. So a NaN component did not propagate and did not raise: the
clamp converted it into the maximum possible score. A pair whose bridge
percentile could not be measured would have ranked as having the best bridge
in the panel, and `percentile_of` returns NaN whenever the reference
distribution is empty, which is what a host without BINMAN's atlas looks
like. `+inf` did the same; `-inf` became 0.0.

The second half of the finding is that `weights.py` carried its own copy of
the Mann-Whitney estimator, identical in its tie handling and never hardened
when F74 hardened the one in `layers.py`. That copy is what the grid search
maximises to choose the weights (F77).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.numeric import mann_whitney_auc  # noqa: E402
from nobble.score import weights  # noqa: E402

NAN = float("nan")
INF = float("inf")


def test_the_clamp_used_to_promote_a_nan_and_now_does_not():
    """The defect, and the arithmetic behind it."""
    assert min(1.0, NAN) == 1.0, "the behaviour this finding rests on"
    assert max(0.0, min(1.0, NAN)) == 1.0, "what the old clamp returned"
    assert weights._normalise("bridge_percentile", NAN) is None


def test_every_non_finite_component_is_absent_rather_than_extreme():
    for name in ("bridge_percentile", "delta_iptm", "convergence_score",
                 "plip_fingerprint_match"):
        for value in (NAN, INF, -INF):
            assert weights._normalise(name, value) is None, (name, value)


def test_a_measurable_component_is_unchanged():
    """The fix must not move a real figure. These are the three scalings the
    normaliser applies."""
    assert weights._normalise("bridge_percentile", 70.0) == 0.7
    assert weights._normalise("delta_iptm", 0.0) == 0.5
    assert weights._normalise("delta_iptm", 1.0) == 1.0
    assert weights._normalise("convergence_score", 0.4) == 0.4
    assert weights._normalise("bridge_percentile", None) is None


def test_the_clamp_still_clamps_a_real_outlier():
    """Out of range is not the same as unmeasurable: a bridge percentile of
    120 is a bug upstream, and clamping it is the right answer."""
    assert weights._normalise("bridge_percentile", 120.0) == 1.0
    assert weights._normalise("delta_iptm", -5.0) == 0.0


def test_an_absent_component_renormalises_rather_than_scoring_zero():
    """Why None is the right value to return. The composite is a weighted
    mean over the components that were measurable, so dropping one must not
    drag the score towards zero."""
    row = {"bridge_percentile": 80.0, "delta_iptm": NAN,
           "convergence_score": 0.6}
    weighting = {"bridge_percentile": 1.0, "delta_iptm": 1.0,
                 "convergence_score": 1.0}
    score = weights.apply(row, weighting)
    # (0.8 + 0.6) / 2, not (0.8 + 0 + 0.6) / 3 and not (0.8 + 1 + 0.6) / 3.
    assert score == 0.7


def test_the_composite_no_longer_rewards_an_unmeasurable_bridge():
    """The failure in the shape it would have taken: two pairs alike except
    that one's bridge could not be measured."""
    weighting = {"bridge_percentile": 1.0, "convergence_score": 1.0}
    measured = {"bridge_percentile": 50.0, "convergence_score": 0.5}
    unmeasurable = {"bridge_percentile": NAN, "convergence_score": 0.5}
    assert weights.apply(measured, weighting) == 0.5
    assert weights.apply(unmeasurable, weighting) == 0.5, (
        "the unmeasurable pair should score on what it has, not on a 1.0"
    )
    # Under the old clamp it would have been (1.0 + 0.5) / 2 = 0.75.


def test_one_estimator_serves_both_callers():
    """The duplication. Both now call the same function, and each keeps the
    empty-side contract its caller needs."""
    from nobble.validate import layers

    # `assert layers._auc(...) != layers._auc(...) or True` stood here and
    # could not fail: `or True` makes any test unconditional, and the NaN
    # inequality it was reaching for is asserted properly on the next line
    # anyway. Removed rather than repaired, because the property it meant to
    # check was already covered (F245).
    assert math.isnan(layers._auc([], [1.0])), "the layer reports absence as NaN"
    assert weights._auc([], [1.0]) is None, "the fitter declines that grid point"
    assert layers._auc([0.3], [0.1]) == mann_whitney_auc([0.3], [0.1]) == 1.0
    assert weights._auc([0.3], [0.1]) == 1.0


def test_both_callers_refuse_a_non_finite_value():
    """The property F74 gave one of them and not the other."""
    import pytest

    from nobble.validate import layers

    for auc in (layers._auc, weights._auc, mann_whitney_auc):
        with pytest.raises(ValueError, match="non-finite"):
            auc([0.3, NAN], [0.1, 0.2])


def test_the_shared_estimator_still_scores_ties_at_a_half():
    assert mann_whitney_auc([0.0], [0.0]) == 0.5
    assert mann_whitney_auc([0.2, 0.0], [0.0, 0.1]) == 0.625


def test_no_module_carries_its_own_auc():
    """The sweep. A third copy would be the next one nobody hardens."""
    import ast

    offenders = []
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        if path.name == "numeric.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.unparse(node)
            if "wins" in body and "0.5" in body and "len(" in body:
                offenders.append(f"{path.relative_to(ROOT)}::{node.name}")
    assert not offenders, (
        f"module(s) computing their own Mann-Whitney statistic: {offenders}"
    )
