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


def _run_template_helper(name: str, rows: list[dict]):
    """Execute one of delta.html's named helpers under node.

    Three string checks of mine were wrong today and none of the executed
    ones were, so the headline view's forced styling is run rather than
    matched. The helper is lifted out of the template by name, which is why
    it is a named arrow function rather than written inline in the Plotly
    trace (F50).
    """
    import json
    import re
    import subprocess

    source = (ROOT / "nobble" / "app" / "templates" / "delta.html").read_text()
    match = re.search(
        r"const " + name + r" = p =>.*?;\n", source, re.S
    )
    assert match, f"{name} is no longer a named helper in delta.html"
    script = match.group(0) + "console.log(JSON.stringify(" \
        + json.dumps(rows) + f".map({name})));"
    completed = subprocess.run(["node", "-e", script], capture_output=True,
                               text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_the_headline_view_draws_a_forced_pair_hollow():
    """Spec 4.7's "shown separately", executed. The position still carries
    the measurement; the marker says not to read it as a found pose."""
    found, forced = _run_template_helper("forcedStyle", [
        {"forced": False},
        {"forced": True, "conditioning_disagreement": 0.494},
    ])
    assert forced["opacity"] < found["opacity"], (forced, found)
    assert forced["width"] > found["width"]
    assert forced["colour"] != found["colour"]


def test_a_pair_with_no_forced_field_is_drawn_as_found():
    """A record from before the flag existed must not render as forced."""
    (plain,) = _run_template_helper("forcedStyle", [{}])
    (found,) = _run_template_helper("forcedStyle", [{"forced": False}])
    assert plain == found


def test_the_hover_gives_the_magnitude_not_a_bare_flag():
    """"forced" is true of CDK12 at 0.494 and of a pair at 0.21, and the
    two are not the same result."""
    labels = _run_template_helper("forcedLabel", [
        {"forced": False},
        {"forced": True, "conditioning_disagreement": 0.494},
        {"forced": True, "conditioning_disagreement": 0.21},
        {"forced": True},
    ])
    assert labels[0] == "no"
    assert "0.494" in labels[1]
    assert "0.210" in labels[2]
    assert labels[1] != labels[2], "two different disagreements read the same"
    # A forced pair whose magnitude was never recorded says so rather than
    # printing a number it does not have.
    assert "unrecorded" in labels[3], labels[3]
