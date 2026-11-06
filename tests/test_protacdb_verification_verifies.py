"""The licensing guarantee is checked rather than announced (F218).

Spec 2.1, verbatim: "PROTAC-DB stays internal-use-only and is never
redistributed". `deploy/build_atlas.py` ended by printing

    verified: no PROTAC-DB chemistry in the published bundle

from an f-string with no interpolation, no condition in front of it, and no
scan of the bundle anywhere above it. It was printed every time the build
reached its last line, whatever the bundle held.

What replaced it is an allow-list on provenance, and the negative controls
below are the point of this file: a check that has never refused anything is
not a check. The one that matters most is the misspelled source, because that
is the case `redact()` cannot catch by construction and therefore the only
case where a second opinion is worth having.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy"))

import build_atlas as B  # noqa: E402

A_SMILES = "CC(=O)Nc1ccc(cc1)S(=O)(=O)N"


def _bundle(tmp_path: Path, record: dict, name: str = "design.json") -> Path:
    bundle = tmp_path / "atlas"
    bundle.mkdir(exist_ok=True)
    (bundle / name).write_text(json.dumps(record))
    return bundle


def test_wwpdb_chemistry_is_publishable(tmp_path):
    """The permitted case, and the reason the check is about provenance.

    A molecule can be in PROTAC-DB and in the PDB at once: CCD 759 is MZ1 and
    so is PROTAC-DB 335. Publishing wwPDB's version redistributes wwPDB's
    data, so it travels freely, and a check that compared the chemistry
    against PROTAC-DB's table would refuse this bundle. The first version of
    this check did exactly that.
    """
    bundle = _bundle(tmp_path, {"ligand": {
        "ccd": "759", "smiles": A_SMILES, "source": "deposited_ternary"}})
    assert B.unattributable_chemistry_in(bundle) == []


def test_a_protacdb_sourced_smiles_is_refused(tmp_path):
    bundle = _bundle(tmp_path, {"ligand": {
        "key": "dBET57", "smiles": A_SMILES, "source": "protacdb"}})
    leaked = B.unattributable_chemistry_in(bundle)
    assert len(leaked) == 1, leaked
    assert leaked[0][2] == "protacdb"


@pytest.mark.parametrize("source", ["PROTAC-DB", "protac_db", "ProtacDB", ""])
def test_a_source_redact_does_not_recognise_is_refused(tmp_path, source):
    """The case that justifies a second opinion existing.

    `redact()` nulls a SMILES when `source in REDACT_WHEN_SOURCE`, so each of
    these is published untouched by it. An allow-list fails closed on all of
    them; a deny-list cannot, and a verifier sharing the deny-list would have
    confirmed the bundle clean.
    """
    from build_atlas import REDACT_WHEN_SOURCE

    assert source not in REDACT_WHEN_SOURCE, (
        "this source is on the deny-list, so it does not test the gap"
    )
    bundle = _bundle(tmp_path, {"ligand": {"smiles": A_SMILES, "source": source}})
    assert len(B.unattributable_chemistry_in(bundle)) == 1


def test_a_record_with_no_source_at_all_is_refused(tmp_path):
    bundle = _bundle(tmp_path, {"ligand": {"smiles": A_SMILES}})
    assert len(B.unattributable_chemistry_in(bundle)) == 1


def test_it_looks_nested_and_into_jsonl(tmp_path):
    bundle = tmp_path / "atlas"
    (bundle / "deep").mkdir(parents=True)
    (bundle / "deep" / "rows.jsonl").write_text(
        json.dumps({"pairs": [{"arms": {"ternary": {
            "smiles": A_SMILES, "source": "protacdb"}}}]}) + "\n"
        + json.dumps({"pairs": [{"arms": {"ternary": {
            "smiles": A_SMILES, "source": "deposited_ternary"}}}]}) + "\n")
    leaked = B.unattributable_chemistry_in(bundle)
    assert len(leaked) == 1, leaked
    assert "ternary" in leaked[0][1], leaked[0][1]


def test_a_redacted_record_is_not_refused(tmp_path):
    """redact() nulls the field, and a null is not a published SMILES."""
    bundle = _bundle(tmp_path, {"ligand": {
        "key": "dBET57", "smiles": None, "smiles_withheld": "internal use only",
        "source": "protacdb"}})
    assert B.unattributable_chemistry_in(bundle) == []


def test_every_permitted_source_carries_its_reason():
    """An allow-list without reasons becomes a list of whatever was there."""
    assert B.PUBLISHABLE_SMILES_SOURCES
    for source, reason in B.PUBLISHABLE_SMILES_SOURCES.items():
        assert isinstance(reason, str) and len(reason) > 20, (source, reason)


def test_an_empty_bundle_says_so_rather_than_passing_quietly(tmp_path):
    bundle = tmp_path / "atlas"
    bundle.mkdir()
    assert B.unattributable_chemistry_in(bundle) == []
    assert "no SMILES published" in B._verification_scope


def test_the_scope_reports_what_was_checked(tmp_path):
    bundle = _bundle(tmp_path, {"ligand": {
        "smiles": A_SMILES, "source": "deposited_ternary"}})
    B.unattributable_chemistry_in(bundle)
    assert "1 published SMILES" in B._verification_scope


def test_the_build_refuses_rather_than_printing_verified():
    """The claim and the refusal are both wired to the check's result."""
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "leaked = unattributable_chemistry_in(OUT)" in source
    claim = source.index("verified: every published SMILES")
    check = source.index("leaked = unattributable_chemistry_in(OUT)")
    assert check < claim, "the bundle is pronounced clean before it is checked"
    assert "REFUSED: the built bundle publishes chemistry" in source
    # And the claim says what it checked, so a build that checked nothing
    # cannot print the sentence a build that checked something prints.
    assert "_verification_scope" in source[claim - 400:claim + 400]
