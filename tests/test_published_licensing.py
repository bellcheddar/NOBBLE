"""What the published bundle may and may not carry.

Spec 2.1 and CLAUDE.md set three restrictions: PROTAC-DB stays
internal-use-only and is never redistributed, UbiBrowser ships as derived
counts only, and BioLiP2 annotations are not redistributed. The bundle is
rsynced to a public host, so a breach is published rather than merely
committed.

`build_atlas` already checks one direction, that no PROTAC-DB chemistry
reaches the bundle, and F72 fixed its count reporting zero while a withheld
field sat in the file. What nothing checked is the positive direction: that
every SMILES which *is* published has a source permitted to be.

Measured on the live bundle: seven ligand records, six sourced
`deposited_ternary` from the PDB entries and published, and one, dBET57,
sourced `protacdb` and withheld. UbiBrowser and BioLiP2 appear only as
availability booleans in `about.json`, which is metadata about which sources
were reachable rather than any of their content (F117).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PUBLISHED = ROOT / "deploy" / "atlas"
RESTRICTED = {"protacdb", "ubibrowser", "biolip"}
# Sources whose chemistry may be redistributed: the deposited structures.
PERMITTED_CHEMISTRY = {"deposited_ternary"}


def _bundle() -> list[Path]:
    """The whole bundle, from `conftest.published_files`.

    This globbed `*.json`, so the licensing check never looked at
    `results.jsonl`, which carries ligand records. Nothing was wrong there,
    `redact()` is applied to those rows too, but a check on what may be
    published should see what is published (F129).
    """
    from conftest import published_files

    files = published_files()
    if not files:
        pytest.skip("no published atlas")
    return files


def _ligand_records(document) -> list[dict]:
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "smiles" in node or "smiles_withheld" in node:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(document)
    return found


def test_every_published_smiles_has_a_permitted_source():
    """The direction nothing checked. A withheld record is not enough on its
    own: what matters is that the ones published were allowed to be."""
    from conftest import published_documents

    checked = 0
    for path, line, document in published_documents():
        for record in _ligand_records(document):
            if "smiles_withheld" in record:
                continue
            if not record.get("smiles"):
                continue        # nothing published for this record
            source = record.get("smiles_source") or record.get("source")
            assert source in PERMITTED_CHEMISTRY, (
                path.name, line, record.get("key") or record.get("ligand_key"),
                source
            )
            checked += 1
    if not checked:
        pytest.skip("no published ligand chemistry in the bundle")
    assert checked >= 5, checked


def test_protac_db_chemistry_is_withheld_and_says_so():
    from conftest import published_documents

    found = 0
    for path, line, document in published_documents():
        for record in _ligand_records(document):
            if (record.get("smiles_source") or record.get("source")) != "protacdb":
                continue
            found += 1
            # The key may be present with a null value, and that is the right
            # shape: a reader learns the record has chemistry and that it was
            # withheld, rather than that the field does not exist. What must
            # be absent is a value.
            assert not record.get("smiles"), (
                path.name, line, record.get("key") or record.get("ligand_key"),
                "PROTAC-DB chemistry is in the published bundle"
            )
            assert "smiles_withheld" in record
            assert "internal use" in record["smiles_withheld"], (
                "the withheld field no longer says why"
            )
    if not found:
        pytest.skip("no PROTAC-DB-sourced ligand in this bundle")


def test_the_restricted_sources_appear_only_as_availability():
    """UbiBrowser and BioLiP2 may be named, because saying which sources were
    reachable is not shipping their rows. What must not appear is their
    content: a curated pair, a predicted pair, an annotation."""
    offenders = []
    for path in _bundle():
        text = path.read_text()
        for term in RESTRICTED:
            for match in re.finditer(rf'"([a-z0-9_]*{term}[a-z0-9_]*)"\s*:\s*([^,}}\]]{{0,40}})',
                                     text, re.I):
                key, value = match.group(1), match.group(2).strip()
                # A boolean or a count is derived metadata. Anything else is
                # worth looking at by hand.
                if re.fullmatch(r"(true|false|null|\d+|\d+\.\d+)", value, re.I):
                    continue
                offenders.append(f"{path.name}: {key} = {value[:30]}")
    assert not offenders, offenders


def test_no_published_file_carries_a_restricted_source_as_a_row_list():
    """The shape a leak would take: a list of records under a restricted
    source's name."""
    from conftest import published_documents

    for path, line, document in published_documents():

        def walk(node, trail=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    lowered = key.lower()
                    if any(term in lowered for term in RESTRICTED):
                        assert not isinstance(value, (list, dict)) or not value, (
                            path.name, line, f"{trail}.{key}",
                            "a restricted source carries structured content"
                        )
                    walk(value, f"{trail}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{trail}[{index}]")

        walk(document)


def test_the_build_still_runs_its_own_redaction_check():
    """`build_atlas` prints a verification line at the end. Losing it would
    leave only these tests, which run when someone runs them."""
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "REDACT_WHEN_SOURCE" in source
    assert "protacdb" in source
    assert "no PROTAC-DB chemistry in the published bundle" in source
