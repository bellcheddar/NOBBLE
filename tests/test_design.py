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


# --- cofactor inheritance (D-NOB-038) ---------------------------------------

def _zf_parent() -> "object":
    from nobble.curate.peptides import Peptide
    return Peptide(
        peptide_id="zf_parent", sequence="YPCIPCGFSFKTKSNLYKHRKSHAH",
        source="sievers_zf", label="degraded", accession="X", gene="ZEP2",
        start_res=1, end_res=25, degron_class="zinc_finger",
    )


def test_scanning_a_zinc_finger_would_drop_the_ion_without_inheritance():
    """The trap, demonstrated before the fix is applied.

    An alanine scan mutates the coordinating cysteines. Inferring the
    cofactor from each variant's own sequence drops the zinc at exactly
    C3A and C6A, which are the positions the scan most wants to measure.
    """
    from nobble.curate.peptides import Peptide, requires_structural_zinc

    parent = _zf_parent()
    assert requires_structural_zinc(parent)["required"] is True

    dropped = []
    for variant in V.generate(parent.peptide_id, parent.sequence)["variants"]:
        naive = Peptide(
            peptide_id=variant["variant_id"], sequence=variant["sequence"],
            source="design", label=None, accession="X", gene="ZEP2",
            start_res=1, end_res=25, degron_class="zinc_finger",
        )
        if not requires_structural_zinc(naive)["required"]:
            dropped.append(variant["substitution"])

    assert dropped, "the trap should exist without inheritance"
    assert all(s[0] in "CH" for s in dropped), dropped


def test_an_inherited_cofactor_keeps_every_variant_symmetric_with_its_parent():
    from nobble.curate.peptides import Peptide, requires_structural_zinc

    parent = _zf_parent()
    inherited = requires_structural_zinc(parent)

    for variant in V.generate(parent.peptide_id, parent.sequence)["variants"]:
        child = Peptide(
            peptide_id=variant["variant_id"], sequence=variant["sequence"],
            source="design", label=None, accession="X", gene="ZEP2",
            start_res=1, end_res=25, degron_class="zinc_finger",
            cofactor=dict(inherited),
        )
        assert requires_structural_zinc(child)["required"] is True, (
            f"{variant['substitution']} lost the ion its parent has"
        )


def test_an_explicit_no_cofactor_is_also_respected():
    """Inheritance has to carry "no zinc" as faithfully as "zinc", or a
    variant of a non-finger parent could acquire one."""
    from nobble.curate.peptides import Peptide, requires_structural_zinc

    child = Peptide(
        peptide_id="v", sequence="CCHHCCHHCCHH", source="design", label=None,
        accession=None, gene=None, start_res=None, end_res=None,
        degron_class="zinc_finger",
        cofactor={"required": False, "reason": "parent had none"},
    )
    assert requires_structural_zinc(child)["required"] is False


def test_design_variants_carry_no_experimental_label():
    """A design is a question. Labelling it would smuggle an answer into
    the set the weight fitter reads as ground truth."""
    from nobble.design import assemble as A

    manifest = A.build_manifest("benchmark_888fd2c63e")
    if manifest.get("status"):
        pytest.skip(manifest["status"])
    variants = [p for p in manifest["pairs"] if p["role"] == "variant"]
    assert variants
    assert all(p["peptide_label"] is None for p in variants)
    parent = next(p for p in manifest["pairs"] if p["role"] == "parent")
    assert parent["peptide_label"] == "degraded"


def test_design_linkage_survives_scoring(tmp_path):
    """A variant that cannot name its parent cannot be paired with one.

    PairMetrics carries parent_peptide_id, substitution, role and the
    sequence because lift is computed from scores.jsonl. Without them
    from_scores finds zero variants and reports that quietly, after the
    campaign has already spent its compute.
    """
    import json
    from nobble.score import metrics

    def _job(job_id, pair_id, complex_type, iptm, **extra):
        row = {
            "job_id": job_id, "pair_id": pair_id, "seed": 1,
            "construct": "CRBN_CULT", "e3_gene": "CRBN",
            "peptide_id": "design_abc", "peptide_sequence": "PFQANQCGASFTQKG",
            "complex_type": complex_type, "conditioning": "unconstrained",
            "tier": "design", "status": "done",
            "parent_peptide_id": "benchmark_888fd2c63e",
            "substitution": "C4A", "role": "variant",
            "confidence": {"pair_chains_iptm": {"0": {"1": iptm}, "1": {"0": iptm}},
                            "iptm": iptm},
        }
        row.update(extra)
        return row

    results = tmp_path / "results.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in [
        _job("j1", "design_C4A", "binary", 0.60),
        _job("j2", "design_C4A", "ternary", 0.80),
    ]))

    pairs = metrics.aggregate(results)
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.parent_peptide_id == "benchmark_888fd2c63e"
    assert pair.substitution == "C4A"
    assert pair.role == "variant"
    assert pair.peptide_sequence == "PFQANQCGASFTQKG"
    # And the linkage reaches the serialised row lift reads.
    assert pair.to_dict()["parent_peptide_id"] == "benchmark_888fd2c63e"


def test_a_substitution_for_itself_is_refused():
    """A no-op variant's two runs differ only by seed, so the difference
    between them is the noise floor. Nothing downstream distinguishes that
    from a real effect: it sorts into the ranking like any other number and
    can come out on top, which is how it was found."""
    base = dict(construct="CRBN_CULT", e3_gene="CRBN", ligand_key="Y70",
                modality="glue", seeds_binary=5, seeds_ternary=5)
    result = Lmod.compute({**base, "delta_iptm": 0.1, "substitution": "A9A"},
                          {**base, "delta_iptm": 0.3})
    assert result.lift is None
    assert "for itself" in result.status

    real = Lmod.compute({**base, "delta_iptm": 0.1, "substitution": "A9G"},
                        {**base, "delta_iptm": 0.3})
    assert real.lift == -0.2


def test_the_alanine_scan_never_emits_a_no_op():
    """The guard above is belt and braces: the generator already avoids
    this by scanning an alanine to glycine."""
    for sequence in ("AAAA", "PFQCNQCGASFTQKG", "ACDEFGHIKLMNPQRSTVWY"):
        for variant in V.generate("p", sequence)["variants"]:
            assert variant["wild_type"] != variant["mutant"], variant["substitution"]


def test_unequal_seed_counts_between_variant_and_parent_block_the_lift():
    """Equal depth, not merely sufficient depth.

    delta_iptm is a difference of minima over seeds, and a minimum is not
    robust to sample count. A variant scored over four seeds against a
    parent scored over five has a lower minimum before any substitution is
    considered. Both normally match, because they come from one campaign
    with one seed tuple: they stop matching when a job fails, which is
    exactly when nobody is checking seed counts.
    """
    base = dict(construct="CRBN_CULT", e3_gene="CRBN", ligand_key="Y70",
                modality="glue", delta_iptm=0.3)
    result = Lmod.compute(
        {**base, "seeds_binary": 5, "seeds_ternary": 4, "substitution": "K7A"},
        {**base, "seeds_binary": 5, "seeds_ternary": 5},
    )
    assert result.lift is None
    assert any(m["field"] == "seeds_ternary" for m in result.mismatches)

    matched = Lmod.compute(
        {**base, "seeds_binary": 5, "seeds_ternary": 5, "substitution": "K7A"},
        {**base, "seeds_binary": 5, "seeds_ternary": 5},
    )
    assert matched.status == "computed"


def test_the_scan_profile_uses_the_recorded_position_not_the_label():
    """Re-deriving the position from the label works for K7A and stops
    working for anything else. The generator already records it, so a scan
    should not depend on a string parse that can silently drop a position
    and leave a gap in the chart."""
    base = dict(construct="CRBN_CULT", e3_gene="CRBN", ligand_key="Y70",
                modality="glue", seeds_binary=5, seeds_ternary=5)
    # A label the parse cannot read, with the position recorded alongside.
    odd = Lmod.compute(
        {**base, "delta_iptm": 0.20, "substitution": "p.Lys7Ala", "position": 7},
        {**base, "delta_iptm": 0.30})
    assert odd.status == "computed"
    assert odd.position == 7

    profile = Lmod.scan_profile([odd], "PFQCNQCGASFTQKG")
    assert profile["scored"] == 1
    assert profile["most_sensitive"]["position"] == 7


def test_a_lift_with_neither_position_nor_a_readable_label_is_skipped():
    base = dict(construct="CRBN_CULT", e3_gene="CRBN", ligand_key="Y70",
                modality="glue", seeds_binary=5, seeds_ternary=5)
    unreadable = Lmod.compute(
        {**base, "delta_iptm": 0.2, "substitution": "mutant"},
        {**base, "delta_iptm": 0.3})
    profile = Lmod.scan_profile([unreadable], "PFQCNQCGASFTQKG")
    assert profile["scored"] == 0


def test_the_unscored_fallback_never_picks_a_bivalent_degrader():
    """Every benchmark degron is a 15-mer, so "shortest" was an arbitrary
    tiebreak and it landed on BRD4/VHL: a PROTAC pair, in an arm about glue
    dependence. The fallback fires whenever nothing is scored, which
    includes the case where the main campaign failed to score, so it has to
    be right on its own rather than relying on scores existing."""
    from nobble.design.report import _default_parent

    parents = [
        {"peptide_id": "p_protac", "gene": "BRD4", "sequence": "A" * 15,
         "length": 15, "source": "benchmark", "e3_hint": "VHL",
         "label": "degraded", "modality": "protac"},
        {"peptide_id": "p_glue", "gene": "GSPT1", "sequence": "C" * 15,
         "length": 15, "source": "benchmark", "e3_hint": "CRBN",
         "label": "degraded", "modality": "glue"},
    ]
    chosen = _default_parent(parents)
    assert chosen["modality"] == "glue", chosen["gene"]
    assert "not been ranked" in chosen["chosen_because"]


def test_sievers_parents_are_glues():
    from nobble.design.report import _modality_of
    assert _modality_of({"source": "sievers_zf", "gene": "ZN346"}) == "glue"
