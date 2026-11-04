"""The four-chain case the Sievers arm is about to produce.

Every prediction scored so far has three chains: receptor A, peptide P,
glue L. A peptide carrying a structural zinc has four, and the YAML emits
them as A, P, Z, L with the ion as a ligand entry before the glue. cif2plip
renumbers chains to single letters in order, so the glue becomes D and the
ion C.

Two things depend on that and neither had been exercised on a four-chain
input, because the Sievers arm had not run. F81 removed a fallback chain map
that assumed three chains and would have handed the ligand slot to the ion;
F14 added the exclusion that keeps the ion's own contacts out of the glue's
fingerprint.

Both work. Built by taking a real benchmark ternary and inserting a zinc as
chain Z between the peptide and the glue, which is where the assembler puts
it: the map parses as A to A, P to B, Z to C, L to D, and the ion's row is
excluded naming chain D as the glue. Verified 21 jobs before the first real
one (F82).
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _four_chain_structure(tmp_path: Path) -> Path:
    """A real ternary with a zinc inserted as chain Z, in assembler order."""
    gemmi = pytest.importorskip("gemmi")

    sources = sorted(glob.glob(
        str(ROOT / "campaigns" / "benchmark_*" / "outputs" / "**"
            / "*ternary*_model_0.cif"), recursive=True))
    chosen = None
    for path in sources:
        structure = gemmi.read_structure(path)
        structure.setup_entities()
        names = [chain.name for chain in structure[0]]
        if {"A", "P", "L"} <= set(names) and "Z" not in names:
            chosen = path
            break
    if chosen is None:
        pytest.skip("no three-chain benchmark ternary on this checkout")

    structure = gemmi.read_structure(chosen)
    structure.setup_entities()
    structure.remove_hydrogens()
    chains = {chain.name: chain for chain in structure[0]}
    anchor = chains["P"][0][0].pos

    zinc = gemmi.Chain("Z")
    residue = gemmi.Residue()
    residue.name = "ZN"
    residue.seqid = gemmi.SeqId(1, " ")
    atom = gemmi.Atom()
    atom.name = "ZN"
    atom.element = gemmi.Element("Zn")
    atom.pos = gemmi.Position(anchor.x + 2.2, anchor.y, anchor.z)
    atom.occ = 1.0
    atom.b_iso = 20.0
    residue.add_atom(atom)
    zinc.add_residue(residue)

    rebuilt = gemmi.Structure()
    rebuilt.cell = structure.cell
    rebuilt.spacegroup_hm = structure.spacegroup_hm
    model = gemmi.Model("1")
    # A, P, Z, L: the order the assembler emits, with the ion before the glue.
    model.add_chain(chains["A"])
    model.add_chain(chains["P"])
    model.add_chain(zinc)
    model.add_chain(chains["L"])
    rebuilt.add_model(model)
    rebuilt.setup_entities()

    out = tmp_path / "apzl.cif"
    rebuilt.make_mmcif_document().write_file(str(out))
    return out


def _fingerprint(tmp_path: Path):
    from nobble.score import plip

    if not plip.CIF2PLIP.exists():
        pytest.skip("cif2plip is not available on this host")
    structure = _four_chain_structure(tmp_path)
    job = {"job_id": "apzl_probe", "complex_type": "ternary",
           "structure": str(structure), "e3_gene": "CRBN",
           "construct": "CRBN_CULT", "peptide_start_res": 1}
    return plip.fingerprint(job, workdir=tmp_path / "plip")


def test_the_chain_map_parses_for_four_chains(tmp_path):
    """The question F81 left open. The fallback is gone, so a parse failure
    is now a refusal, and the Sievers arm is 120 pairs: if the parse did
    not work here, the PLIP component would be absent for all of them."""
    result = _fingerprint(tmp_path)
    assert result.status == "ok", result.status
    mapping = next((note for note in result.notes if note.startswith("chain map")), None)
    assert mapping, result.notes
    assert "'Z': 'C'" in mapping and "'L': 'D'" in mapping, mapping


def test_the_glue_is_identified_as_the_fourth_chain(tmp_path):
    """Not the third. The removed fallback said L is C, which is the ion."""
    result = _fingerprint(tmp_path)
    assert any("chain D" in note for note in result.notes), result.notes


def test_the_ion_contacts_are_excluded_from_the_glue_fingerprint(tmp_path):
    """F14's exclusion, on a four-chain input for the first time. A zinc
    row counted as a glue contact would move spec 4.1's primary signal on
    the arm the headline ROC is computed on."""
    result = _fingerprint(tmp_path)
    assert any("ZN" in note and "excluded" in note for note in result.notes), (
        result.notes
    )
    assert "metal complexes" not in (result.interaction_types or {})


def test_the_fingerprint_still_finds_real_contacts(tmp_path):
    """The exclusion must remove the ion's rows and nothing else: a
    fingerprint emptied by the filter would pass the test above and be
    useless."""
    result = _fingerprint(tmp_path)
    assert result.receptor_contacts, "no receptor contact survived the filter"
    assert result.interaction_types, result.interaction_types
