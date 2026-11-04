"""A structural ion is a ligand to PLIP, and it is not the glue.

PLIP perceives every het group as a ligand, so a Sievers finger's
interactions CSV carries Y70:D:1 beside ZN:C:1. The zinc's rows are metal
coordination to the receptor: the finger holding itself together. Counting
them as glue contacts would put the substrate's own fold into a
fingerprint that measures the glue's grip on the degron, on all 120 pairs
in the arm.

Measured on a real prediction: before the filter, 10 receptor contacts and
an interaction set including "metal complexes": 4. After, 6 receptor
contacts and the glue's own hydrophobic and hydrogen-bond rows alone.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _zinc_structure() -> Path | None:
    hits = sorted((ROOT / "campaigns" / "smoke_sievers").rglob("*ternary*/**/*.cif"))
    return hits[0] if hits else None


def test_a_structural_ion_does_not_enter_the_glue_fingerprint():
    from nobble.score.plip import CIF2PLIP, fingerprint

    structure = _zinc_structure()
    if structure is None:
        pytest.skip("no zinc-bearing smoke structure")
    if not CIF2PLIP.exists():
        pytest.skip("cif2plip not available")

    import tempfile
    with tempfile.TemporaryDirectory() as work:
        result = fingerprint(
            {"job_id": "zinc", "structure": str(structure.resolve()),
             "complex_type": "ternary"},
            workdir=Path(work),
        ).to_dict()

    if not result["status"].startswith("ok"):
        pytest.skip(f"plip did not run: {result['status'][:60]}")

    types = result.get("interaction_types") or {}
    assert "metal complexes" not in types, types
    assert any("ZN" in note and "excluded" in note
               for note in result.get("notes") or []), result.get("notes")


def test_an_unparsed_chain_map_refuses_rather_than_guessing():
    """There is no fallback chain map any more, and that is the fix.

    The A/P/L to A/B/C ordering is correct for three chains. A job carrying
    a structural ion has four, A, P, Z and L, so the ligand is D and the
    fallback handed the ligand slot to the zinc: every "glue to degron"
    contact would have been the ion's coordination to the receptor.

    It used to apply that map, append two notes saying the result was
    unverified, and then set status "ok" regardless. Nothing downstream
    reads `notes`, so `run.py` recorded the match as a measurement. The
    guess is gone: an unparsed map is a refusal, which costs one component
    on one pair instead of the component's meaning across the Sievers arm
    (F81).
    """
    source = (ROOT / "nobble" / "score" / "plip.py").read_text()
    assert '"A": "A", "P": "B", "L": "C"' not in source, (
        "the guessed chain map is back"
    )
    assert "chain map not parsed from cif2plip output" in source


def test_the_refusal_is_a_status_and_not_a_note():
    """The wiring, not the string (F40).

    `run.py` branches on `finger.status != "ok"` and knows nothing about
    `notes`. The old code put its warning in notes and left the status
    "ok", so the two disagreed and the reader of the two was the one that
    did not see the warning. This checks the refusal is on the field that
    is actually read.
    """
    from nobble.score import plip

    refusal = plip.Fingerprint(
        job_id="j",
        status=("failed: chain map not parsed from cif2plip output. The "
                "A/P/L fallback is correct for three chains"))
    assert refusal.status != "ok"

    scorer = (ROOT / "nobble" / "score" / "run.py").read_text()
    assert 'if finger.status != "ok":' in scorer, (
        "run.py no longer branches on the status, so where the refusal "
        "lives would need rechecking"
    )
    assert "finger.notes" not in scorer, (
        "run.py reads notes now, which would change where a refusal belongs"
    )


def test_the_zinc_stays_out_of_every_geometry_consumer():
    """The ion was added so the finger folds. Each downstream consumer had
    to be checked separately, because each classifies chains itself and
    "not receptor, not peptide, not ligand" is only correct if that branch
    exists. PLIP was the one that did not have it (F14).

    Verified against a real prediction rather than read off the source:
    the bridge metric is spec 4.1's primary signal, so a zinc quietly
    entering it would move the headline number on 120 pairs.
    """
    from nobble.score import geometry, poses

    structure = _zinc_structure()
    if structure is None:
        pytest.skip("no zinc-bearing smoke structure")

    job = {"job_id": "zinc", "structure": str(structure.resolve()),
           "construct": "CRBN_CULT", "complex_type": "ternary"}

    contacts = geometry.contact_map(job)
    assert contacts["status"] == "ok"
    labels = contacts["receptor_residues"] + contacts["peptide_residues"]
    assert not any("ZN" in str(label) for label in labels), labels

    docking = poses.docking_check(job).to_dict()
    assert docking["docked"] is True
    # 197 peptide atoms for a 26-mer: the single zinc atom is not among them.
    assert docking["peptide_atoms"] > 100

    bridge = geometry.score_structure(job).to_dict()
    assert bridge.get("reject_reason") is None
    assert bridge["dsasa_total"] > 0
    assert 0 <= bridge["bridge_percentile"] <= 100
