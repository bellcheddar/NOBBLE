"""The prediction scorer must be able to say "wrong".

F13 recorded what F6 predicts for CDK12 and RBM39 before either ran, with
explicit falsifiers. Reading the numbers afterwards and deciding is the
step where a prediction quietly turns into a description: the threshold
drifts a little, the wording softens, and nothing was ever at stake.

So the thresholds are transcribed into tools/check_prediction.py and the
verdict is whatever they produce. These tests check it produces all three
outcomes, including the one that costs something.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "check_prediction", ROOT / "tools" / "check_prediction.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def test_cdk12_is_wrong_if_it_stays_badly_placed():
    """F13's falsifier verbatim: above about 20 A means the fragment was
    not the limitation there."""
    spec = check.PREDICTIONS["CDK12"]
    assert spec["falsified"](44.92, 31.0) is True
    assert spec["falsified"](44.92, 1.5) is False
    assert spec["passes_if"](44.92, 1.5) is True


def test_cdk12_improving_only_slightly_is_not_a_pass():
    """Dropping from 44.92 to 21 is a large change and still a failure:
    the prediction was that the pose becomes right, not that it moves."""
    spec = check.PREDICTIONS["CDK12"]
    assert spec["passes_if"](44.92, 21.0) is False
    assert spec["falsified"](44.92, 21.0) is True


def test_rbm39_is_wrong_because_it_moved_a_long_way():
    """The prediction said little change. It moved 5.35 A, and the scorer
    has to call that rather than soften it."""
    spec = check.PREDICTIONS["RBM39"]
    assert spec["falsified"](6.085, 0.731) is True
    assert spec["passes_if"](6.085, 0.731) is False
    # The prediction would have held had it genuinely changed little.
    assert spec["passes_if"](6.085, 5.5) is True


def test_the_scorer_reports_wrong_against_the_real_campaigns():
    import glob

    import pytest

    baselines = sorted(glob.glob("campaigns/benchmark_*"))
    correcteds = sorted(glob.glob("campaigns/corrected_*"))
    if not baselines or not correcteds:
        pytest.skip("campaigns not present")

    result = check.evaluate(Path(baselines[-1]), Path(correcteds[-1]))
    rbm39 = next(r for r in result["predictions"] if r["gene"] == "RBM39")
    if rbm39["verdict"] == "not yet testable":
        pytest.skip("RBM39 has not finished in both campaigns")

    assert rbm39["verdict"] == "WRONG", rbm39
    assert result["wrong"] >= 1, "a scorer that never returns wrong is not scoring"


def test_an_unfinished_pair_is_not_scored_either_way():
    """Silence until the data exists, rather than a provisional verdict
    that gets quoted."""
    spec = check.PREDICTIONS["CDK12"]
    assert callable(spec["falsified"])
    assert "falsified_if" in spec and spec["falsified_if"]
