"""The design arm's entry point had thirty tests around it and none on it.

`lift.from_scores` is what the Design tab and `tools/run_design.sh` both
call. Thirty tests in `test_design.py` cover the pieces it composes,
`lift.compute` and `scan_profile`, and one mentions `from_scores` in its
docstring, but nothing called it. The composition is where the selection
happens: which row is the parent, which rows are its variants, and what is
reported when either is missing.

That selection is the part that can be wrong without any single piece being
wrong. It filters on `tier == "design"` and on `parent_peptide_id`, and
either filter failing open would compose lifts from rows that are not
variants of this parent at all, producing a difference of differences
between unrelated pairs. Every number downstream would be plausible.

The one path still never executed on real data, because it needs design
results and the design campaign is queued behind the main one (F63).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.design import lift as Lmod  # noqa: E402

PARENT_SEQUENCE = "PFQCNQCGASFTQKG"


def _row(**kwargs) -> dict:
    base = {"construct": "CRBN_CULT", "e3_gene": "CRBN", "ligand_key": "Y70",
            "modality": "glue", "seeds_binary": 5, "seeds_ternary": 5,
            "delta_iptm": 0.30, "peptide_id": "parent1", "pair_id": "p1",
            "peptide_sequence": PARENT_SEQUENCE, "tier": "benchmark"}
    base.update(kwargs)
    return base


def _variant(substitution, delta, position, **kwargs):
    fields = {"peptide_id": f"design_{substitution}",
              "pair_id": f"v_{substitution}",
              "parent_peptide_id": "parent1", "tier": "design",
              "substitution": substitution, "position": position,
              "delta_iptm": delta}
    fields.update(kwargs)
    return _row(**fields)


def _scores(tmp_path, rows) -> Path:
    path = tmp_path / "scores.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def test_it_computes_a_lift_for_each_variant_of_the_parent(tmp_path):
    path = _scores(tmp_path, [
        _row(),
        _variant("C4A", 0.50, 4),
        _variant("K14A", 0.10, 14),
    ])
    result = Lmod.from_scores(path, "parent1")
    assert result["parent"] == "parent1"
    assert result["parent_sequence"] == PARENT_SEQUENCE
    assert result["computed"] == 2
    assert result["refused"] == 0
    assert sorted(item["lift"] for item in result["lifts"]) == [-0.2, 0.2]


def test_a_variant_of_a_different_parent_is_not_included(tmp_path):
    """The filter that matters most. A lift is a difference of differences,
    so composing it against the wrong parent yields a number that is
    plausible and is about two unrelated peptides."""
    path = _scores(tmp_path, [
        _row(),
        _row(peptide_id="parent2", pair_id="p2"),
        _variant("C4A", 0.50, 4),
        _variant("Q6A", 0.90, 6, parent_peptide_id="parent2"),
    ])
    result = Lmod.from_scores(path, "parent1")
    assert len(result["lifts"]) == 1
    assert result["lifts"][0]["substitution"] == "C4A"


def test_a_row_that_is_not_a_design_row_is_not_a_variant(tmp_path):
    """Both filters are required. A benchmark row carrying a
    parent_peptide_id would otherwise be scanned as though it were a
    designed substitution."""
    path = _scores(tmp_path, [
        _row(),
        _row(peptide_id="sievers1", pair_id="s1",
             parent_peptide_id="parent1", tier="sievers_zf", delta_iptm=0.9),
    ])
    result = Lmod.from_scores(path, "parent1")
    assert result["lifts"] == []
    assert result["computed"] == 0


def test_a_refused_lift_is_counted_and_not_dropped(tmp_path):
    """A variant run against a different glue cannot be subtracted. It has
    to appear as refused rather than vanish, or the scan would silently
    report a profile with a hole in it."""
    path = _scores(tmp_path, [
        _row(),
        _variant("C4A", 0.50, 4),
        _variant("Q6A", 0.90, 6, ligand_key="LVY"),
    ])
    result = Lmod.from_scores(path, "parent1")
    assert result["computed"] == 1
    assert result["refused"] == 1
    assert len(result["lifts"]) == 2
    refused = [item for item in result["lifts"] if item["lift"] is None]
    assert len(refused) == 1
    assert refused[0]["status"].startswith("not_computed")


def test_an_unscored_parent_is_reported_rather_than_assumed(tmp_path):
    path = _scores(tmp_path, [_variant("C4A", 0.50, 4)])
    result = Lmod.from_scores(path, "parent1")
    assert result["lifts"] == []
    assert "parent1" in result["status"]
    assert "not scored" in result["status"]


def test_a_missing_scores_file_is_reported_rather_than_crashing(tmp_path):
    result = Lmod.from_scores(tmp_path / "absent.jsonl", "parent1")
    assert result["status"] == "no scores"
    assert result["lifts"] == []


def test_a_parent_with_no_variants_yet_reports_zero_not_an_error(tmp_path):
    """What the Design tab shows while the scan is still queued."""
    path = _scores(tmp_path, [_row()])
    result = Lmod.from_scores(path, "parent1")
    assert result["lifts"] == []
    assert result["computed"] == 0
    assert result["refused"] == 0
    assert result["parent"] == "parent1"


def test_the_output_feeds_scan_profile_without_reshaping(tmp_path):
    """The composition the Design tab performs: from_scores, then Lift
    objects, then scan_profile. report.py rebuilds Lift from each dict, so
    the dicts have to round-trip."""
    path = _scores(tmp_path, [
        _row(),
        _variant("C4A", 0.50, 4),
        _variant("K14A", 0.10, 14),
    ])
    result = Lmod.from_scores(path, "parent1")
    objects = [Lmod.Lift(**item) for item in result["lifts"]]
    profile = Lmod.scan_profile(objects, PARENT_SEQUENCE)
    assert profile, "scan_profile returned nothing for two computed lifts"
    positions = profile.get("positions") or profile.get("ranked") or []
    assert positions, f"no ranked positions in {sorted(profile)}"
