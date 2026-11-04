"""The frozen curation artefacts, checked against the rules that made them.

A mutation sweep over the curation modules caught one of five. The four
misses all decide which pairs enter a campaign: the mandatory Tier A
ligases, Tier B's pocket-druggability floor, the pLDDT profile's choice of
atoms, and whether the diversity reduction's selection is used at all.

They are unexercised because the selection is frozen and committed: the
campaign is assembled, so nothing reruns the code that assembled it. That
is the right operating choice and it leaves the rules untested, so a
future rerun could produce a different library with nothing to say so.

These test the artefacts against the rules instead of rerunning the
derivation, which needs an ESM checkpoint and BINMAN's triage table. The
worst of the four misses is the clearest: with the reduction's selection
ignored, `library.jsonl` would hold all 25,519 candidates rather than 158,
and the campaign would be 383,000 jobs instead of 2,360.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MANIFEST = ROOT / "data" / "manifests" / "library.jsonl"
SUMMARY = ROOT / "data" / "manifests" / "library.summary.json"


def _library():
    if not MANIFEST.exists() or not SUMMARY.exists():
        pytest.skip("no library manifest on this checkout")
    rows = [json.loads(line) for line in MANIFEST.read_text().splitlines()
            if line.strip()]
    return rows, json.loads(SUMMARY.read_text())


def test_the_manifest_holds_exactly_the_selection_it_records():
    """The manifest and its own summary have to agree about what was
    selected, or one of them is describing a different campaign."""
    rows, summary = _library()
    written = [row["peptide_id"] for row in rows]
    recorded = summary["selected_ids"]

    assert len(written) == summary["selected"], (
        f"manifest holds {len(written)} peptides, the summary says "
        f"{summary['selected']}"
    )
    assert written == recorded, "the manifest's order or membership has drifted"


def test_the_reduction_actually_reduced():
    """With the reduction's selection ignored, every candidate would be
    written and the campaign would be two orders of magnitude larger."""
    rows, summary = _library()
    assert summary["candidates"] > 10_000, summary["candidates"]
    assert len(rows) < summary["candidates"] / 100, (
        f"{len(rows)} selected from {summary['candidates']} candidates is not "
        "a reduction"
    )
    assert 0 < summary["reduction_ratio"] < 0.05, summary["reduction_ratio"]


def test_every_mandatory_source_survived_the_reduction():
    """benchmark and sievers_zf are not trimmed: the Sievers split is the
    headline ROC's control set, and truncating it to hit a budget would
    weaken the measurement it exists to support."""
    rows, summary = _library()
    counts = summary["sources"]
    assert counts["benchmark"] == 7, counts
    assert counts["sievers_zf"] == 120, counts
    assert summary["mandatory"] == counts["benchmark"] + counts["sievers_zf"]

    from collections import Counter
    actual = Counter(row["source"] for row in rows)
    assert dict(actual) == counts, {"manifest": dict(actual), "summary": counts}


def test_being_over_budget_is_recorded_rather_than_absorbed():
    """158 against a budget of 156. The right answer is to say so and keep
    the controls, not to trim two peptides out of the middle."""
    _rows, summary = _library()
    assert summary["selected"] > summary["budget"]
    assert summary["over_budget_by"] == summary["selected"] - summary["budget"]
    assert summary["status"].startswith("over_budget")
    assert any("not trimmed" in note for note in summary["notes"]), summary["notes"]


def test_every_scramble_has_its_parent_in_the_library():
    """A control without its positive measures nothing."""
    rows, _summary = _library()
    present = {row["peptide_id"] for row in rows}
    orphans = [row["peptide_id"] for row in rows
               if row["source"] == "scramble"
               and row.get("parent_peptide_id") not in present]
    assert not orphans, f"scrambles whose parent is absent: {orphans[:5]}"


def test_the_frozen_tier_b_selection_respects_its_own_floor():
    """Spec 3.3's selection function, against the frozen rows.

    The pLDDT floor applies to `best_window_mean_plddt`, not to
    `mean_plddt`. Both columns are in the table and the threshold is named
    `mean_plddt_min`, which is how I first asserted it against the wrong
    one and read "7 of 15 ligases below the floor" as a defect. It is the
    opposite: a whole-model mean punishes a protein with one tight domain
    and long disordered linkers, which is the shape Tier B is looking for,
    so plddt.py takes the best contiguous window instead.
    """
    from nobble import paths

    if not paths.TIER_B_SELECTION.exists():
        pytest.skip("no frozen Tier B selection on this checkout")
    pandas = pytest.importorskip("pandas")

    frame = pandas.read_parquet(paths.TIER_B_SELECTION)
    limits = paths.thresholds()["tier_b"]
    pocket_floor = float(limits["pocket_druggability_min"])
    plddt_floor = float(limits["mean_plddt_min"])

    below = frame[frame["pocket_score"] < pocket_floor]
    assert below.empty, (
        f"{len(below)} frozen Tier B ligase(s) below the {pocket_floor} "
        "pocket-druggability floor"
    )

    below = frame[frame["best_window_mean_plddt"] < plddt_floor]
    assert below.empty, (
        f"{len(below)} frozen Tier B ligase(s) below the {plddt_floor} "
        "best-window pLDDT floor"
    )
    assert (frame["plddt_status"] == "ok").all()


def test_the_plddt_floor_is_not_applied_to_the_whole_model_mean():
    """The distinction, pinned from the other side.

    Seven of the fifteen frozen ligases are below 80 on `mean_plddt` and
    all fifteen are above it on `best_window_mean_plddt`. So a selection
    that switched to the whole-model mean would reject nearly half the
    tier, and this test fails if it ever does.
    """
    from nobble import paths

    if not paths.TIER_B_SELECTION.exists():
        pytest.skip("no frozen Tier B selection on this checkout")
    pandas = pytest.importorskip("pandas")

    frame = pandas.read_parquet(paths.TIER_B_SELECTION)
    floor = float(paths.thresholds()["tier_b"]["mean_plddt_min"])

    whole_model_failures = int((frame["mean_plddt"] < floor).sum())
    window_failures = int((frame["best_window_mean_plddt"] < floor).sum())
    assert window_failures == 0
    assert whole_model_failures > 0, (
        "no frozen ligase is below the floor on its whole-model mean, so "
        "this test can no longer tell the two columns apart"
    )
    assert (frame["best_window_mean_plddt"] >= frame["mean_plddt"]).all(), (
        "a best window scores below the whole-model mean it is drawn from"
    )


def test_the_tier_b_selection_is_the_configured_size():
    from nobble import paths

    if not paths.TIER_B_SELECTION.exists():
        pytest.skip("no frozen Tier B selection on this checkout")
    pandas = pytest.importorskip("pandas")

    frame = pandas.read_parquet(paths.TIER_B_SELECTION)
    take_top = int(paths.thresholds()["tier_b"]["take_top"])
    assert len(frame) == take_top, (
        f"frozen Tier B holds {len(frame)} rows, take_top is {take_top}"
    )
