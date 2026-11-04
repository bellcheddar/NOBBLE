"""The design arm (DESIGN_ARM.md).

Two things are being protected here. One is that a variant is always
anchored to a parent, so nothing is scored in the abstract. The other is
that design lift is a difference of differences and only survives if the
parent and the variant were run identically, which is the same rule as
D-NOB-032 and D-NOB-034 one level up.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.design import lift as Lmod
from nobble.design import variants as V

PARENT = "PFQCNQCGASFTQKG"


def test_an_alanine_scan_covers_every_position_exactly_once():
    result = V.generate("p1", PARENT)
    assert result["count"] == len(PARENT)
    positions = [v["position"] for v in result["variants"]]
    assert positions == list(range(1, len(PARENT) + 1))


def test_a_position_already_alanine_is_scanned_to_glycine():
    """Emitting it unchanged would queue a variant identical to its parent:
    15 jobs to learn nothing, and it would read on the chart as "this
    position does not matter" when it was never tested."""
    result = V.generate("p1", "AAACDEFGH")
    first = result["variants"][0]
    assert first["mutant"] == "G"
    assert first["sequence"] != "AAACDEFGH"
    assert any("never tested" in n or "untested" in n for n in first["notes"])


def test_every_variant_differs_from_its_parent_by_exactly_one_residue():
    for variant in V.generate("p1", PARENT)["variants"]:
        differences = sum(1 for a, b in zip(PARENT, variant["sequence"]) if a != b)
        assert differences == 1, variant["substitution"]
        assert len(variant["sequence"]) == len(PARENT)


def test_variant_ids_are_deterministic_and_distinct():
    first = V.generate("p1", PARENT)["variants"]
    second = V.generate("p1", PARENT)["variants"]
    assert [v["variant_id"] for v in first] == [v["variant_id"] for v in second]
    assert len({v["variant_id"] for v in first}) == len(first)


def test_saturation_refuses_without_explicit_positions():
    """Saturating every position of a 15-mer is 285 variants and 4,275 jobs.
    The alanine scan is what chooses where to look."""
    with pytest.raises(ValueError, match="explicit positions"):
        V.generate("p1", PARENT, generator="saturation")


def test_saturation_gives_nineteen_substitutions_and_never_the_wild_type():
    result = V.generate("p1", PARENT, generator="saturation", positions=[7])
    assert result["count"] == 19
    assert all(v["mutant"] != PARENT[6] for v in result["variants"])


def test_a_non_standard_residue_is_refused():
    with pytest.raises(ValueError, match="non-standard"):
        V.generate("p1", "PFQCXQCG")


def _row(**kwargs) -> dict:
    base = {"construct": "CRBN_CULT", "e3_gene": "CRBN", "ligand_key": "Y70",
            "modality": "glue", "seeds_binary": 5, "seeds_ternary": 5,
            "delta_iptm": 0.3, "peptide_id": "parent1", "pair_id": "v1"}
    base.update(kwargs)
    return base


def test_lift_is_the_difference_of_the_two_deltas():
    result = Lmod.compute(_row(delta_iptm=0.50, substitution="K7A"),
                          _row(delta_iptm=0.30))
    assert result.status == "computed"
    assert result.lift == 0.20


def test_a_variant_run_with_a_different_glue_gets_no_lift():
    """The number would be plausible and would report the glue swap rather
    than the substitution."""
    result = Lmod.compute(_row(ligand_key="LVY", delta_iptm=0.9),
                          _row(ligand_key="Y70", delta_iptm=0.3))
    assert result.status.startswith("not_computed")
    assert result.lift is None
    assert any(m["field"] == "ligand_key" for m in result.mismatches)


def test_a_variant_run_against_a_different_receptor_gets_no_lift():
    result = Lmod.compute(_row(construct="VHL_VCB", e3_gene="VHL"), _row())
    assert result.lift is None
    assert {m["field"] for m in result.mismatches} >= {"construct", "e3_gene"}


def test_too_few_seeds_blocks_the_subtraction():
    """delta_iptm is built from minima over seeds, and a minimum over two
    samples is not the same statistic as a minimum over five."""
    result = Lmod.compute(_row(seeds_ternary=1), _row())
    assert result.lift is None
    assert any("seeds_ternary" in m["field"] for m in result.mismatches)


def test_a_variant_without_a_scored_parent_is_refused():
    result = Lmod.compute(_row(delta_iptm=0.5), _row(delta_iptm=None))
    assert result.lift is None
    assert "parent" in result.status


def test_the_scan_profile_ranks_positions_and_keeps_the_unscored_ones():
    lifts = [
        Lmod.compute(_row(delta_iptm=0.30 + d, substitution=f"{PARENT[i]}{i+1}A"),
                     _row(delta_iptm=0.30))
        for i, d in ((0, -0.20), (6, -0.05), (9, +0.10))
    ]
    profile = Lmod.scan_profile(lifts, PARENT)

    assert profile["of"] == len(PARENT)
    assert profile["scored"] == 3
    assert profile["most_sensitive"]["position"] == 1
    assert profile["least_sensitive"]["position"] == 10
    # Untested positions stay visible rather than vanishing from the chart.
    assert sum(1 for p in profile["positions"] if p["status"] == "not_scored") == 12
