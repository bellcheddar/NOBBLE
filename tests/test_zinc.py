"""A C2H2 zinc finger needs its ion, and needs it in both arms.

The Sievers arm submits whole zinc fingers rather than tiles, precisely
because a zinc finger is a folding unit. The Zn(2+) ion is what makes it
one: a C2H2 finger with no zinc is not a domain missing an accessory, it is
a disordered 23-mer. All 120 peptides in the arm carry the complete motif.

The asymmetry case is the one that matters. Delta-ipTM is the ternary ipTM
minus the binary one, so a cofactor present in only the ternary arm would
fold the peptide differently between the two and the difference would report
"the glue changed the interface" for what was really "the peptide folded
this time".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate.peptides import Peptide, requires_structural_zinc


def _peptide(sequence: str, degron_class: str) -> Peptide:
    return Peptide(
        peptide_id="p", sequence=sequence, source="sievers_zf", label="degraded",
        accession="P0", gene="ZNFX", start_res=1, end_res=len(sequence),
        degron_class=degron_class,
    )


def test_a_complete_c2h2_finger_gets_a_zinc():
    result = requires_structural_zinc(
        _peptide("NQCCPICNMTFSSPVVAQSHYLGKTH", "zinc_finger")
    )
    assert result["required"] is True
    assert result["ccd"] == "ZN"


def test_a_scramble_of_a_zinc_finger_also_gets_one():
    """Its job is to differ from its positive in exactly one variable, the
    residue order. Withholding the ion would make it differ in two, and a
    negative that fails for the wrong reason says nothing about the positive."""
    result = requires_structural_zinc(
        _peptide("NHCPIHKFYKCHSRKKLTSGPAFSY", "scramble_of_zinc_finger")
    )
    assert result["required"] is True


def test_a_degron_fragment_with_no_coordination_site_gets_none():
    """IKZF1's benchmark window is a fragment of zinc finger 2 whose
    histidines fall outside it. There is no site to complete, and bench04
    scored the best Delta-ipTM in the panel without one."""
    result = requires_structural_zinc(_peptide("PFQCNQCGASFTQKG", "zinc_finger"))
    assert result["required"] is False
    assert "incomplete" in result["reason"]


def test_a_non_zinc_finger_never_gets_one():
    assert requires_structural_zinc(
        _peptide("CHCHCHCHCHCHCH", "degron")
    )["required"] is False


def test_the_zinc_is_present_in_both_arms_not_just_the_ternary():
    """The whole reason this is tested rather than eyeballed."""
    from nobble.curate import constructs as C, ligands as L, manifest as M
    from nobble.curate import library as LM
    from nobble.curate import peptides as P
    from nobble.execute import yaml_gen as Y

    lib = LM.load()
    assert lib is not None, "library manifest missing: run nobble.curate.library"
    rows = {r["peptide_id"]: r for r in lib["peptides"]}

    manifest = M.build_campaign_manifest(library=lib["peptides"])
    pair = next(p for p in manifest["pairs"] if p["tier"] == "sievers_zf")
    jobs = [j for j in manifest["jobs"] if j.pair_id == pair["pair_id"]]
    peptide = P.Peptide(**{k: v for k, v in rows[pair["peptide_id"]].items()
                           if k != "length"})
    ligand = L.by_ccd(pair["ligand"]["ccd"], modality="glue")

    def _ccds(complex_type: str) -> set:
        job = next(j for j in jobs if j.complex_type == complex_type)
        document = Y.build_yaml(job, peptide, ligand, None)
        return {
            entry["ligand"]["ccd"]
            for entry in document["sequences"] if "ligand" in entry
            and entry["ligand"].get("ccd")
        }

    assert "ZN" in _ccds("binary"), "the binary arm lost the structural zinc"
    assert "ZN" in _ccds("ternary")
    # And the glue is still only in the ternary arm.
    assert pair["ligand"]["ccd"] in _ccds("ternary")
    assert pair["ligand"]["ccd"] not in _ccds("binary")
