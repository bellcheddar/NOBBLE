"""A weakened bridge must not read as a clean improvement.

F19 recorded that a healthy-looking lift can hide a broken ternary: the
substitution pushed the peptide away, the model stayed confident about
whatever contact remained, and the lift came out positive. The fix then
flagged outright loss, where the parent bridged in some seed and the
variant bridged in none.

It left the case in between. A parent at 10/10 against a variant at 1/10
is not an outright loss and is barely different from one, and it carried
no flag at all: `bridge_lost` was False, so the scan chart (which outlines
only lost bridges) drew it as an ordinary point, and with a positive lift
it would be picked as `least_sensitive`, the arm's headline "this position
tolerates substitution".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.design import lift as lift_module  # noqa: E402

BASE = dict(construct="CRBN_CULT", e3_gene="CRBN", ligand_key="Y70",
            modality="glue", seeds_binary=5, seeds_ternary=10,
            bridging_seeds_total=10)


def _pair(variant_bridged: int, variant_delta: float = 0.30,
          parent_bridged: int = 10, parent_delta: float = 0.20,
          position: int = 7, substitution: str = "K7A"):
    parent = dict(BASE, peptide_id="p", delta_iptm=parent_delta,
                  bridging_seeds_with_bridge=parent_bridged)
    variant = dict(BASE, pair_id="v", substitution=substitution,
                   position=position, delta_iptm=variant_delta,
                   bridging_seeds_with_bridge=variant_bridged)
    return lift_module.compute(variant, parent)


def test_a_bridge_kept_intact_is_not_flagged():
    result = _pair(10)
    assert result.status == "computed"
    assert result.bridge_rate_change == 0.0
    assert result.bridge_weakened is False
    assert result.bridge_lost is False


def test_a_bridge_kept_in_one_seed_of_ten_is_weakened():
    """The case that previously carried no flag, with a positive lift."""
    result = _pair(1)
    assert result.lift and result.lift > 0, "the lift still looks like a gain"
    assert result.bridge_lost is False, "not an outright loss"
    assert result.bridge_weakened is True
    assert result.bridge_rate_change == -0.9


def test_exactly_half_retained_is_not_weakened():
    """The threshold's own meaning: the variant must keep under half."""
    assert _pair(5).bridge_weakened is False
    assert _pair(4).bridge_weakened is True


def test_an_outright_loss_is_both_lost_and_weakened():
    result = _pair(0)
    assert result.bridge_lost is True
    assert result.bridge_weakened is True


def test_a_parent_that_never_bridged_cannot_have_a_weakened_bridge():
    """Otherwise every variant of a failed parent falls under suspicion."""
    result = _pair(0, parent_bridged=0)
    assert result.bridge_weakened is False
    assert result.bridge_lost is False


def test_the_scan_profile_separates_weakening_from_breaking():
    """Two different claims, kept apart: weakened is stronger than a poor
    lift and weaker than a lost bridge."""
    lifts = [
        _pair(10, position=1, substitution="A1G"),
        _pair(1, position=2, substitution="K2A"),   # weakened
        _pair(0, position=3, substitution="R3A"),   # lost
    ]
    profile = lift_module.scan_profile(lifts, "AKR")
    assert profile["bridge_breaking"] == ["R3A"]
    assert profile["bridge_weakening"] == ["K2A"], profile["bridge_weakening"]

    # And the fields travel to the rows the chart and the headline picks read.
    row = next(r for r in profile["positions"] if r["position"] == 2)
    assert row["bridge_weakened"] is True
    assert row["bridge_rate_change"] == -0.9


def test_the_thresholds_come_from_config():
    from nobble import paths

    design = paths.thresholds()["design"]
    assert lift_module.MINIMUM_SEEDS == int(design["minimum_seeds"])
    assert lift_module.BRIDGE_RATE_RETAINED_MIN == float(
        design["bridge_rate_retained_min"]
    )
