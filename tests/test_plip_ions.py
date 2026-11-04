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


def test_the_fallback_chain_map_announces_that_it_may_be_wrong():
    """The A/P/L fallback assumes three chains. A job carrying a structural
    ion has four, so L is D and the fallback would hand the ligand slot to
    the zinc. It fires only when the parse fails, so it must say so."""
    source = (ROOT / "nobble" / "score" / "plip.py").read_text()
    assert '"A": "A", "P": "B", "L": "C"' in source
    assert "unverified" in source, (
        "the fallback chain map must flag itself when it cannot be trusted"
    )
