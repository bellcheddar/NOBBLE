"""Tier 2 must say where the refinement budget went.

Twenty-five diffusion samples per job against tier 1's one, on the top
decile. The ranking is deliberately blind to which arm a pair belongs to:
a scramble that ranks top is a result, and excluding it would hide it.

But the selection recorded which key it ranked on and not which arm each
chosen pair came from, so "2 pairs selected" could mean two negative
controls and a reader would have had to cross-reference scores.jsonl to
find out.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import tier2  # noqa: E402


def _campaign(tmp_path, rows):
    (tmp_path / "scores.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return tmp_path


def _candidate(index, percentile):
    return {"pair_id": f"sv{index}", "tier": "sievers_zf",
            "peptide_label": "degraded", "bridge_percentile": percentile}


def _control(index, percentile):
    return {"pair_id": f"scr{index}", "tier": "scramble",
            "peptide_label": "negative_control", "bridge_percentile": percentile}


def test_a_decile_made_of_controls_says_so(tmp_path):
    """The case worth catching: every refined pair is a negative control."""
    rows = [_candidate(i, 50 + i) for i in range(16)] + \
           [_control(i, 90 + i) for i in range(4)]
    selection = tier2.select_top_decile(_campaign(tmp_path, rows))

    assert selection.status == "selected"
    assert selection.arms == {"scramble": 2}
    note = next((n for n in selection.notes if "controls" in n), None)
    assert note, selection.notes
    assert "2 of 2" in note
    # And the arm travels on each selected row, not only in the summary.
    assert all(item["tier"] == "scramble" for item in selection.selected)
    assert all(item["peptide_label"] == "negative_control"
               for item in selection.selected)


def test_a_decile_of_candidates_carries_no_control_note(tmp_path):
    """A note on every selection would be noise, and CLAUDE.md is explicit
    that a caveat repeated everywhere reads as a lack of confidence."""
    rows = [_candidate(i, 50 + i) for i in range(16)] + \
           [_control(i, 10 + i) for i in range(4)]
    selection = tier2.select_top_decile(_campaign(tmp_path, rows))

    assert selection.arms == {"sievers_zf": 2}
    assert not any("controls" in n for n in selection.notes)


def test_the_ranking_itself_stays_blind_to_the_arm(tmp_path):
    """Reporting the arm must not become filtering by it. A control that
    outranks every candidate is a finding, and refusing to refine it would
    be the one way to make sure nobody saw it."""
    rows = [_candidate(i, 50 + i) for i in range(16)] + \
           [_control(i, 99) for i in range(4)]
    selection = tier2.select_top_decile(_campaign(tmp_path, rows))

    assert selection.pairs_selected == 2
    assert [item["pair_id"] for item in selection.selected][0].startswith("scr")


def test_the_arm_summary_is_absent_when_nothing_was_selected(tmp_path):
    rows = [_candidate(0, 50)]
    selection = tier2.select_top_decile(_campaign(tmp_path, rows))
    # One pair is below the floor to rank on at all.
    assert selection.status.startswith("not_selected")
    assert selection.arms == {}


def test_the_tier2_queue_reuses_the_tier1_yaml_paths(tmp_path):
    """The property that makes correcting a pair's tier-1 input sufficient.

    `build_tier2_queue`'s docstring says the YAMLs "do not change" and are
    "reused verbatim", and the whole correction path depends on it: F47's
    hydroxyproline was fixed by regenerating the tier-1 YAMLs, and that only
    corrects the refinement because tier 2 reads the same files. If tier 2
    ever copied or regenerated them, the chain would have to correct twice
    and nothing would say so (F62).
    """
    import json

    from nobble.execute import tier2

    campaign = tmp_path / "campaign_20261104T000000Z"
    (campaign / "yaml").mkdir(parents=True)
    rows = []
    for index, (pair, complex_type) in enumerate(
            [("p1", "ternary"), ("p1", "binary"), ("p2", "ternary")]):
        path = campaign / "yaml" / f"job{index}.yaml"
        path.write_text("sequences: []\n")
        rows.append({"job_id": f"job{index}", "pair_id": pair,
                     "complex_type": complex_type, "yaml": str(path),
                     "tokens": 150, "seed": 1})
    (campaign / "queue.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")

    selection = tier2.Selection(
        campaign=campaign.name, ranking_key="bridge_percentile",
        decile_fraction=0.1, pairs_considered=2, pairs_selected=1,
        selected=[{"pair_id": "p1"}], arms={"benchmark": 1},
        forced_excluded=[], status="selected")
    result = tier2.build_tier2_queue(campaign, selection)

    emitted = [json.loads(line) for line in
               (campaign / "queue_tier2.jsonl").read_text().splitlines()
               if line.strip()]
    assert result["jobs"] == 1, "only p1's ternary job should be refined"
    assert emitted[0]["yaml"] == rows[0]["yaml"], (
        "tier 2 no longer points at the tier-1 YAML, so correcting a pair's "
        "tier-1 input would not correct its refinement"
    )
    assert emitted[0]["job_id"] == "job0__tier2"
    assert emitted[0]["tier_setting"] == 2
