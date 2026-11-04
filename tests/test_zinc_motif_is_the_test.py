"""The zinc decision's reason has to be true of the peptide it describes.

`requires_structural_zinc` ends its docstring with "The test is the complete
motif, not the source", and then tested the source: anything whose curated
class was not `zinc_finger` returned the flat reason "not a zinc-finger
domain" without the motif ever being counted.

For the one peptide it actually fired on that statement is false. The design
scan's parent is IKZF1's degron window, and IKZF1 is a zinc finger; the
window is a fragment of finger 2 whose histidines fall outside it. So the
campaign's own `campaign.json` recorded `"reason": "not a zinc-finger
domain"` against `PFQCNQCGASFTQKG`, which carries a CxxC pair. Right answer,
false reason, and the reason is the part a reader and a future maintainer
sees.

The motif is tested first now. No decision changes anywhere in the library,
which `test_the_reorder_changed_no_decisions` checks over all 5670 peptides
rather than asserting (F56).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import peptides as P  # noqa: E402


def _peptide(sequence, degron_class, cofactor=None, peptide_id="t"):
    return P.Peptide(
        peptide_id=peptide_id, sequence=sequence, source="test", label=None,
        accession=None, gene="TEST", start_res=None, end_res=None,
        degron_class=degron_class, e3_hint="CRBN", parent_peptide_id=None,
        cofactor=cofactor,
    )


def _library():
    rows = []
    for name in ("benchmark_peptides", "sievers_peptides", "library"):
        fn = getattr(P, name, None)
        if fn is not None:
            rows += list(fn())
    assert rows, "no peptides on this checkout"
    return rows


def test_the_ikzf1_window_declines_on_its_histidines():
    """The peptide that exposed it. The decision is unchanged; the reason
    now names what is actually missing."""
    peps = {p.peptide_id: p for p in P.benchmark_peptides()}
    ikzf1 = peps["benchmark_888fd2c63e"]
    assert ikzf1.gene == "IKZF1"
    assert ikzf1.sequence.count("C") == 2 and ikzf1.sequence.count("H") == 0

    decision = P.requires_structural_zinc(ikzf1)
    assert decision["required"] is False
    assert "incomplete coordination site" in decision["reason"]
    assert "0 His" in decision["reason"]


def test_no_reason_denies_a_zinc_finger_its_provenance():
    """The sentence that was false. A peptide from a zinc finger must never
    be told it is not one, whatever the decision about the ion."""
    for peptide in _library():
        reason = P.requires_structural_zinc(peptide)["reason"]
        assert "not a zinc-finger domain" not in reason, (
            f"{peptide.peptide_id} ({peptide.gene}) is still described as "
            f"not a zinc-finger domain: {reason}"
        )


def test_a_complete_site_in_a_domain_still_gets_the_ion():
    decision = P.requires_structural_zinc(
        _peptide("CPECGKHFSRKDHLTKH", "zinc_finger"))
    assert decision["required"] is True
    assert decision["ccd"] == P.STRUCTURAL_ZINC_CCD
    assert "complete C2H2" in decision["reason"]


def test_a_scramble_keeps_its_ion():
    """D-NOB-038's reasoning: a negative that fails for the wrong reason
    tells you nothing about the positive."""
    decision = P.requires_structural_zinc(
        _peptide("HCKFTDRSGKHCPLEH", "scramble_of_zinc_finger"))
    assert decision["required"] is True


def test_an_incomplete_site_in_a_domain_is_named_as_incomplete():
    decision = P.requires_structural_zinc(_peptide("CPECGKAFSRKD", "zinc_finger"))
    assert decision["required"] is False
    assert "incomplete coordination site (2 Cys, 0 His)" in decision["reason"]


def test_a_complete_site_submitted_as_a_tile_is_reported_not_dropped():
    """The branch the class-first order fell through in silence. It does not
    occur in the present library, so the test constructs it: a 15-mer that
    could coordinate an ion and is folded without one has to say so."""
    decision = P.requires_structural_zinc(
        _peptide("CPECGKHFSRKDHLT", "benchmark_ikzf1"))
    assert decision["required"] is False
    reason = decision["reason"]
    assert "complete coordination site" in reason
    assert "tile" in reason
    assert "benchmark_ikzf1" in reason


def test_an_explicit_cofactor_still_wins():
    """A design variant inherits its parent's decision, so an alanine scan
    of a coordinating cysteine does not silently drop the ion (D-NOB-038)."""
    explicit = {"required": True, "ccd": "ZN", "reason": "inherited"}
    decision = P.requires_structural_zinc(
        _peptide("AAAAAAAAAAA", "design", cofactor=explicit))
    assert decision == explicit


def test_the_library_holds_no_complete_site_outside_a_domain_class():
    """The premise of the reorder being decision-neutral. If a peptide like
    this is ever curated, the reorder's third branch reports it and this
    test is the notice that the case went from hypothetical to real."""
    offenders = [
        (p.peptide_id, p.degron_class)
        for p in _library()
        if p.cofactor is None
        and p.degron_class not in P.DOMAIN_COFACTOR_CLASSES
        and (p.sequence or "").count("C") >= 2
        and (p.sequence or "").count("H") >= 2
    ]
    assert not offenders, (
        "a complete coordination site is now curated outside the domain "
        f"classes: {offenders}. The decision is unchanged, but the reorder "
        "was justified as decision-neutral on this being empty"
    )


def test_the_reorder_changed_no_decisions():
    """The invariant, over the real library rather than fixtures. The class
    gate used to come first; reconstruct that order and confirm the ion and
    the CCD code agree for every peptide."""
    def class_first(peptide):
        if peptide.cofactor is not None:
            return dict(peptide.cofactor)
        if peptide.degron_class not in P.DOMAIN_COFACTOR_CLASSES:
            return {"required": False}
        sequence = peptide.sequence or ""
        if sequence.count("C") >= 2 and sequence.count("H") >= 2:
            return {"required": True, "ccd": P.STRUCTURAL_ZINC_CCD}
        return {"required": False}

    changed = []
    for peptide in _library():
        before, after = class_first(peptide), P.requires_structural_zinc(peptide)
        if (before.get("required"), before.get("ccd")) != (
                after.get("required"), after.get("ccd")):
            changed.append(peptide.peptide_id)
    assert not changed, f"the reorder moved {len(changed)} decisions: {changed[:5]}"
