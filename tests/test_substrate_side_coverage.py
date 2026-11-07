"""How much of the deposited substrate-side burial each arm reproduces.

The totals can agree while the split does not, and the split is what a
representation changes: a 15-mer has less surface to bury than the folded
domain it was cut from, while the glue's seat in the E3 is not bounded by the
substrate's length. So the substrate-side ratio is the diagnostic, and these
assert it is computed as a ratio of measurements rather than as a verdict.

Fixtures rather than live campaigns, because the point of each test is a
case: an arm that reproduces the deposited burial, an arm that cannot, and an
arm that found no bridge at all, which is not a coverage of zero.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import bridge_on_crystals as crystals                      # noqa: E402

SHORT_SUBSTRATE = {"pair_id": "bench04_IKZF1_CRBN", "measurable": True,
                   "found": True, "dsasa_peptide": 228.3}
DOMAIN_SUBSTRATE = {"pair_id": "bench02_BRD4_VHL", "measurable": True,
                    "found": True, "dsasa_peptide": 980.7}
NO_GLUE = {"pair_id": "bench03_BRD4_CRBN", "measurable": False,
           "found": False, "dsasa_peptide": None}

PREDICTIONS = {
    ("15-mer", "04"): {"substrate": 211.8, "n_bridged": 10},
    ("whole domain", "04"): {"substrate": 211.8, "n_bridged": 10},
    ("15-mer", "02"): {"substrate": 255.6, "n_bridged": 4},
    ("whole domain", "02"): {"substrate": 984.7, "n_bridged": 10},
    ("15-mer", "03"): {"substrate": 290.4, "n_bridged": 4},
}


def _by(rows, pair, label):
    return next(row for row in rows
                if row["pair_id"] == pair and row["representation"] == label)


def test_a_short_substrate_is_reproduced_by_its_fifteen_mer():
    """IKZF1's ZF2 epitope is close to 15 residues, so cutting it to a
    15-mer loses little: this is the case where the main campaign's
    representation is adequate."""
    rows = crystals.substrate_coverage([SHORT_SUBSTRATE], PREDICTIONS)
    assert _by(rows, "bench04_IKZF1_CRBN", "15-mer")["coverage"] > 0.9


def test_a_folded_domain_is_not_reproduced_by_its_fifteen_mer():
    """BRD4's bromodomain buries a face, not a strand, and a 15-mer has no
    face to bury. The whole-domain arm of the same pair does reproduce it,
    which is what makes this a property of the representation rather than
    of the pair."""
    rows = crystals.substrate_coverage([DOMAIN_SUBSTRATE], PREDICTIONS)
    short = _by(rows, "bench02_BRD4_VHL", "15-mer")["coverage"]
    whole = _by(rows, "bench02_BRD4_VHL", "whole domain")["coverage"]
    assert short < 0.5
    assert whole > 0.9
    assert whole > short


def test_an_arm_with_no_bridge_has_no_coverage_rather_than_zero():
    """A ratio needs a numerator that was measured. Zero would say the
    prediction buried nothing, which is a different claim from not having
    found a bridge to measure."""
    rows = crystals.substrate_coverage(
        [DOMAIN_SUBSTRATE],
        {("15-mer", "02"): {"substrate": None, "n_bridged": 0}})
    row = _by(rows, "bench02_BRD4_VHL", "15-mer")
    assert row["coverage"] is None
    assert row["seeds_bridged"] == 0


def test_a_deposition_with_no_glue_contributes_no_row():
    """There is no deposited burial to be a fraction of, so the pair is
    absent rather than carrying a ratio against nothing."""
    rows = crystals.substrate_coverage([NO_GLUE], PREDICTIONS)
    assert rows == []


def test_the_ratio_is_predicted_over_deposited_and_not_the_other_way():
    """One of the two readings says the prediction under-buries and the
    other says the crystal does, and they are not interchangeable."""
    rows = crystals.substrate_coverage([DOMAIN_SUBSTRATE], PREDICTIONS)
    row = _by(rows, "bench02_BRD4_VHL", "15-mer")
    assert row["deposited"] == DOMAIN_SUBSTRATE["dsasa_peptide"]
    assert row["predicted"] == PREDICTIONS[("15-mer", "02")]["substrate"]
    assert row["coverage"] == round(row["predicted"] / row["deposited"], 3)
    assert row["coverage"] < 1.0
