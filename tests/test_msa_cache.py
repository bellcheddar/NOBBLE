"""The MSA cache is content-addressed, and every job depends on the key.

`sequence_key` hashes a sequence to a filename and `build_yaml` writes that
path into each receptor chain. If two different sequences produced one key,
every job for one of them would be aligned against the other's homologues
and nothing would say so: Boltz would read a valid a3m of the wrong
protein. If one sequence produced two keys, the campaign would call the
MSA server mid-run, which spec 1.3 exists to prevent.

The module had no test. Its network path is not testable here, but the
cache key is pure and is the part every job rides on.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.execute import msa


def test_the_key_is_stable_for_one_sequence():
    seq = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
    assert msa.sequence_key(seq) == msa.sequence_key(seq)
    assert msa.a3m_path(seq) == msa.a3m_path(seq)


def test_different_sequences_get_different_keys():
    """Including sequences that differ by one residue, which is exactly
    what a design variant is."""
    base = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ"
    variants = {base}
    for index in range(len(base)):
        mutant = base[:index] + ("A" if base[index] != "A" else "G") + base[index + 1:]
        variants.add(mutant)

    keys = {msa.sequence_key(s) for s in variants}
    assert len(keys) == len(variants), "two sequences share one MSA key"


def test_the_key_is_content_addressed_not_identity_addressed():
    """Two constructs can carry the same chain: DDB1's propeller appears in
    two of them. The same sequence must reuse one alignment rather than be
    aligned twice."""
    seq = "MSYNYVVTAQKPTAVNGCVTGHFTSAEDLNLLIAKNTRLEIYVVTAEGLRPVKEVGMYGK"
    assert msa.sequence_key(seq) == msa.sequence_key(str(seq))
    assert msa.a3m_path(seq).name.endswith(".a3m")


def test_an_empty_or_missing_cache_file_is_not_cached(tmp_path, monkeypatch):
    """A zero-byte a3m is a failed fetch, not an alignment. Treating it as
    cached would hand Boltz an empty file and call it a hit."""
    monkeypatch.setattr(msa, "CACHE", tmp_path)
    seq = "MKTAYIAKQRQ"
    assert msa.is_cached(seq) is False

    path = tmp_path / f"{msa.sequence_key(seq)}.a3m"
    path.write_text("")
    assert msa.is_cached(seq) is False, "an empty a3m counted as cached"

    path.write_text(">q\nMKTAYIAKQRQ\n")
    assert msa.is_cached(seq) is True


def test_the_empty_sentinel_is_what_boltz_expects():
    """Peptide chains carry this string rather than a path (spec 1.3)."""
    assert msa.EMPTY == "empty"


def test_no_two_real_construct_segments_share_a_key():
    """Against the actual constructs rather than invented strings. Eleven
    receptor segments, eleven keys: no two different sequences collide,
    and any sequence genuinely shared between constructs collapses to one
    alignment, which is the behaviour the content-addressing exists for."""
    from nobble.curate import constructs

    by_key: dict[str, set[str]] = {}
    for construct in constructs.CONSTRUCTS.values():
        for segment in construct.segments:
            sequence = segment.sequence()
            by_key.setdefault(msa.sequence_key(sequence), set()).add(sequence)

    collisions = {k: v for k, v in by_key.items() if len(v) > 1}
    assert not collisions, f"different sequences sharing one MSA: {list(collisions)}"
    assert by_key, "no construct segments found"
