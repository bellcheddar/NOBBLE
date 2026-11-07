"""The crystal control reads files a live runner is appending to (F297f).

`results.jsonl` is appended one row at a time by a runner that may be killed
at any moment, so a torn final line is an expected state and the rows before
it are good. `paths.read_jsonl(tolerate_torn=True)` exists for exactly that,
and F111 recorded seven readers of the same files that did not use it.

The crystal control was the eighth. It parsed every line with a bare
`json.loads`, and `deploy/build_atlas.py` now calls it on every rebuild, so a
kill at the wrong moment would have taken down an atlas build over a line
whose absence changes nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import bridge_on_crystals as crystals                      # noqa: E402

@pytest.fixture(autouse=True)
def _clear_the_cache():
    """Before and after, not just before.

    `_construct_by_pair` is a module-level `lru_cache`, so a test that fills
    it from a tmp_path campaign leaves that mapping in place for whatever
    runs next in the same session. Clearing only on the way in fixed these
    tests and broke
    `test_the_receptor_comparator_is_derived_from_the_construct`, which then
    saw one pair with one accession and reported that every benchmark
    construct now has the same arity. A cache shared between tests has to be
    cleaned up by the test that dirties it.
    """
    crystals._construct_by_pair.cache_clear()
    yield
    crystals._construct_by_pair.cache_clear()


GOOD = {"job_id": "bench01_GSPT1_CRBN__ternary__unconstrained__seed1",
        "pair_id": "bench01_GSPT1_CRBN", "construct": "CRBN_CULT",
        "complex_type": "ternary", "tokens": 400, "structure": "s.cif"}


def _campaign(tmp_path: Path, torn: bool) -> Path:
    directory = tmp_path / "campaigns" / "benchmark_20000101T000000Z"
    directory.mkdir(parents=True)
    body = json.dumps(GOOD) + "\n"
    if torn:
        body += json.dumps(dict(GOOD, job_id="torn"))[:40]
    (directory / "results.jsonl").write_text(body)
    return tmp_path


def test_the_construct_lookup_reads_a_whole_file(tmp_path, monkeypatch):
    monkeypatch.chdir(_campaign(tmp_path, torn=False))
    assert crystals.construct_of("bench01_GSPT1_CRBN") == "CRBN_CULT"


def test_a_torn_final_line_does_not_lose_the_rows_before_it(tmp_path, monkeypatch):
    """The whole point: the complete records are still read."""
    monkeypatch.chdir(_campaign(tmp_path, torn=True))
    assert crystals.construct_of("bench01_GSPT1_CRBN") == "CRBN_CULT"


def test_the_rescoring_pass_also_survives_it(tmp_path, monkeypatch):
    """Two readers of the same file, and only fixing one leaves the build
    failing on the other."""
    monkeypatch.chdir(_campaign(tmp_path, torn=True))
    rows = crystals.predicted_rows()
    assert ("15-mer", "01") in rows


def test_neither_reader_parses_a_line_by_hand():
    """A text check, because the failure mode is a `json.loads` per line
    reappearing in a file that reads a live runner's output."""
    source = (ROOT / "tools" / "bridge_on_crystals.py").read_text()
    assert "read_text().splitlines()" not in source
    assert source.count("paths.read_jsonl") >= 2


def test_the_lookup_is_built_once(tmp_path, monkeypatch):
    """Seven pairs used to mean seven passes over both campaigns."""
    monkeypatch.chdir(_campaign(tmp_path, torn=False))
    crystals.construct_of("bench01_GSPT1_CRBN")
    crystals.construct_of("bench01_GSPT1_CRBN")
    info = crystals._construct_by_pair.cache_info()
    assert info.misses == 1 and info.hits >= 1
