"""The registered predictions can return wrong, which is the whole point.

F18: "a scorer that cannot return wrong is not scoring anything". F251, F252
and F253 were registered before their data existed, so each is scored here
against a fixture that should refute it as well as one that should support it.
If only the supporting case were tested, the scorer would be decoration.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "check_registered", ROOT / "tools" / "check_registered.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sievers(tmp_path, tier2_shift):
    """Four degraded and six not, with tier-2 deltas shifted by arm."""
    from nobble.validate import layers

    campaign = tmp_path / "campaign_f251"
    campaign.mkdir()
    tier1, tier2 = [], []
    for index in range(4):
        pair = f"sv_pos_{index}"
        tier1.append({"pair_id": pair, "tier": layers.ROC_ARM,
                      "peptide_label": "degraded", "delta_iptm": 0.05})
        tier2.append({"pair_id": pair, "delta_iptm": 0.05 + tier2_shift})
    for index in range(6):
        pair = f"sv_neg_{index}"
        tier1.append({"pair_id": pair, "tier": layers.ROC_ARM,
                      "peptide_label": "not_degraded", "delta_iptm": 0.10})
        tier2.append({"pair_id": pair, "delta_iptm": 0.10})
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in tier1))
    (campaign / "scores_tier2.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in tier2))
    return campaign


def test_f251_is_not_yet_testable_without_tier_two_scores(tmp_path):
    campaign = tmp_path / "campaign_bare"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text("")
    verdict = _module().f251_refinement_discrimination(campaign)
    assert verdict["status"] == "not yet testable", verdict
    assert "scores_tier2" in verdict["detail"], verdict


def test_f251_returns_wrong_when_refinement_separates(tmp_path):
    """Positives overtaking the negatives is the falsifier, not the claim."""
    verdict = _module().f251_refinement_discrimination(
        _sievers(tmp_path, tier2_shift=0.40))
    assert verdict["status"] == "WRONG", verdict
    assert abs(verdict["move"]) > 0.10, verdict


def test_f251_is_supported_when_nothing_moves(tmp_path):
    verdict = _module().f251_refinement_discrimination(
        _sievers(tmp_path, tier2_shift=0.0))
    assert verdict["status"] == "supported", verdict
    assert verdict["move"] == 0.0, verdict


def _profile(tmp_path, position):
    campaign = tmp_path / "design_f252"
    campaign.mkdir()
    (campaign / "scan_profile.json").write_text(json.dumps(
        {"most_sensitive": {"position": position, "substitution": "X",
                            "lift": -0.5}}))
    return campaign


def test_f252_is_supported_on_a_contacting_position(tmp_path):
    verdict = _module().f252_design_scan_position(_profile(tmp_path, 7))
    assert verdict["status"] == "supported", verdict


def test_f252_returns_wrong_on_a_position_touching_nothing(tmp_path):
    verdict = _module().f252_design_scan_position(_profile(tmp_path, 14))
    assert verdict["status"] == "WRONG", verdict


def test_f252_is_unclear_in_between(tmp_path):
    verdict = _module().f252_design_scan_position(_profile(tmp_path, 10))
    assert verdict["status"] == "unclear", verdict


def _tier_b(tmp_path, positive_seeds, scramble_seeds):
    campaign = tmp_path / "tier_b_f253"
    campaign.mkdir()
    rows = [
        {"pair_id": "tb_pos_ASB8_BRD4_759",
         "bridging_seeds_with_bridge": positive_seeds},
        {"pair_id": "tb_neg_ASB8_BRD4_759",
         "bridging_seeds_with_bridge": scramble_seeds},
    ]
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    return campaign


def test_f253_is_supported_when_nothing_clears_the_line(tmp_path):
    verdict = _module().f253_tier_b_bridging(_tier_b(tmp_path, 3, 2))
    assert verdict["status"] == "supported", verdict
    assert verdict["hits"] == [], verdict


def test_f253_returns_wrong_on_a_hit(tmp_path):
    """The positive bridges and its own scramble does not."""
    verdict = _module().f253_tier_b_bridging(_tier_b(tmp_path, 9, 1))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["hits"][0]["pair_id"] == "tb_pos_ASB8_BRD4_759", verdict


def test_f253_needs_the_scramble_before_it_judges(tmp_path):
    """A positive with no matched scramble is counted, never scored."""
    campaign = tmp_path / "tier_b_unpaired"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(json.dumps(
        {"pair_id": "tb_pos_ASB8_BRD4_759",
         "bridging_seeds_with_bridge": 10}) + "\n")
    verdict = _module().f253_tier_b_bridging(campaign)
    assert verdict["status"] == "supported", verdict
    assert verdict["unpaired"] == 1, verdict


def test_the_live_state_is_every_prediction_pending():
    """Today: nothing has run, so nothing is scored and nothing is wrong."""
    assert _module().main([]) == 0
