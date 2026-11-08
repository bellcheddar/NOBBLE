"""The Sievers arm as a matched design (F317).

`peptides.py` pairs every positive with the four non-degraded zinc fingers
closest to it in length and composition, gives each control its positive's
drug, and records `parent_peptide_id`. Spec 5.3's ROC then pools all of them
into one curve, which discards the matching the arm exists for.

These check the block construction, the within-block statistic and the one
thing that decides whether the headline figure means anything: that the
composite is reported held out as well as in sample, because it was fitted
on these pairs.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import matched_arm_stratified as stratified                # noqa: E402


def test_the_within_block_auc_counts_ties_as_a_half():
    """A tie is neither a win nor a loss, and dropping them instead would
    change the denominator per block."""
    blocks = {"p": ["a", "b", "c", "d"]}
    values = {"p": 1.0, "a": 0.0, "b": 1.0, "c": 2.0, "d": 0.0}
    result = stratified.within_block(blocks, values.get)
    # beats a and d, ties b, loses to c: (2 + 0.5) / 4
    assert result["mean_within_block_auc"] == pytest.approx(0.625)


def test_a_block_is_one_observation_not_four():
    """Four comparisons sharing a positive are not four independent facts,
    so the sign test runs over blocks."""
    blocks = {f"p{i}": [f"n{i}a", f"n{i}b"] for i in range(3)}
    values = {}
    for i in range(3):
        values[f"p{i}"] = 1.0
        values[f"n{i}a"] = 0.0
        values[f"n{i}b"] = 0.0
    result = stratified.within_block(blocks, values.get)
    assert result["blocks"] == 3
    assert result["blocks_above_half"] == 3
    assert result["p_two_sided"] == pytest.approx(2 / 2 ** 3)


def test_a_block_at_exactly_a_half_counts_neither_way():
    """It is evidence for nothing, and counting it as a win would bias every
    statistic with ties upward."""
    blocks = {"p": ["a", "b"]}
    values = {"p": 1.0, "a": 0.0, "b": 2.0}
    result = stratified.within_block(blocks, values.get)
    assert result["mean_within_block_auc"] == pytest.approx(0.5)
    assert result["blocks_above_half"] == 0
    assert result["blocks_below_half"] == 0
    assert result["p_two_sided"] is None


def test_a_positive_with_no_value_contributes_no_block():
    blocks = {"p": ["a"], "q": ["b"]}
    values = {"q": 1.0, "a": 0.0, "b": 0.0}
    result = stratified.within_block(blocks, values.get)
    assert result["blocks"] == 1


def test_the_composite_is_reported_both_ways():
    """The whole interpretation turns on this. It was fitted on these pairs,
    so its in-sample within-block figure is F312's optimism in a different
    slicing, and a table with only that row would read as a result."""
    source = (ROOT / "tools" / "matched_arm_stratified.py").read_text()
    assert "composite, in sample" in source
    assert "composite, held out" in source
    assert "held_out_composite" in source


def test_the_held_out_score_comes_from_a_fold_that_excluded_the_row():
    """Otherwise it is the in-sample number under another name."""
    import ast

    source = (ROOT / "tools" / "matched_arm_stratified.py").read_text()
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "held_out_composite")
    body = ast.unparse(function)
    assert "W._folds" in body
    assert "index not in held" in body
    assert "W.fit_rows(train)" in body


def test_the_live_arm_has_the_blocks_the_design_claims():
    """24 positives with four controls each. A block of a different size
    means the matching was not what `sievers_matched_set` describes."""
    from nobble import paths
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")
    rows = paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
    by_peptide = {row["peptide_id"]: row for row in rows
                  if row.get("peptide_id")}
    blocks = stratified.blocks_of(by_peptide)
    if not blocks:
        pytest.skip("no matched blocks on this checkout")
    sizes = {len(controls) for controls in blocks.values()}
    assert sizes == {4}, f"block sizes are {sorted(sizes)}, not four each"


def test_the_pairing_is_absent_from_the_scores_and_present_in_the_manifest():
    """The reason this tool joins a manifest. If the assembler ever carries
    the field through, this fails and the join can be dropped, which is the
    outcome to want."""
    from nobble import paths
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    library = ROOT / "data" / "manifests" / "library.jsonl"
    if campaign is None or not library.exists():
        pytest.skip("no campaign or library manifest on this checkout")

    in_manifest = [entry for entry in paths.read_jsonl(library, tolerate_torn=True)
                   if entry.get("parent_peptide_id")
                   and entry.get("source") == "sievers_zf"]
    assert in_manifest, "the library manifest carries no Sievers pairing"

    scores = paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
    carried = [row for row in scores
               if str(row.get("pair_id") or "").startswith("sv_")
               and row.get("parent_peptide_id")]
    if carried:
        pytest.skip(
            "the scores now carry the pairing, so the manifest join in "
            "tools/matched_arm_stratified.py can be dropped")
