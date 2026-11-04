"""The matched-control ROC is the Sievers split and nothing else (spec 5.3).

The benchmark panel also carries the label "degraded". On label alone its
seven pairs join the positive side of this curve, and they are a different
experiment: other E3 ligases, PROTACs as well as glues, and no matched
negative from the same screen. They are also the panel chosen for having
good co-crystals, so they would raise the positive side and the AUC with
it.

That failure is silent and flattering, which is the worst combination: the
curve still draws, the number still looks plausible, and it moves in the
direction that makes the result look better.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.validate.layers import matched_control_roc


def _row(tier: str, label: str, delta: float, pair_id: str) -> dict:
    return {"pair_id": pair_id, "tier": tier, "peptide_label": label,
            "delta_iptm": delta}


def _campaign(tmp_path, rows) -> Path:
    (tmp_path / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    return tmp_path


def test_benchmark_pairs_do_not_enter_the_positive_side(tmp_path):
    """The contamination case, built to flatter the curve.

    Four Sievers positives sit below their negatives, so the arm alone is
    worse than chance. Three benchmark pairs with high Delta-ipTM would drag
    the AUC up if they counted.
    """
    rows = [_row("sievers_zf", "degraded", 0.01, f"sv_pos{i}") for i in range(4)]
    rows += [_row("sievers_zf", "not_degraded", 0.50, f"sv_neg{i}") for i in range(4)]
    rows += [_row("benchmark", "degraded", 0.99, f"bench{i}") for i in range(3)]

    layer = matched_control_roc(_campaign(tmp_path, rows))

    assert layer.summary["positives"] == 4, "a benchmark pair reached the ROC"
    assert layer.summary["matched_negatives"] == 4
    assert layer.summary["pairs_outside_the_arm_excluded"] == 3
    # The arm is genuinely worse than chance here; the curve must say so.
    assert layer.summary["auc"] < 0.5


def test_scrambles_are_not_counted_as_matched_negatives(tmp_path):
    """A scramble is a different kind of negative: it never went through the
    screen, so it is not a matched control for this curve."""
    rows = [_row("sievers_zf", "degraded", 0.8, f"sv_pos{i}") for i in range(3)]
    rows += [_row("sievers_zf", "not_degraded", 0.2, f"sv_neg{i}") for i in range(3)]
    rows += [_row("scramble", "negative_control", 0.1, f"scr{i}") for i in range(5)]

    layer = matched_control_roc(_campaign(tmp_path, rows))
    assert layer.summary["matched_negatives"] == 3


def test_it_still_refuses_when_the_arm_has_not_run(tmp_path):
    """Spec 5 is explicit that reporting a curve without the matched
    negatives is itself the failure."""
    rows = [_row("benchmark", "degraded", 0.9, f"bench{i}") for i in range(7)]

    layer = matched_control_roc(_campaign(tmp_path, rows))
    assert layer.status.startswith("not_computed")
    assert "auc" not in layer.summary
