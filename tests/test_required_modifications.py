"""Spec 2.3 keys its modification table on the degron class, not the E3.

    | Degron class      | Modification   | CCD |
    | VHL / HIF-1alpha  | hydroxyproline | HYP |
    ...
    Any peptide whose degron class requires a modification and which is
    submitted without one is a manifest error, not a low-scoring result.

The rule keyed on the E3 as well, matching any peptide whose `e3_hint`
contained VHL, BTRC or FBXW7. That is a different rule. VHL reads HIF-1alpha
through a hydroxylated proline, and a PROTAC supplies that hydroxyproline
from its own VHL ligand: MZ1 carries VH032, whose (2S,4R)-4-hydroxyproline
occupies the pocket. The substrate contributes none, and BRD4 Pro379 is not
a hydroxylation site.

So every BRD4/VHL job went to Boltz with a hydroxylated Pro379, a residue
that does not exist in biology, and the rule never once fired on the
HIF-like class it was written for, because this library contains none (F47).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import peptides as P  # noqa: E402


def _peptide(sequence, degron_class, e3_hint, peptide_id="p"):
    return P.Peptide(
        peptide_id=peptide_id, sequence=sequence, source="benchmark",
        label="degraded", accession=None, gene="G", start_res=None,
        end_res=None, degron_class=degron_class, e3_hint=e3_hint,
    )


def _annotate(peptide):
    P.annotate_required_modifications([peptide])
    return peptide


def test_a_hif_like_degron_requires_hydroxyproline():
    """The case the table was written for, and the one it never saw."""
    peptide = _annotate(_peptide("DLDLEMLAPYIPMDDDFQL", "hif1a_cterm", "VHL"))
    assert peptide.required_modification == P.REQUIRED_MODIFICATIONS["vhl_hif1a"]
    assert peptide.required_modification["ccd"] == "HYP"


def test_a_protac_recruited_substrate_requires_nothing():
    """BRD4 on VHL, the live case. MZ1's VH032 carries the hydroxyproline;
    BRD4 Pro379 is not a hydroxylation site."""
    peptide = _annotate(_peptide("PVDVEALGLHDYCDI", "benchmark_brd4", "VHL"))
    assert peptide.required_modification is None, peptide.required_modification


def test_declining_a_modification_says_why():
    """Spec 2.3 treats a missing modification as a manifest error, so
    "deliberately none" has to be distinguishable from "forgotten"."""
    peptide = _annotate(_peptide("PVDVEALGLHDYCDI", "benchmark_brd4", "VHL"))
    note = next((n for n in peptide.notes if "no required modification" in n), None)
    assert note, peptide.notes
    assert "benchmark_brd4" in note
    assert "VHL" in note


def test_the_other_two_classes_still_resolve():
    phospho = _annotate(_peptide("LDSGLGSMK", "btrcp_dsgxxs", "BTRC"))
    assert phospho.required_modification["ccd"] == "SEP"

    cpd = _annotate(_peptide("LPSGSGSPT", "fbxw7_cpd", "FBXW7"))
    assert cpd.required_modification["ccd"] == "SEP/TPO"


def test_a_class_that_requires_nothing_gets_nothing_and_says_nothing():
    """A zinc finger's E3 is CRBN, which reads an unmodified surface, so
    there is no decision to record and no note to clutter it with."""
    peptide = _annotate(_peptide("PFQCNQCGASFTQKG", "zinc_finger", "CRBN"))
    assert peptide.required_modification is None
    assert not [n for n in peptide.notes if "no required modification" in n]


def test_a_requiring_class_without_the_residue_gets_nothing():
    """A HIF-like window with no proline in it cannot carry a
    hydroxyproline, and the rule must not invent a position."""
    peptide = _annotate(_peptide("DLDLEMLAAYIAMDDDFQL", "hif1a_cterm", "VHL"))
    assert "P" not in peptide.sequence
    assert peptide.required_modification is None


def test_the_e3_alone_no_longer_decides():
    """The defect, stated as a test. Two peptides, same E3, same proline,
    different degron classes: only the one whose class requires it gets it."""
    native = _annotate(_peptide("DLDLEMLAPYIPMDDDFQL", "hif1a_cterm", "VHL"))
    recruited = _annotate(_peptide("PVDVEALGLHDYCDI", "benchmark_brd4", "VHL"))
    assert native.required_modification is not None
    assert recruited.required_modification is None


def test_the_frozen_library_carries_no_unjustified_modification():
    """The manifest is what the YAMLs are generated from, so fixing the rule
    without re-deriving the field would have changed nothing: the rule writes
    the manifest and the manifest writes the YAML."""
    import json

    path = ROOT / "data" / "manifests" / "library.jsonl"
    if not path.exists():
        import pytest
        pytest.skip("no library manifest on this checkout")

    rows = [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]
    wrong = []
    for row in rows:
        requirement = row.get("required_modification")
        if not requirement:
            continue
        degron_class = (row.get("degron_class") or "").lower()
        if not any(pattern in degron_class
                   for pattern, _key in P.MODIFICATION_CLASSES):
            wrong.append((row["peptide_id"], row.get("degron_class"),
                          requirement.get("ccd")))
    assert not wrong, (
        "peptide(s) in the frozen library carry a modification their degron "
        f"class does not require: {wrong}"
    )
