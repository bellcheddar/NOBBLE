"""Spec 4.7: a forced pose is shown separately and never ranked.

    A pose that only appears under conditioning is flagged `forced: true`.
    Forcing a binder into a site it did not choose reliably produces the
    right neighbourhood and the wrong pose, so forced hits are shown
    separately and never in the headline ranking.

The flag was computed, published and displayed, and nothing acted on it.
A forced pair could take a place in tier 2's decile and twenty-five
diffusion samples with it, refining a pose the spec says is wrong, and it
sat in the headline scatter indistinguishable from a found one.

CDK12 is the live case: conditioned seeds 0.745 to 0.851, unconstrained
0.252 to 0.653, a disagreement of 0.494 (F44).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import tier2  # noqa: E402


def _pair(pair_id, percentile, forced=False, disagreement=None):
    return {
        "pair_id": pair_id, "tier": "sievers_zf", "peptide_label": "degraded",
        "bridge_percentile": percentile, "forced": forced,
        "conditioning_disagreement": disagreement,
    }


def _select(tmp_path, rows):
    (tmp_path / "scores.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return tier2.select_top_decile(tmp_path)


def test_a_forced_pair_does_not_enter_the_decile(tmp_path):
    """Twenty-five diffusion samples is the cost of getting this wrong."""
    rows = [_pair(f"sv{i}", 50 + i) for i in range(16)]
    rows.append(_pair("forced1", 99, forced=True, disagreement=0.49))
    selection = _select(tmp_path, rows)

    chosen = [item["pair_id"] for item in selection.selected]
    assert "forced1" not in chosen, (
        "a forced pair took a place in the refinement decile"
    )
    assert chosen, "nothing was selected at all"


def test_the_exclusion_is_reported_rather_than_silent(tmp_path):
    """Dropped without a word, a forced pair that would have topped the
    decile is a finding nobody sees."""
    rows = [_pair(f"sv{i}", 50 + i) for i in range(16)]
    rows.append(_pair("forced1", 99, forced=True, disagreement=0.49))
    selection = _select(tmp_path, rows)

    assert [item["pair_id"] for item in selection.forced_excluded] == ["forced1"]
    assert selection.forced_excluded[0]["conditioning_disagreement"] == 0.49
    note = next((n for n in selection.notes if "forced" in n), None)
    assert note, selection.notes
    assert "would have entered the decile: forced1" in note, note


def test_a_forced_pair_below_the_cut_is_reported_as_not_having_entered(tmp_path):
    """The distinction matters: one that would have ranked top is a result,
    one that would not is housekeeping."""
    rows = [_pair(f"sv{i}", 50 + i) for i in range(16)]
    rows.append(_pair("forced_low", 10, forced=True, disagreement=0.3))
    selection = _select(tmp_path, rows)

    assert [item["pair_id"] for item in selection.forced_excluded] == ["forced_low"]
    note = next(n for n in selection.notes if "forced" in n)
    assert "would have entered the decile: none" in note, note


def test_a_campaign_with_no_forced_pairs_says_nothing_about_them(tmp_path):
    """A note on every selection is a note nobody reads."""
    selection = _select(tmp_path, [_pair(f"sv{i}", 50 + i) for i in range(16)])
    assert selection.forced_excluded == []
    assert not [n for n in selection.notes if "forced" in n]


def test_excluding_forced_pairs_cannot_empty_the_decile(tmp_path):
    """If every scorable pair is forced there is nothing to refine, and the
    honest answer is to say so rather than to refine a forced pose because
    it was the only candidate."""
    rows = [_pair(f"f{i}", 50 + i, forced=True, disagreement=0.4) for i in range(16)]
    selection = _select(tmp_path, rows)
    assert selection.selected == []
    assert len(selection.forced_excluded) == 16


def test_the_headline_view_draws_forced_pairs_differently():
    """Spec 4.7's "shown separately". The position still carries the
    measurement; the marker says not to read it as a found pose."""
    source = (ROOT / "nobble" / "app" / "templates" / "delta.html").read_text()
    scatter = source[source.index("function buildScatter"):]
    scatter = scatter[:scatter.index("function buildMarginal")]

    assert "p.forced" in scatter, "the headline scatter does not look at forced"
    # Distinguished by the marker, not only in the tooltip.
    assert re.search(r"opacity:\s*rows\.map\(p => p\.forced", scatter), scatter[-400:]
    assert re.search(r"width:\s*rows\.map\(p => p\.forced", scatter)
    # And named in the hover, with the magnitude rather than a bare flag.
    assert "pose only under conditioning" in source
    assert "conditioning_disagreement" in scatter
