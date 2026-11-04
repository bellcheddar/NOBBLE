"""The campaign manifest routes each arm by its own rule.

The three arms reach a receptor and a ligand by different routes, so the
routing is explicit per source rather than one rule with exceptions. The
cases pinned here are the ones that were wrong or nearly wrong when it was
written.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate import manifest as M


def _manifest():
    return M.build_campaign_manifest()


def test_a_scramble_inherits_a_smiles_encoded_parent_ligand():
    """The bug this was written for.

    The scramble inheritance first rebuilt the parent's ligand with by_ccd,
    which silently returns nothing for a degrader that never had a CCD.
    bench03's dBET57 is SMILES-encoded, so its scramble fell out of the
    campaign as "unroutable" while its positive ran: a positive with no
    control, which is worse than running neither.
    """
    manifest = _manifest()
    scrambles = [p for p in manifest["pairs"] if p["tier"] == "scramble"]
    smiles_inherited = [
        p for p in scrambles
        if p["ligand"].get("encoding") == "smiles"
    ]
    assert smiles_inherited, "no scramble inherited a SMILES ligand"
    assert manifest["unroutable"] == [], manifest["unroutable"]


def test_every_scramble_matches_its_parents_receptor_and_ligand():
    """A composition-matched scramble run against a different receptor or a
    different drug than its positive is not a control for anything."""
    manifest = _manifest()
    by_pair = {p["pair_id"]: p for p in manifest["pairs"]}

    scrambles = [p for p in manifest["pairs"] if p["tier"] == "scramble"]
    assert scrambles
    for scramble in scrambles:
        parent = by_pair[scramble["parent_pair_id"]]
        assert scramble["construct"] == parent["construct"]
        assert scramble["ligand"]["key"] == parent["ligand"]["key"]


def test_every_sievers_pair_carries_the_drug_its_screen_row_assigned():
    manifest = _manifest()
    sievers = [p for p in manifest["pairs"] if p["tier"] == "sievers_zf"]
    assert len(sievers) == 120

    allowed = {"Y70", "LVY"}
    for pair in sievers:
        assert pair["ligand"]["ccd"] in allowed, pair["ligand"]["ccd"]
        assert pair["e3_gene"] == "CRBN"
        assert pair["assigned_drug"] in {"POM", "LEN"}


def test_the_matched_split_is_both_sided():
    """A ROC needs both classes. If the degraded side were empty the arm
    would still build and still score, and the ROC would be meaningless."""
    manifest = _manifest()
    sievers = [p for p in manifest["pairs"] if p["tier"] == "sievers_zf"]
    degraded = [p for p in sievers if p["screen_label"] == "degraded"]
    not_degraded = [p for p in sievers if p["screen_label"] == "not_degraded"]

    assert len(degraded) == 24
    assert len(not_degraded) == 96


def test_the_manifest_has_no_errors_and_every_pair_has_jobs():
    manifest = _manifest()
    assert manifest["errors"] == 0, manifest["issues"]
    assert len(manifest["pairs"]) == 158
    assert len(manifest["jobs"]) == 2370
    for pair in manifest["pairs"]:
        assert pair["jobs"] > 0, pair["pair_id"]
