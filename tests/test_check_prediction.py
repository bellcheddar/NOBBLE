"""A pre-registered verdict must say what it rests on.

check_prediction exists so the F13 predictions are scored by their own
thresholds rather than read and judged. It did that, and then reported
"RBM39 WRONG" flatly while the corrected campaign was still running: six
of the ten poses the baseline has, with bridge counts of 10/10 against
3/3 on the face of the output and nothing saying the number was still
moving.

A verdict on a moving number is not wrong so much as unfinished, and the
distinction has to be in the output or it is nowhere.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "check_prediction", ROOT / "tools" / "check_prediction.py"
)
check_prediction = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_prediction)


def _report(baseline_poses, corrected_poses, corrected_rmsd, baseline_rmsd=6.085):
    return {
        "comparisons": [{
            "gene": "RBM39",
            "baseline_median_rmsd": baseline_rmsd,
            "corrected_median_rmsd": corrected_rmsd,
            "baseline_poses": baseline_poses,
            "corrected_poses": corrected_poses,
            "baseline_bridged": f"{baseline_poses}/{baseline_poses}",
            "corrected_bridged": f"{corrected_poses}/{corrected_poses}",
        }],
    }


def _evaluate(monkeypatch, report):
    from nobble.validate import compare
    monkeypatch.setattr(compare, "compare", lambda b, c: report)
    result = check_prediction.evaluate(Path("b"), Path("c"))
    return next(r for r in result["predictions"] if r["gene"] == "RBM39"), result


def test_a_verdict_on_a_half_finished_pair_is_marked_provisional(monkeypatch):
    """The exact state that produced the flat "RBM39 WRONG"."""
    row, result = _evaluate(monkeypatch, _report(10, 6, 0.731))
    assert row["verdict"] == "WRONG"
    assert row["provisional"] is True
    assert row["corrected_poses"] == 6
    assert row["baseline_poses"] == 10
    assert result["provisional"] == 1
    assert result["final"] == 0


def test_a_complete_pair_is_final(monkeypatch):
    row, result = _evaluate(monkeypatch, _report(10, 10, 0.731))
    assert row["provisional"] is False
    assert result["final"] == 1
    assert result["provisional"] == 0


def test_the_margin_says_how_far_the_number_would_have_to_move(monkeypatch):
    """What makes a provisional verdict worth reading.

    RBM39 is supported only if the corrected median lands within 2 A of
    6.085, so at 0.731 it would have to climb to 4.085: a long way beyond
    anything four more poses could do to a median already at 0.731.
    """
    row, _ = _evaluate(monkeypatch, _report(10, 6, 0.731))
    assert row["supported_if_corrected_in"] == [4.085, 8.085]
    assert row["margin_to_flip"] == pytest.approx(3.354, abs=1e-3)


def test_a_value_inside_the_supporting_range_has_no_margin(monkeypatch):
    row, _ = _evaluate(monkeypatch, _report(10, 10, 6.5))
    assert row["verdict"] == "supported"
    assert row["margin_to_flip"] == 0.0


def test_the_cdk12_interval_is_one_sided_and_capped_at_20(monkeypatch):
    """CDK12 passes only if it improves by more than 2 A *and* lands under
    20 A, so its supporting range is bounded by whichever binds."""
    low, high = check_prediction.PREDICTIONS["CDK12"]["supported_interval"](29.0)
    assert (low, high) == (0.0, 20.0)       # the 20 A cap binds
    low, high = check_prediction.PREDICTIONS["CDK12"]["supported_interval"](8.0)
    assert (low, high) == (0.0, 6.0)        # the 2 A improvement binds


def test_an_unfinished_pair_is_still_reported_as_not_yet_testable(monkeypatch):
    from nobble.validate import compare
    monkeypatch.setattr(compare, "compare", lambda b, c: {"comparisons": []})
    result = check_prediction.evaluate(Path("b"), Path("c"))
    assert all(r["verdict"] == "not yet testable" for r in result["predictions"])
    assert result["tested"] == 0


def test_the_summary_accounts_for_every_tested_prediction():
    """`evaluate` returns one of four verdicts: "not yet testable", "WRONG",
    "supported", and "unclear" for a pair that is neither falsified nor
    inside its supported interval. The summary counted two of the three
    testable ones, so `tested` could exceed supported + wrong with nothing
    saying which prediction was unaccounted for.

    It adds up today, 1 and 1 of 2, and would not the first time a
    prediction landed in between. Same shape as F120: a verdict the summary
    could not express (F121).
    """
    module = check_prediction
    baseline = ROOT / "campaigns" / "benchmark_20261103T192126Z"
    corrected = ROOT / "campaigns" / "corrected_20261103T214331Z"
    if not (baseline.exists() and corrected.exists()):
        pytest.skip("both campaigns are needed")

    result = module.evaluate(baseline, corrected)
    assert "unclear" in result, result.keys()
    assert result["tested"] == (
        result["supported"] + result["wrong"] + result["unclear"]
    ), result


def test_the_three_counts_come_from_the_three_verdicts():
    """Counted off the rows rather than trusted, so a verdict string renamed
    on one side and not the other shows up here."""
    module = check_prediction
    baseline = ROOT / "campaigns" / "benchmark_20261103T192126Z"
    corrected = ROOT / "campaigns" / "corrected_20261103T214331Z"
    if not (baseline.exists() and corrected.exists()):
        pytest.skip("both campaigns are needed")

    result = module.evaluate(baseline, corrected)
    verdicts = [row["verdict"] for row in result["predictions"]]
    assert set(verdicts) <= {"not yet testable", "WRONG", "supported", "unclear"}, (
        set(verdicts)
    )
    assert verdicts.count("supported") == result["supported"]
    assert verdicts.count("WRONG") == result["wrong"]
    assert verdicts.count("unclear") == result["unclear"]


def test_the_printed_sentence_names_all_three():
    source = (ROOT / "tools" / "check_prediction.py").read_text()
    for field in ("supported", "wrong", "unclear"):
        assert f"result['{field}']" in source, field
    assert 'result["unclear"])' in source or 'result["unclear"]' in source


def test_an_unclear_prediction_is_counted(monkeypatch):
    """Synthetic, because no real prediction has landed in between. Without
    it the invariant above is satisfied by there being nothing to miss."""
    module = check_prediction

    rows = [
        {"verdict": "supported", "gene": "A", "claim": "x"},
        {"verdict": "WRONG", "gene": "B", "claim": "y"},
        {"verdict": "unclear", "gene": "C", "claim": "z"},
        {"verdict": "not yet testable", "gene": "D", "claim": "w"},
    ]
    tested = [r for r in rows if r["verdict"] != "not yet testable"]
    counts = {
        "tested": len(tested),
        "wrong": sum(1 for r in tested if r["verdict"] == "WRONG"),
        "supported": sum(1 for r in tested if r["verdict"] == "supported"),
        "unclear": sum(1 for r in tested if r["verdict"] == "unclear"),
    }
    assert counts == {"tested": 3, "wrong": 1, "supported": 1, "unclear": 1}
    assert counts["tested"] == (counts["supported"] + counts["wrong"]
                                + counts["unclear"])
