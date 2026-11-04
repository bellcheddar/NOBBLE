"""Construct boundaries come from named InterPro entries (CLAUDE.md).

Every job in every campaign is built on these numbers: get a boundary
wrong and the receptor is the wrong length, the token count is wrong, the
pocket residues are wrong, and nothing fails. The module had no test.

Runs against the cached annotations, so no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate import interpro


def test_a_named_entry_resolves_to_a_boundary():
    from nobble.curate import constructs

    # CRBN's CULT domain, the receptor behind every IMiD pair in the build.
    record = interpro.domain_by_accession("Q96SW2", constructs.CULT_DOMAIN)
    assert record["accession"] == constructs.CULT_DOMAIN
    assert record["start"] < record["end"]
    assert record["length"] == record["end"] - record["start"] + 1


def test_an_unannotated_entry_raises_rather_than_guessing():
    """Named entries exist so the code never picks "the longest domain".
    An entry that is not annotated must fail loudly, not fall back."""
    with pytest.raises(KeyError):
        interpro.domain_by_accession("Q96SW2", "IPR000000")


def test_a_discontinuous_domain_spans_its_fragments_by_position():
    """Boundaries are taken with min and max, not first and last.

    345 multi-fragment locations across the cached accessions are all in
    positional order today, so first/last happened to work. That is an
    undocumented property of someone else's API, and relying on it would
    move a construct boundary silently if it ever changed.
    """
    fragments = [{"start": 300, "end": 400}, {"start": 100, "end": 200}]
    payload = {"results": [{
        "metadata": {"accession": "IPR999999", "source_database": "interpro",
                     "type": "domain", "name": "test"},
        "proteins": [{"entry_protein_locations": [{"fragments": fragments}]}],
    }]}

    import unittest.mock as mock
    with mock.patch.object(interpro, "_fetch", return_value=payload):
        records = interpro.domains("Q00000")

    assert len(records) == 1
    assert records[0]["start"] == 100, "start was taken from the first fragment"
    assert records[0]["end"] == 400, "end was taken from the last fragment"


def test_every_construct_boundary_is_self_consistent():
    """Against the real constructs rather than a fixture."""
    from nobble.curate import constructs

    for name, construct in constructs.CONSTRUCTS.items():
        assert construct.segments, name
        total = 0
        for segment in construct.segments:
            sequence = segment.sequence()
            assert sequence, f"{name}: empty segment"
            total += len(sequence)
        assert construct.residue_count() == total, name
