"""The paired parent-versus-scramble test (F316).

A scramble shares its parent's receptor, glue, seeds and composition and
differs only in peptide order, so the comparison is paired and isolates the
sequence. Every other test in the project is unpaired and has to carry
variation between receptors and glues that this design removes.

These check the arithmetic, which is where a sign test goes wrong: the tails,
the handling of ties, and the direction.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import scramble_paired_test as paired                      # noqa: E402


def test_the_sign_test_matches_the_exact_binomial():
    """Checked against the closed form rather than against itself."""
    for wins, trials in ((22, 31), (9, 23), (1, 9), (13, 15), (25, 26)):
        expected = min(1.0, 2 * sum(
            math.comb(trials, k) for k in range(min(wins, trials - wins) + 1))
            / 2 ** trials)
        assert paired.sign_test(wins, trials) == pytest.approx(expected)


def test_an_even_split_is_not_significant():
    assert paired.sign_test(5, 10) == pytest.approx(1.0)
    assert paired.sign_test(16, 31) > 0.5


def test_a_clean_sweep_is():
    assert paired.sign_test(31, 31) == pytest.approx(2 / 2 ** 31)


def test_nothing_to_test_is_none_rather_than_one():
    """All ties means no comparison was made, which is not a p of 1."""
    assert paired.sign_test(0, 0) is None


def test_the_p_is_symmetric_in_the_direction():
    """A sign test says how lopsided, not which way, so the direction has to
    be reported separately or a statistic that loses reads as one that
    wins."""
    assert paired.sign_test(1, 9) == paired.sign_test(8, 9)


def test_ties_leave_the_denominator_rather_than_splitting_it():
    """Splitting ties halves them into both columns and inflates the
    comparison count, which would make a statistic that cannot tell a parent
    from its scramble look tested on 29 pairs instead of 15."""
    rows = {
        "a": {"pair_id": "a", "nobble_score": 1.0},
        "scr_a": {"pair_id": "scr_a", "nobble_score": 1.0},
        "b": {"pair_id": "b", "nobble_score": 2.0},
        "scr_b": {"pair_id": "scr_b", "nobble_score": 1.0},
    }
    result = paired.compare(rows, "composite")
    assert result["tied"] == 1
    assert result["compared"] == 1
    assert result["parent_higher"] == 1


def test_a_pair_with_one_side_missing_is_counted_apart():
    """Not as a tie and not as a loss: it was not compared."""
    rows = {
        "a": {"pair_id": "a", "nobble_score": 1.0},
        "scr_a": {"pair_id": "scr_a"},
        "b": {"pair_id": "b", "nobble_score": 2.0},
        "scr_b": {"pair_id": "scr_b", "nobble_score": 1.0},
    }
    result = paired.compare(rows, "composite")
    assert result["one_side_absent"] == 1
    assert result["compared"] == 1
    assert result["tied"] == 0


def test_a_scramble_without_its_parent_is_not_paired():
    rows = {"scr_x": {"pair_id": "scr_x", "nobble_score": 1.0},
            "y": {"pair_id": "y", "nobble_score": 1.0}}
    assert paired.pairs_of(rows) == []


def test_the_family_is_stated_rather_than_left_to_the_reader():
    """Six tests at 0.05 give a 26 per cent chance of one crossing by luck,
    which is the arithmetic F280 did for seven. A table of p-values without
    it invites reading the smallest one."""
    rows = {"a": {"pair_id": "a", "nobble_score": 1.0},
            "scr_a": {"pair_id": "scr_a", "nobble_score": 0.5}}
    out = paired.report(rows)
    assert out["statistics_tested"] >= 1
    assert out["any_one_crossing_by_chance"] == pytest.approx(
        1 - 0.95 ** out["statistics_tested"], abs=1e-3)
    assert out["bonferroni_threshold"] == pytest.approx(
        0.05 / out["statistics_tested"], abs=1e-5)


def test_the_live_campaign_is_paired_on_every_scramble():
    """The design's premise: a scramble with no parent cannot be paired, and
    a campaign where some are unpaired would be reporting a mix."""
    from nobble import paths
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")
    rows = {row["pair_id"]: row for row
            in paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
            if row.get("pair_id")}
    scrambles = [name for name in rows if name.startswith("scr_")]
    if not scrambles:
        pytest.skip("no scrambles scored")
    orphans = [name for name in scrambles
               if name[len("scr_"):] not in rows]
    assert not orphans, (
        f"{len(orphans)} scramble(s) have no scored parent, so they can only "
        f"enter an unpaired test: {orphans[:3]}")
