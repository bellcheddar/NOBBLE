"""A cache a later run reads back must never be half-written.

`Path.write_text` truncates and then writes, so a kill inside that window
leaves whatever had been flushed. For a file something reads later that is a
corruption with no self-healing, and the three caches here differ in how
loudly they would fail.

The InterPro cache is JSON, so damage fails to parse. That sounds safe and is
not: `_fetch` returns the file because it `exists()` and never re-fetches it,
and `domain_context` catches `Exception` and reports `interpro_unavailable`,
which drops a substrate from its folded domain to the 15-mer. That is the
independent variable of the F6 experiment, changed silently.

The UniProt sequence cache is plain text, which is worse. A truncated protein
sequence is still a valid-looking protein, there is no parse step to fail at,
and every domain slice taken from it would be quietly short. F107 and F108
are both about domain boundaries; this is the same boundary arriving wrong by
another route.

So the writes go through `paths.write_atomic`, which renames into place
(F110).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402


def test_the_file_appears_whole(tmp_path):
    target = tmp_path / "nested" / "value.json"
    paths.write_atomic(target, json.dumps({"a": 1}))
    assert json.loads(target.read_text()) == {"a": 1}
    assert [item.name for item in target.parent.iterdir()] == ["value.json"], (
        "a temporary file was left behind"
    )


def test_an_interrupted_write_leaves_the_previous_contents(tmp_path, monkeypatch):
    """The whole point. The old contents are what a reader gets, rather than
    a prefix of the new ones."""
    target = tmp_path / "value.json"
    target.write_text(json.dumps({"kept": True}))

    def killed(src, dst):
        raise KeyboardInterrupt("killed between write and rename")

    monkeypatch.setattr(paths.os, "replace", killed)
    with pytest.raises(KeyboardInterrupt):
        paths.write_atomic(target, json.dumps({"new": True}))
    assert json.loads(target.read_text()) == {"kept": True}


def test_the_temporary_sits_beside_the_target(tmp_path, monkeypatch):
    """`os.replace` is atomic within a filesystem, not across them, so the
    temporary cannot live in /tmp."""
    target = tmp_path / "value.json"
    seen = {}

    def capture(src, dst):
        seen["src"] = Path(src)
        seen["dst"] = Path(dst)

    monkeypatch.setattr(paths.os, "replace", capture)
    paths.write_atomic(target, "x")
    assert seen["src"].parent == target.parent, seen


def test_every_cache_write_goes_through_it():
    """The rule, not the three instances. A cache added later with a bare
    write_text is the same defect again."""
    offenders = []
    for relative in ("nobble/curate/interpro.py", "nobble/curate/numbering.py",
                     "nobble/execute/msa.py"):
        source = (ROOT / relative).read_text()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if ".write_text(" in stripped and "write_atomic" not in stripped:
                offenders.append(f"{relative}: {stripped[:70]}")
    assert not offenders, offenders


def test_an_empty_cached_sequence_is_refused():
    """Plain text has no parse step, so the check has to be explicit."""
    from nobble.curate import numbering

    numbering.canonical_sequence.cache_clear()
    target = numbering.CACHE / "P00000.seq"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("   \n")
    try:
        with pytest.raises(RuntimeError, match="empty"):
            numbering.canonical_sequence("P00000")
    finally:
        target.unlink()
        numbering.canonical_sequence.cache_clear()


def test_a_cached_sequence_of_non_residues_is_refused():
    from nobble.curate import numbering

    numbering.canonical_sequence.cache_clear()
    target = numbering.CACHE / "P00001.seq"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"error": "not found"}')
    try:
        with pytest.raises(RuntimeError, match="not residues"):
            numbering.canonical_sequence("P00001")
    finally:
        target.unlink()
        numbering.canonical_sequence.cache_clear()


def test_the_refusal_names_the_file_to_delete():
    """A corrupt cache is fixed by deleting it, so the message has to say
    which one. The alternative is an operator guessing among 1,200 files."""
    from nobble.curate import numbering

    numbering.canonical_sequence.cache_clear()
    target = numbering.CACHE / "P00002.seq"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("")
    try:
        with pytest.raises(RuntimeError) as raised:
            numbering.canonical_sequence("P00002")
        assert str(target) in str(raised.value), raised.value
    finally:
        target.unlink()
        numbering.canonical_sequence.cache_clear()


def test_the_live_caches_are_intact():
    """Measured rather than assumed, since the fix removes the cause and not
    any damage already on disk."""
    import re

    sequences = sorted(Path(ROOT / "data" / "cache" / "uniprot").glob("*.seq"))
    if sequences:
        for path in sequences:
            text = path.read_text().strip()
            assert text, path.name
            assert re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWYBXZUO]+", text), path.name

    responses = sorted(Path(ROOT / "data" / "cache" / "interpro").glob("*.json"))
    if responses:
        broken = []
        for path in responses:
            try:
                json.loads(path.read_text())
            except ValueError:
                broken.append(path.name)
        assert not broken, broken[:5]


def test_no_writing_temporaries_are_left_in_the_caches():
    """A leftover `.writing` file means an interrupted write, and it would
    not be picked up as a cache entry, so it would go unnoticed."""
    for directory in ("uniprot", "interpro", "msa"):
        root = ROOT / "data" / "cache" / directory
        if not root.exists():
            continue
        assert not list(root.rglob("*.writing")), directory
