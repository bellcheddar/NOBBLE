"""Each manifest error, raised on its own.

`manifest.validate` collects `ValidationIssue`s and the manifest reports
`errors` as a count of the error-severity ones. `assemble_campaign` refuses to
emit when that count is non-zero, so the count is the gate, and a count is the
weakest possible thing to assert against: with any one check removed, the
others still raise whatever the fixture in front of them raises.

Mutated one at a time, all three error checks were caught by nothing: the
token cap, the absent PTM residue, and a ternary job with no ligand. The two
warnings have their codes asserted elsewhere; the three that block the gate
did not (F275).

This is the third gate with the shape, after the atlas build's refusals (F273)
and preflight's checks (F274). Each is tested here by its code rather than by
the error count, and a clean job must raise nothing, because a fixture that
errors for an unrelated reason satisfies any assertion about a count.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths
from nobble.curate import manifest as M


def _job(**overrides) -> M.Job:
    """A ternary job that validates clean."""
    base = {
        "job_id": "j1", "pair_id": "p1", "tier": "benchmark",
        "construct": "CRBN_CULT", "e3_gene": "CRBN", "peptide_id": "pep1",
        "peptide_sequence": "PFQCNQCGASFTQKG", "peptide_gene": "IKZF1",
        "peptide_label": "degraded", "peptide_accession": "Q13422",
        "peptide_start_res": 1, "peptide_end_res": 15,
        "ligand_key": "Y70", "ligand_encoding": "ccd", "modality": "glue",
        "complex_type": "ternary", "conditioning": "unconstrained",
        "seed": 1, "tokens": 150, "affinity_available": True,
        "required_modification": None,
    }
    base.update(overrides)
    return M.Job(**base)


def _codes(jobs: list[M.Job]) -> list[str]:
    return [issue.code for issue in M.validate(jobs)]


def _errors(jobs: list[M.Job]) -> list[str]:
    return [issue.code for issue in M.validate(jobs)
            if issue.severity == "error"]


def test_a_clean_job_raises_nothing():
    """Without this, every test below could pass on an unrelated issue."""
    assert _codes([_job()]) == [], _codes([_job()])


def test_the_token_cap_fires():
    cap = int(paths.thresholds()["manifest"]["token_cap_tier1"])
    assert "token_cap_exceeded" in _errors(
        [_job(tokens=cap + 1, construct="NOT_A_DECLARED_CONSTRUCT")])


def test_a_declared_exception_is_allowed_over_the_cap():
    """So the check above cannot pass by meaning 'large jobs are bad'."""
    from nobble.curate import constructs as C

    declared = sorted(C.declared_exceptions())
    if not declared:
        pytest.skip("no declared token-cap exceptions in config")
    cap = int(paths.thresholds()["manifest"]["token_cap_tier1"])
    assert "token_cap_exceeded" not in _errors(
        [_job(tokens=cap + 1, construct=declared[0])])


def test_a_required_modification_with_no_such_residue_fires():
    """Spec 2.3: a degron class that requires a PTM and carries none.

    F47 is the live instance of this going wrong in the other direction, a
    modification applied where it did not belong, so the check that the
    residue is even present is the one that has to work.
    """
    assert "ptm_residue_absent" in _errors([_job(
        peptide_sequence="AAAAAAAAAAAAAAA",
        required_modification={"residue": ["P"], "note": "hydroxyproline"})])


def test_a_required_modification_with_the_residue_present_does_not_fire():
    assert "ptm_residue_absent" not in _errors([_job(
        peptide_sequence="PFQCNQCGASFTQKG",
        required_modification={"residue": ["P"], "note": "hydroxyproline"})])


def test_a_ternary_job_with_no_ligand_fires():
    """The manifest-level sibling of F262, and not the same check.

    This catches a ternary job whose record names no ligand at all. F262 was a
    ternary job whose record named one and whose YAML had no ligand block, so
    this check passed it and `tools/preflight.py` is where that is caught.
    Both are needed and neither subsumes the other.
    """
    assert "ternary_without_ligand" in _errors(
        [_job(ligand_key=None, ligand_encoding=None)])


def test_a_binary_job_with_no_ligand_does_not_fire():
    """A binary arm is supposed to have no ligand."""
    assert "ternary_without_ligand" not in _errors(
        [_job(complex_type="binary", ligand_key=None, ligand_encoding=None)])


def test_the_warnings_stay_warnings():
    """They must not block the gate, and the gate is a count of errors.

    A warning promoted to an error would stop every SMILES-encoded degrader
    in the campaign, which is 110 of Tier B's ternary jobs.
    """
    issues = M.validate([_job(ligand_encoding="smiles",
                              affinity_available=False)])
    by_code = {issue.code: issue.severity for issue in issues}
    assert by_code.get("smiles_fallback") == "warning", by_code
    assert by_code.get("affinity_unavailable") == "warning", by_code
    assert not [code for code, severity in by_code.items()
                if severity == "error"], by_code
