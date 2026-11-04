"""An RMSD is only a measurement if it compares the right residues.

`recovery_against_crystal` maps a predicted window onto a deposited chain by
residue number, through two frames resolved independently: the construct's
position to canonical, and canonical to the deposition. Its docstring has
always said that "getting this wrong produces a confident RMSD against the
wrong residues", and nothing checked it.

The failure is invisible by construction. The receptor still superposes, the
atom count still looks right, and ten seeds still agree with each other to
within an angstrom, because the error is in the reference rather than in the
prediction. Pose recovery is the layer that decides whether the panel's
positive controls work at all, so a confident wrong number there is the
expensive kind.

The window's residues are now compared by identity and the RMSD is withheld
when too few agree. The floor distinguishes misalignment from sequence
variation: measured across all seven benchmark depositions, six are
identical and CDK12 is 293 of 294, a single K to R where 6TD3's construct
differs from UniProt Q9NYV4. Exact equality refused that pair's 294-residue,
0.96 angstrom-anchored measurement outright, which is why the floor exists
(F103).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.score import poses  # noqa: E402
from nobble.validate.layers import RECOVERY_TARGETS  # noqa: E402


def _jobs(campaign_name: str) -> dict[str, dict]:
    campaign = ROOT / "campaigns" / campaign_name
    results = campaign / "results.jsonl"
    if not results.exists():
        return {}
    found: dict[str, dict] = {}
    for line in results.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (row.get("complex_type") != "ternary" or row.get("status") != "done"
                or not row.get("structure")):
            continue
        for pair in RECOVERY_TARGETS:
            if row.get("pair_id", "").split("_")[1:3] == pair.split("_")[1:3]:
                found.setdefault(pair, row)
    return found


def test_the_floor_comes_from_config():
    expected = float(paths.thresholds()["scoring"]["recovery_identity_floor"])
    assert poses.IDENTITY_FLOOR == expected
    assert 0.5 < poses.IDENTITY_FLOOR < 1.0, (
        "a floor of 1.0 refuses sequence variation and a low one accepts "
        "misalignment"
    )


@pytest.mark.parametrize("campaign", ["benchmark_20261103T192126Z",
                                      "corrected_20261103T214331Z"])
def test_every_benchmark_target_aligns_to_its_own_residues(campaign):
    """The measurement that nothing had made. All seven depositions, both
    construct generations, including GSPT1 whose frame is 138 residues away
    from canonical."""
    jobs = _jobs(campaign)
    if not jobs:
        pytest.skip(f"{campaign} has no completed ternary results")

    for pair, job in sorted(jobs.items()):
        target = RECOVERY_TARGETS[pair]
        out = poses.recovery_against_crystal(
            job, target["pdb_id"], target["substrate_chain"],
            target["substrate_acc"], target["receptor_chain"],
            target["receptor_acc"],
        )
        assert out.peptide_identity is not None, (pair, out.notes)
        assert out.peptide_identity >= poses.IDENTITY_FLOOR, (
            f"{pair} in {campaign}: identity {out.peptide_identity}, "
            f"{out.peptide_predicted_sequence[:40]} against "
            f"{out.peptide_deposited_sequence[:40]}"
        )
        assert out.rmsd is not None, (pair, out.notes)
        assert out.atoms_compared > 0


def test_a_single_substitution_does_not_discard_the_measurement():
    """CDK12 is the live case: 6TD3 chain B carries an R where Q9NYV4 has a
    K, at one position out of 294. The RMSD is reported and the difference is
    said rather than swallowed."""
    jobs = _jobs("corrected_20261103T214331Z")
    job = jobs.get("bench07_CDK12_DDB1")
    if job is None:
        pytest.skip("the corrected CDK12 pair has not run")
    target = RECOVERY_TARGETS["bench07_CDK12_DDB1"]
    out = poses.recovery_against_crystal(
        job, target["pdb_id"], target["substrate_chain"],
        target["substrate_acc"], target["receptor_chain"], target["receptor_acc"],
    )
    assert out.rmsd is not None, out.notes
    assert out.peptide_identity is not None and out.peptide_identity < 1.0
    assert out.peptide_identity >= poses.IDENTITY_FLOOR
    assert any("sequence variation" in note for note in out.notes), out.notes


def test_a_misaligned_frame_is_refused(monkeypatch):
    """The control. Shift the substrate frame by fifty residues, which is
    what a wrongly resolved frame does, and the RMSD must be withheld rather
    than reported.

    Without this the shifted mapping returns a number: the receptor anchor is
    untouched, so it superposes exactly as well as before.
    """
    jobs = _jobs("benchmark_20261103T192126Z") or _jobs("corrected_20261103T214331Z")
    if not jobs:
        pytest.skip("no completed ternary results")
    pair, job = sorted(jobs.items())[0]
    target = RECOVERY_TARGETS[pair]

    from nobble.curate import numbering

    honest = numbering.resolve_frame

    def shifted(pdb_id, chain, accession):
        frame = honest(pdb_id, chain, accession)
        if accession != target["substrate_acc"]:
            return frame

        class Shifted:
            def to_deposited(self, canonical):
                return frame.to_deposited(canonical + 50)

            def __getattr__(self, name):
                return getattr(frame, name)

        return Shifted()

    monkeypatch.setattr(numbering, "resolve_frame", shifted)
    out = poses.recovery_against_crystal(
        job, target["pdb_id"], target["substrate_chain"],
        target["substrate_acc"], target["receptor_chain"], target["receptor_acc"],
    )

    # It either matched the wrong residues, or matched nothing at all. Both
    # are refusals; what must not happen is an RMSD.
    assert out.rmsd is None, (
        f"a frame shifted by fifty residues still reported {out.rmsd} A "
        f"with identity {out.peptide_identity}"
    )
    assert out.notes, "refused without saying why"
    assert any("frame mapping" in note or "no overlapping" in note
               for note in out.notes), out.notes
    # The receptor anchor is unaffected, which is exactly why the peptide
    # identity had to be the thing that caught it.
    assert out.receptor_rmsd is not None and out.receptor_rmsd < 5.0


def test_an_unknown_residue_name_cannot_pass_the_identity_check():
    """"?" has to compare unequal to a real code, or a het group or an
    unparsed name would satisfy the check by being blank on both sides."""
    assert poses._one_letter("ALA") == "A"
    assert poses._one_letter("ZN") == "?"
    assert poses._one_letter("") == "?"
    assert poses._one_letter("HOH") == "?"
    assert poses._one_letter("ZN") != poses._one_letter("ALA")


def test_the_identity_is_recorded_on_the_result():
    """A check whose answer is not written down is a check nobody can audit,
    which is the shape of F79, F91 and F96."""
    from dataclasses import fields

    names = {field.name for field in fields(poses.RecoveryResult)}
    assert {"peptide_identity", "peptide_predicted_sequence",
            "peptide_deposited_sequence"} <= names
