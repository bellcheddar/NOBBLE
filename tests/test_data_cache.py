"""The app's cache must notice when the pipeline rewrites a file.

`_cached` keys on (key, path, mtime) so a live campaign refreshes without
a restart. A mutation sweep found that dropping the mtime comparison, so
any cached entry is reused regardless, left the whole suite passing.

That matters because of when it would bite. `refresh.sh` rewrites
scores.jsonl in place after every campaign, and the chain calls it twice:
once after the main run and again at the end with tier 2 and the design
scan included. A cache that ignored mtime would serve the first version
for the life of the process, so the site would show numbers that the
pipeline had already replaced, with nothing anywhere saying so.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import data  # noqa: E402


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_a_rewritten_file_is_reread(tmp_path):
    """The case refresh.sh creates twice in every chain run."""
    path = tmp_path / "scores.jsonl"
    _write(path, [{"pair_id": "p1", "delta_iptm": 0.10}])

    first = data._cached("scores-test", path, data._read_jsonl)
    assert [row["delta_iptm"] for row in first] == [0.10]

    # Rewritten with a distinctly later mtime, as a pipeline rewrite would be.
    _write(path, [{"pair_id": "p1", "delta_iptm": 0.90}])
    os.utime(path, (time.time() + 10, time.time() + 10))

    second = data._cached("scores-test", path, data._read_jsonl)
    assert [row["delta_iptm"] for row in second] == [0.90], (
        "the cache served the old numbers after the file was rewritten"
    )


def test_an_unchanged_file_is_not_reread(tmp_path):
    """The cache has to still be a cache: without this the test above would
    pass on a function that simply never caches."""
    path = tmp_path / "scores.jsonl"
    _write(path, [{"pair_id": "p1", "delta_iptm": 0.10}])

    calls = []

    def counting_loader(p):
        calls.append(p)
        return data._read_jsonl(p)

    data._cached("scores-count", path, counting_loader)
    data._cached("scores-count", path, counting_loader)
    assert len(calls) == 1, f"the loader ran {len(calls)} times for one mtime"


def test_two_campaigns_sharing_an_mtime_do_not_share_rows(tmp_path):
    """The bug the docstring records, kept closed: the entry is keyed on the
    path, so two campaigns whose files happen to share an mtime stay
    distinct."""
    first_dir = tmp_path / "campaign_a"
    second_dir = tmp_path / "campaign_b"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "scores.jsonl"
    second = second_dir / "scores.jsonl"
    _write(first, [{"pair_id": "a", "delta_iptm": 0.1}])
    _write(second, [{"pair_id": "b", "delta_iptm": 0.2}])
    shared = time.time()
    os.utime(first, (shared, shared))
    os.utime(second, (shared, shared))

    rows_a = data._cached("scores-two", first, data._read_jsonl)
    rows_b = data._cached("scores-two", second, data._read_jsonl)
    assert [r["pair_id"] for r in rows_a] == ["a"]
    assert [r["pair_id"] for r in rows_b] == ["b"], (
        "a second campaign returned the first one's rows"
    )


def test_an_absent_file_yields_the_shape_its_consumers_expect(tmp_path):
    """campaign.json is read as a mapping and everything else as a list, so
    an absent file must not hand back the wrong empty thing: a consumer
    doing .get on a list raises, which is how two routes once 500'd."""
    missing = tmp_path / "nope.jsonl"
    assert data._cached("scores", missing, data._read_jsonl) == []
    assert data._cached("campaign", missing, data._read_jsonl) == {}


def test_the_degron_gate_records_a_non_glycine_fallback():
    """Both reference degrons are glycine degrons: the defining residue is
    the glycine packing closest to the glue. The gate falls back to the
    closest contact of any kind so the test stays meaningful for another
    degron class, and that note is the only record the fallback happened.

    A mutation sweep found the note could be dropped with the suite still
    passing, which is this project's recurring shape: a fallback taken and
    not recorded.
    """
    import inspect

    from nobble.curate import degron_gate

    source = inspect.getsource(degron_gate.check)
    assert "glycines = [" in source, "the glycine selection has moved"
    assert "if not glycines:" in source, (
        "the gate no longer distinguishes a glycine contact from a fallback"
    )
    # The note's wording is what a reader sees, so it has to say which
    # happened rather than merely that something did.
    assert "no glycine among the glue contacts" in source
    assert "used the closest contact" in source


def test_the_gate_result_has_somewhere_to_put_that_note():
    """A note appended to a field that is dropped before anyone reads it
    would pass the check above and still tell nobody."""
    from nobble.curate.degron_gate import GateResult

    fields = GateResult.__dataclass_fields__
    assert "notes" in fields, "GateResult no longer carries notes"
    assert "degron_amino_acid" in fields, (
        "the residue actually chosen is no longer recorded, so a fallback "
        "could not be checked against it"
    )
