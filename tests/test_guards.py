"""Guards that only fire on data no campaign has produced yet.

A second mutation sweep found five guards whose removal the whole suite
ignored. All five protect against conditions the finished campaigns never
hit, which is why they were never exercised, and three of them turn a
failure into a plausible number rather than an error. A 2,360-job run with
a fallback ladder designed to let individual items fail is exactly where
such conditions arrive.

The other two are left untested on purpose and said so here: an empty
radii table in score/lysine.py and a sequence shorter than the tile length
in curate/peptides.py both produce an obvious absence rather than a
confident wrong figure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------------- #
# A ternary arm with no ligand is the binary arm wearing a different label
# --------------------------------------------------------------------------- #

def test_no_ternary_job_is_emitted_without_a_ligand():
    """Delta-ipTM would then be ternary minus binary over two runs that
    differ only by seed: a number near zero, produced by construction and
    indistinguishable from a real measurement of no glue dependence.

    Reachable whenever ligand resolution fails: no CCD match and no
    PROTAC-DB entry leaves `ligand` as None.
    """
    from nobble.curate import constructs as C
    from nobble.curate import manifest as M
    from nobble.curate import peptides as P

    peptide = P.Peptide(
        peptide_id="pep1", sequence="A" * 15, source="benchmark",
        label="degraded", accession="P15170", gene="GSPT1",
        start_res=1, end_res=15,
    )
    construct = C.CONSTRUCTS["CRBN_CULT"]

    without = M.expand_pair("p1", "benchmark", construct, peptide, None)
    assert without, "no jobs at all were emitted"
    assert not [job for job in without if job.complex_type == "ternary"], (
        "a ternary job was emitted with no ligand, so its arm is identical "
        "to the binary one"
    )
    assert all(job.complex_type == "binary" for job in without)


def test_a_pair_with_a_ligand_still_gets_both_arms():
    """The opposite case, so the guard cannot be satisfied by emitting
    nothing."""
    from nobble.curate import constructs as C
    from nobble.curate import ligands as L
    from nobble.curate import manifest as M
    from nobble.curate import peptides as P

    peptide = P.Peptide(
        peptide_id="pep1", sequence="A" * 15, source="benchmark",
        label="degraded", accession="P15170", gene="GSPT1",
        start_res=1, end_res=15,
    )
    try:
        ligand = L.by_ccd("85C", modality="glue")
    except Exception:                       # noqa: BLE001
        pytest.skip("BINMAN ligand store not readable here")

    jobs = M.expand_pair("p1", "benchmark", C.CONSTRUCTS["CRBN_CULT"],
                         peptide, ligand)
    kinds = {job.complex_type for job in jobs}
    assert kinds == {"binary", "ternary"}


# --------------------------------------------------------------------------- #
# An RMSD over mismatched atom sets
# --------------------------------------------------------------------------- #

class _Point:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


def test_an_rmsd_over_mismatched_atom_sets_is_refused():
    """Without the length check, zip truncates to the shorter list and the
    RMSD is computed over a prefix: a confident number against the wrong
    residues, which is the failure this module's own docstring warns about.

    Reachable because the predicted peptide and the deposited chain are
    matched across two numbering frames, and a frame that resolves
    partially yields fewer matched atoms on one side.
    """
    from nobble.score import poses

    moving = [_Point(0, 0, 0), _Point(1, 0, 0), _Point(2, 0, 0)]
    fixed = [_Point(0, 0, 0), _Point(1, 0, 0)]

    assert poses._rmsd(moving, fixed, None) is None, (
        "an RMSD was returned over atom sets of different sizes"
    )
    assert poses._rmsd([], [], None) is None
    # Equal lengths still measure, so the guard is not simply refusing
    # everything.
    assert poses._rmsd(moving, list(moving), None) == 0.0


# --------------------------------------------------------------------------- #
# A substitution outside the sequence
# --------------------------------------------------------------------------- #

def test_a_variant_outside_the_sequence_is_refused():
    """A position past the end would produce a label like K99A against a
    15-mer: a variant id that no residue backs, which would then rank in
    the scan profile like any other.

    saturate() raises rather than returning a status, which is the right
    choice here: positions come from the alanine scan's own output, so an
    out-of-range one is a bug upstream rather than a datum to record.
    """
    from nobble.design import variants

    sequence = "A" * 15
    for position in (0, 16, 99, -1):
        with pytest.raises(ValueError, match="outside the peptide"):
            variants.saturate("pep1", sequence, [position])

    # In range, it produces one variant per alternative residue.
    inside = variants.saturate("pep1", sequence, [7])
    assert inside, "a valid position produced no variants"
    assert all(v.position == 7 for v in inside)
    assert all(v.substitution[-1] != "A" for v in inside), (
        "a self-substitution was emitted, whose two runs differ only by seed"
    )
