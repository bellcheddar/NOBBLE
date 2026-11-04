"""The Tier B selection is frozen, and freeze.py is what keeps it frozen.

PROGRESS records Tier B as 15 ligases, frozen. That is a scientific
commitment: the exploratory arm was chosen once, under thresholds recorded
alongside it, and a later rerun that quietly reselected would change which
ligases the campaign explores without anything saying so.

`write_tier_b` returns early when the file exists. These check it really
does, and that `force` is the only way past, without touching the real
frozen selection.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths
from nobble.curate import freeze


def test_an_existing_selection_is_not_rewritten(tmp_path, monkeypatch):
    import pandas

    target = tmp_path / "tier_b_selection.parquet"
    pandas.DataFrame([{"gene": "DCAF8L1"}, {"gene": "CCNF"}]).to_parquet(
        target, index=False)
    monkeypatch.setattr(paths, "TIER_B_SELECTION", target)
    monkeypatch.setattr(freeze.paths, "TIER_B_SELECTION", target)

    def _must_not_run():
        raise AssertionError("tier_b() was reselected over a frozen file")

    monkeypatch.setattr(freeze.tiers, "tier_b", _must_not_run)

    result = freeze.write_tier_b()
    assert result["written"] is False
    assert result["rows"] == 2


def test_the_real_selection_is_present_and_frozen():
    """Against the actual file rather than a fixture: it exists, and a
    plain call leaves it alone."""
    if not paths.TIER_B_SELECTION.exists():
        pytest.skip("no frozen Tier B selection on this checkout")

    before = paths.TIER_B_SELECTION.stat().st_mtime
    result = freeze.write_tier_b()
    after = paths.TIER_B_SELECTION.stat().st_mtime

    assert result["written"] is False, "a plain call rewrote the frozen selection"
    assert before == after, "the frozen file's mtime moved"
    assert result["rows"] > 0


def test_the_frozen_selection_matches_what_progress_claims():
    """PROGRESS says 15 ligases. A file that has drifted from the written
    record is worse than no record."""
    import pandas

    if not paths.TIER_B_SELECTION.exists():
        pytest.skip("no frozen Tier B selection on this checkout")

    frame = pandas.read_parquet(paths.TIER_B_SELECTION)
    assert len(frame) == 15, f"frozen Tier B holds {len(frame)} rows, PROGRESS says 15"
