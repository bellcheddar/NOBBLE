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


def _arm(tmp_path, edge: float, seed: int = 7) -> Path:
    """A Sievers-shaped arm: 24 degraded against 96 matched controls, plus
    the benchmark and scramble pairs the curve must exclude."""
    import random

    random.seed(seed)
    rows = []
    for index in range(24):
        rows.append(_row("sievers_zf", "degraded",
                         round(random.gauss(0.05 + edge, 0.17), 4), f"sv_pos{index}"))
    for index in range(96):
        rows.append(_row("sievers_zf", "not_degraded",
                         round(random.gauss(0.05, 0.17), 4), f"sv_neg{index}"))
    for index in range(7):
        rows.append(_row("benchmark", "degraded", 0.9, f"bench{index}"))
    for index in range(31):
        rows.append(_row("scramble", "negative_control", 0.0, f"scr{index}"))
    return _campaign(tmp_path, rows)


def test_the_curve_computes_at_the_real_arm_size(tmp_path):
    """The headline measurement has never computed: every campaign so far
    has had no matched negatives. Its branches first run for real after the
    main campaign, so they are exercised here at the size they will be."""
    layer = matched_control_roc(_arm(tmp_path, edge=0.22, seed=33))
    summary = layer.summary

    assert layer.status == "computed"
    assert summary["positives"] == 24
    assert summary["matched_negatives"] == 96
    assert summary["pairs_outside_the_arm_excluded"] == 38
    low, high = summary["ci95"]
    assert low <= summary["auc"] <= high


def test_no_signal_is_reported_as_no_signal(tmp_path):
    summary = matched_control_roc(_arm(tmp_path, edge=0.0)).summary
    assert "not distinguishable from chance" in summary["interpretation"]


def test_an_auc_that_looks_like_a_signal_is_refused_when_the_interval_straddles_chance(tmp_path):
    """The case worth protecting. A weak edge puts the AUC visibly above
    0.5, which reads as a result, while the 95 per cent interval still runs
    below it. Spec 5 is explicit that reporting a curve which cannot carry
    its claim is itself the failure, so the interpretation must decline
    rather than round the point estimate up into a finding.

    Asserted on the property rather than a remembered number: the exact
    AUC depends on the draw, and pinning 0.63 here would be tuning the
    fixture until it agreed with me."""
    summary = matched_control_roc(_arm(tmp_path, edge=0.07)).summary

    assert summary["auc"] > 0.55, summary["auc"]
    assert summary["ci95"][0] < 0.5 < summary["ci95"][1], summary["ci95"]
    assert "not distinguishable from chance" in summary["interpretation"]


def test_a_real_separation_is_reported_as_above_chance(tmp_path):
    """The other side: the layer must not be so cautious that it refuses a
    separation it can actually support."""
    summary = matched_control_roc(_arm(tmp_path, edge=0.12)).summary

    assert summary["ci95"][0] > 0.5, summary["ci95"]
    assert summary["interpretation"] == "above chance"
