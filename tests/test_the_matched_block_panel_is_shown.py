"""The matched arm's stratified panel (F317, F318).

The page shows spec 5.3's pooled ROC over 24 positives against 96 negatives.
That arm was built matched, pooling discards the matching, and the
better-powered analysis gives a stronger null. Showing only the pooled curve
shows the weaker of two analyses of one dataset.

These check that the composite's in-sample row cannot be read as a result,
that the block count is visible, and that an older bundle says so.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MEASURED = {
    "status": "measured",
    "blocks": 24,
    "controls_per_block": [4],
    "statistics_tested": 7,
    "bonferroni_threshold": 0.00714,
    "unfitted_statistics": 5,
    "results": [
        {"statistic": "delta_iptm", "blocks": 24,
         "mean_within_block_auc": 0.4271, "blocks_above_half": 8,
         "blocks_below_half": 13, "p_two_sided": 0.38331},
        {"statistic": "composite, in sample", "blocks": 24,
         "mean_within_block_auc": 0.7083, "blocks_above_half": 18,
         "blocks_below_half": 4, "p_two_sided": 0.00434},
        {"statistic": "composite, held out", "blocks": 24,
         "mean_within_block_auc": 0.6146, "blocks_above_half": 12,
         "blocks_below_half": 4, "p_two_sided": 0.07681},
    ],
}


def _page(tmp_path: Path, about: dict) -> str:
    from nobble.app import create_app

    (tmp_path / "about.json").write_text(json.dumps(about))
    app = create_app(str(tmp_path))
    app.config["TESTING"] = True
    body = app.test_client().get("/about")
    assert body.status_code == 200, body.status_code
    return body.get_data(as_text=True)


def test_the_panel_shows_the_arm_within_its_blocks(tmp_path):
    page = _page(tmp_path, {"matched_blocks": MEASURED})
    assert "The same arm, within its matched blocks" in page
    assert "0.4271" in page
    assert "0.6146" in page


def test_the_in_sample_composite_row_is_qualified_in_words(tmp_path):
    """0.7083 at p 0.00434 is the only figure in the table that crosses the
    corrected threshold and it is in-sample, so a panel that printed it
    without saying which row to read would be worse than one that omitted
    the analysis."""
    page = _page(tmp_path, {"matched_blocks": MEASURED})
    assert "fitted on these pairs" in page
    assert "read" in page and "held-out row" in page


def test_the_block_count_and_block_size_are_both_shown(tmp_path):
    """A within-block AUC over four controls takes five values, so the block
    size is what tells a reader how coarse the statistic is."""
    page = _page(tmp_path, {"matched_blocks": MEASURED})
    assert "4 controls" in page or "4 or" in page or ">4<" in page
    assert ">24<" in page


def test_the_family_threshold_is_printed(tmp_path):
    page = _page(tmp_path, {"matched_blocks": MEASURED})
    assert "7 statistics" in page
    assert "0.00714" in page


def test_an_older_bundle_says_so(tmp_path):
    page = _page(tmp_path, {"sources": {}})
    assert "The same arm, within its matched blocks" in page
    assert "built before the analysis existed" in page


def test_a_failed_analysis_carries_its_reason(tmp_path):
    page = _page(tmp_path, {"matched_blocks": {
        "status": "unavailable: FileNotFoundError: library.jsonl",
        "results": []}})
    assert "FileNotFoundError" in page


def test_the_panel_sits_with_the_pooled_curve_not_at_the_end():
    """Two analyses of one dataset belong together. Separated by three
    panels, a reader takes the first as the answer."""
    template = (ROOT / "nobble" / "app" / "templates" / "about.html").read_text()
    pooled = template.index("matched_control_roc")
    stratified = template.index("The same arm, within its matched blocks")
    scrambles = template.index("Each pair against its own scramble")
    assert pooled < stratified < scrambles, (
        "the stratified panel is not between the pooled curve and the "
        "scramble test"
    )


def test_the_build_computes_it_in_its_own_guard():
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "matched_arm_stratified" in source
    assert '"matched_blocks": matched_blocks' in source
    position = source.index("import matched_arm_stratified")
    assert "except Exception as problem" in source[position:position + 900]
