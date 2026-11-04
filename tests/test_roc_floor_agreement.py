"""The ROC chart and the ROC number must refuse at the same point.

delta.html's own comment says it: "This filter and the Python one have to
agree, because the figure here and the number in the validation report are
supposed to be the same curve."

They agreed by both being written as a literal 3. Then F28 moved the
Python side to `thresholds.toml` as `roc_minimum_per_side` and left the
template's literal where it was, so the two were one config edit away from
disagreeing, and nothing would have failed: the chart would have drawn a
curve the validation report refused, or refused one the report drew.

A divergence of mine, made while removing hard-coded cutoffs, and the kind
that only shows when someone changes the value (F54).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEMPLATE = ROOT / "nobble" / "app" / "templates" / "delta.html"


def _rendered_floor(campaign: str) -> int:
    from nobble.app import create_app

    app = create_app(campaign)
    with app.test_client() as client:
        response = client.get("/delta")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
    match = re.search(r"const ROC_MINIMUM_PER_SIDE = (\d+);", body)
    assert match, "the page no longer carries the floor"
    return int(match.group(1))


def test_the_page_and_the_layer_refuse_at_the_same_floor():
    from nobble.validate import layers

    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        pytest.skip("no published atlas")
    assert _rendered_floor(str(atlas)) == layers.ROC_MINIMUM_PER_SIDE


def test_both_read_it_from_the_same_place():
    """Equality today is not the point: two literals were equal too. The
    point is that one value feeds both."""
    from nobble import paths
    from nobble.validate import layers

    configured = int(paths.thresholds()["validation"]["roc_minimum_per_side"])
    assert layers.ROC_MINIMUM_PER_SIDE == configured

    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        pytest.skip("no published atlas")
    assert _rendered_floor(str(atlas)) == configured


def test_the_template_holds_no_literal_floor():
    """The thing that had drifted. A bare comparison against a number here
    is the divergence coming back."""
    source = TEMPLATE.read_text()
    offenders = re.findall(r"(?:positives|negatives)\.length\s*<\s*\d+", source)
    assert not offenders, (
        f"delta.html compares a count against a literal again: {offenders}"
    )
    assert "ROC_MINIMUM_PER_SIDE" in source


def test_a_changed_floor_moves_both(monkeypatch, tmp_path):
    """The only check that would have caught it. Change the configured
    value and both sides have to follow."""
    import json

    from nobble import paths
    from nobble.validate import layers

    original = paths.thresholds()

    def fake_thresholds():
        altered = json.loads(json.dumps(original))
        altered["validation"]["roc_minimum_per_side"] = 7
        return altered

    monkeypatch.setattr(paths, "thresholds", fake_thresholds)
    monkeypatch.setattr(layers.paths, "thresholds", fake_thresholds)

    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        pytest.skip("no published atlas")

    # The page follows immediately: it reads the value per request.
    assert _rendered_floor(str(atlas)) == 7

    # The layer's constant is bound at import, so reload it the way a fresh
    # process would and confirm it follows too.
    import importlib

    reloaded = importlib.reload(layers)
    try:
        assert reloaded.ROC_MINIMUM_PER_SIDE == 7
    finally:
        monkeypatch.undo()
        importlib.reload(reloaded)
