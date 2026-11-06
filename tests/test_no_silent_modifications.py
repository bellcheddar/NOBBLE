"""A `modifications` block in a Boltz YAML changes nothing, silently (F217).

bench02_BRD4_VHL carried `modifications: [{position: 1, ccd: HYP}]` on its
peptide chain for the whole campaign. F47 caught that the hydroxyproline was
wrong and `tools/rerun_pair.py` corrected it. All fifteen jobs then re-ran
against the corrected input and returned ipTM bit-identical to sixteen
significant figures, which for a deterministic model means the input tensor
never differed: the block was dropped somewhere between the YAML and the
featuriser.

Whether Boltz's schema wants it elsewhere or drops it outright is unresolved
and needs a GPU to settle. Either way, emitting a declaration that has no
effect is the defect, because it reads as chemistry that was modelled. The
campaign's peptide chemistry has to live in the sequence or in a CCD ligand,
where it demonstrably reaches the model.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _campaign_yamls():
    for campaign in sorted((ROOT / "campaigns").glob("*/yaml")):
        yield from sorted(campaign.glob("*.yaml"))


def test_no_emitted_yaml_declares_a_modification():
    """The .bak files are deliberately not checked: they are the record of
    what was wrong, and rewriting history is not the point of a guard."""
    offenders = [path for path in _campaign_yamls()
                 if "modifications:" in path.read_text()]
    if not offenders and not list(_campaign_yamls()):
        pytest.skip("no campaign YAML on this checkout")
    assert not offenders, (
        "YAML declaring a residue modification that Boltz does not apply, so "
        "the chemistry is in the file and not in the model (F217): "
        f"{[str(p.relative_to(ROOT)) for p in offenders[:5]]}. Express it in "
        "the sequence or as a CCD ligand instead."
    )


def test_the_manifest_refuses_a_peptide_whose_ptm_cannot_be_delivered():
    """Caught where a PTM requirement is already taken seriously.

    `manifest.py` has validated PTM completeness since spec 2.3: a degron
    class requiring a modification whose residue is absent is an error. The
    residue being present was treated as sufficient, and it is not, because
    the block that would modify it does nothing. So the same check now also
    refuses a requirement that cannot be delivered at all.

    An error rather than a warning: a phosphodegron folded without its
    phosphate is a different molecule, and a campaign that assembles past
    that scores the parent as the degron.
    """
    from nobble.curate import manifest

    source = Path(manifest.__file__).read_text()
    assert "ptm_not_deliverable" in source, (
        "the manifest validator does not refuse an undeliverable PTM (F217)"
    )
    marker = source.index("ptm_not_deliverable")
    assert source.index('"error"', marker - 200, marker) > 0, (
        "an undeliverable PTM is not an error"
    )


def test_the_assembler_still_computes_the_requirement():
    """The spec's computation stays put.

    Deleting `peptide_modifications` would lose spec 2.3's rule that every
    eligible residue is modified, not one of them, and that rule is correct
    and will be needed by whatever expresses the chemistry in a way that
    reaches the model. What is wrong is relying on its output, not deriving
    it.
    """
    from nobble.execute import yaml_gen

    assert hasattr(yaml_gen, "peptide_modifications")
    # Spec 2.3's rule, stated in the docstring and worth keeping: every
    # eligible residue is modified, because a DSGxxS motif has two serines
    # and phosphorylating one of them is not the degron.
    class Peptide:
        sequence = "ADSGYFS"
        required_modification = {"residue": "ST", "ccd": "SEP/TPO",
                                 "note": "phospho-serine"}

    resolved = yaml_gen.peptide_modifications(Peptide())
    assert [item["position"] for item in resolved] == [3, 7], resolved
    assert {item["ccd"] for item in resolved} == {"SEP"}, resolved
