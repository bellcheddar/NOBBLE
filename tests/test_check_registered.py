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
                      "peptide_label": "degraded",
                      "bridge_formation_rate": 0.5})
        tier2.append({"pair_id": pair,
                      "bridge_formation_rate": 0.5 + tier2_shift})
    for index in range(6):
        pair = f"sv_neg_{index}"
        tier1.append({"pair_id": pair, "tier": layers.ROC_ARM,
                      "peptide_label": "not_degraded",
                      "bridge_formation_rate": 0.5})
        tier2.append({"pair_id": pair, "bridge_formation_rate": 0.5 + tier2_shift})
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in tier1))
    (campaign / "scores_tier2.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in tier2))
    return campaign


def test_f251_is_withdrawn_rather_than_pending(tmp_path):
    """Pending would have waited forever for a measurement that cannot exist.

    Tier 2 is ternary-only, so Delta-ipTM has no binary term there. Left as
    "not yet testable" the scorer would have waited for scores_tier2.jsonl and
    then skipped every row for a null delta, reporting a missing measurement
    as an unfinished stage (F251, F254).
    """
    campaign = tmp_path / "campaign_bare"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text("")
    verdict = _module().f251_refinement_discrimination(campaign)
    assert verdict["status"] == "withdrawn", verdict
    assert "ternary-only" in verdict["detail"], verdict
    assert "F254" in verdict["detail"], verdict


def test_f254_is_not_yet_testable_without_tier_two_scores(tmp_path):
    campaign = tmp_path / "campaign_bare2"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text("")
    verdict = _module().f254_refinement_bridging(campaign)
    assert verdict["status"] == "not yet testable", verdict
    assert "scores_tier2" in verdict["detail"], verdict


def test_f254_returns_wrong_when_refinement_finds_bridges(tmp_path):
    """A rise beyond the line is the falsifier, not the claim."""
    verdict = _module().f254_refinement_bridging(
        _sievers(tmp_path, tier2_shift=0.40))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["move"] > 0.10, verdict


def test_f254_returns_wrong_when_refinement_loses_bridges(tmp_path):
    """A fall is refuting too: it would mean tier 1 overstates the rate."""
    verdict = _module().f254_refinement_bridging(
        _sievers(tmp_path, tier2_shift=-0.40))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["move"] < -0.10, verdict


def test_f254_is_supported_when_nothing_moves(tmp_path):
    verdict = _module().f254_refinement_bridging(
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


def _tier_b(tmp_path, positive_rate, scramble_rate):
    campaign = tmp_path / "tier_b_f253"
    campaign.mkdir()
    rows = [
        {"pair_id": "tb_pos_ASB8_BRD4_759",
         "bridge_formation_rate": positive_rate},
        {"pair_id": "tb_neg_ASB8_BRD4_759",
         "bridge_formation_rate": scramble_rate},
    ]
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    return campaign


def test_f253_is_supported_when_nothing_clears_the_line(tmp_path):
    verdict = _module().f253_tier_b_bridging(_tier_b(tmp_path, 0.6, 0.4))
    assert verdict["status"] == "supported", verdict
    assert verdict["hits"] == [], verdict


def test_f253_returns_wrong_on_a_hit(tmp_path):
    """The positive bridges and its own scramble does not.

    Stated as a rate because Tier B runs five ternary seeds per arm: the
    first version of this line asked for eight of ten and could never fire.
    """
    # 0.8 against 0.2 is 4 of 5 against 1 of 5, which is what Tier B runs.
    verdict = _module().f253_tier_b_bridging(_tier_b(tmp_path, 0.8, 0.2))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["hits"][0]["pair_id"] == "tb_pos_ASB8_BRD4_759", verdict


def test_f253_needs_the_scramble_before_it_judges(tmp_path):
    """A positive with no matched scramble is counted, never scored."""
    campaign = tmp_path / "tier_b_unpaired"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(json.dumps(
        {"pair_id": "tb_pos_ASB8_BRD4_759",
         "bridge_formation_rate": 1.0}) + "\n")
    verdict = _module().f253_tier_b_bridging(campaign)
    assert verdict["status"] == "supported", verdict
    assert verdict["unpaired"] == 1, verdict


def test_the_live_state_is_every_prediction_pending():
    """Today: nothing has run, so nothing is scored and nothing is wrong."""
    assert _module().main([]) == 0


def test_the_brief_mode_is_one_line_per_prediction():
    """A status command is scanned, so the claims stay in the full output."""
    import io
    import contextlib

    module = _module()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.main(["--brief"])
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    # One summary line plus one per prediction.
    assert len(lines) == 5, lines
    assert all("falsifier" not in line for line in lines), lines
    for finding in ("F251", "F252", "F253", "F254"):
        assert any(finding in line for line in lines), (finding, lines)


def test_the_status_command_surfaces_the_verdicts():
    """Wired where it is read, since the chain cannot be edited mid-run."""
    text = (ROOT / "tools" / "status.sh").read_text()
    assert "check_registered.py --brief" in text, (
        "status.sh does not surface the registered predictions, so a verdict "
        "would only appear if someone ran the tool by hand")


def test_the_chain_wiring_is_recorded_as_outstanding():
    """run_chain.sh was executing when this was written.

    Editing a running bash script corrupts it, because the shell reads it
    incrementally. The chain already calls status.sh as its last line, so the
    verdicts do appear at the end of a run; what is outstanding is calling the
    scorer at each stage, and the reason it was not done is in status.sh.
    """
    # Normalised, because the comment wraps and the phrase crosses a line
    # with a "# " between: searching the raw text for it cannot match, which
    # is how this assertion failed when it was written.
    raw = (ROOT / "tools" / "status.sh").read_text()
    text = " ".join(raw.replace("#", " ").split())
    assert "executing while this is written" in text, (
        "the reason the chain itself is not wired has been lost")
    assert "bash tools/status.sh" in (ROOT / "tools" / "run_chain.sh").read_text()
