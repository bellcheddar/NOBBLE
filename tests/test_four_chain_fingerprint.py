"""The chain map on a four-chain job, asserted rather than implied.

A peptide carrying a structural zinc gives four chains. The YAML emits them
as A, P, Z, L with the ion as a ligand entry before the glue, which was read
from a real Sievers YAML rather than from the comment asserting it, and
cif2plip renumbers them in order so the ion becomes C and the glue D.

F81 removed a fallback that assumed three chains and would have handed the
ligand slot to the ion. The question that left open is whether the parse
works on four chains at all, because if it did not, the refusal would be
correct and the PLIP component absent for 120 of the campaign's 158 pairs.

It works, and `campaigns/smoke_sievers` already held the evidence: a real
prediction of `sv_neg_ZN346_d5063d` with chains A, P, Z, L. The map parses
as A to A, P to B, Z to C, L to D, and four of the ion's rows are excluded
naming D as the glue.

What is new here is the assertion about the map itself. `test_plip_ions.py`
covers the consequence, that the ion stays out of the fingerprint and out of
every geometry consumer. Neither of those fails if the map is right for the
wrong reason, so the mapping is pinned directly (F82).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _four_chain_prediction() -> Path | None:
    """A real prediction with receptor, peptide, structural ion and glue."""
    gemmi = pytest.importorskip("gemmi")

    for path in sorted((ROOT / "campaigns").rglob("*ternary*/**/*_model_0.cif")):
        try:
            structure = gemmi.read_structure(str(path))
            structure.setup_entities()
        except Exception:                       # noqa: BLE001
            continue
        if {"A", "P", "Z", "L"} <= {chain.name for chain in structure[0]}:
            return path
    return None


def _fingerprint():
    from nobble.score import plip

    structure = _four_chain_prediction()
    if structure is None:
        pytest.skip("no four-chain prediction on this checkout")
    if not plip.CIF2PLIP.exists():
        pytest.skip("cif2plip is not available on this host")
    job = {"job_id": "four_chain", "complex_type": "ternary",
           "structure": str(structure.resolve()), "e3_gene": "CRBN",
           "construct": "CRBN_CULT", "peptide_start_res": 1}
    return plip.fingerprint(job, workdir=Path(tempfile.mkdtemp()))


def test_a_real_four_chain_prediction_exists_to_test_against():
    """The premise, and the correction. This test was first written against
    a structure built by inserting a zinc into a three-chain benchmark
    ternary, because `zinc_probe`'s predictions are peptide-only and I
    stopped looking there. A real one was on disk the whole time."""
    assert _four_chain_prediction() is not None, (
        "no prediction carries receptor, peptide, ion and glue, so this "
        "file is testing a case that cannot occur"
    )


def test_the_chain_map_parses_for_four_chains():
    """The question F81 left open. With no fallback, a parse failure is a
    refusal, and the Sievers arm is 120 pairs."""
    result = _fingerprint()
    assert result.status == "ok", result.status
    mapping = next((note for note in result.notes
                    if note.startswith("chain map")), None)
    assert mapping, result.notes
    assert "'Z': 'C'" in mapping, mapping
    assert "'L': 'D'" in mapping, mapping


def test_the_glue_is_the_fourth_chain_not_the_third():
    """The removed fallback said L is C, which is the ion. Asserted on the
    mapping rather than on the exclusion it causes."""
    result = _fingerprint()
    assert any("chain D" in note for note in result.notes), result.notes


def test_the_ion_rows_are_excluded_and_the_rest_survive():
    """The exclusion must remove the ion's rows and nothing else: a
    fingerprint emptied by the filter would satisfy the first half of this
    and be useless."""
    result = _fingerprint()
    assert any("ZN" in note and "excluded" in note for note in result.notes), (
        result.notes
    )
    assert "metal complexes" not in (result.interaction_types or {})
    assert result.interaction_types, "the filter left nothing behind"
