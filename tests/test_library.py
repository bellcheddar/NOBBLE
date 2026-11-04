"""The reduced library must survive the process that made it.

Phase 1 reported "25,567 candidates reduced to 220" and left nothing on disk
that could reproduce it: reduce_library and campaign_budget had no callers
anywhere in the tree, and data/manifests/ held only the benchmark panel. The
project rule is that every stage writes a manifest and is resumable and
idempotent, and assembly is measured at over thirty minutes wall clock,
almost all of it blocked on UniProt and InterPro rather than on compute. A
stage that expensive must not be rebuilt by accident.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate import library as L


def _seed_manifest(tmp_path, monkeypatch, rows, summary):
    manifest = tmp_path / "library.jsonl"
    summary_path = tmp_path / "library.summary.json"
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows))
    summary_path.write_text(json.dumps(summary))
    monkeypatch.setattr(L, "MANIFEST", manifest)
    monkeypatch.setattr(L, "SUMMARY", summary_path)
    return manifest, summary_path


def test_an_existing_manifest_is_reloaded_not_rebuilt(tmp_path, monkeypatch):
    """A rebuild costs half an hour of network calls. It must be opt-in."""
    _seed_manifest(
        tmp_path, monkeypatch,
        [{"peptide_id": "bench0", "source": "benchmark", "sequence": "ACDE"}],
        {"selected": 1, "status": "within_budget"},
    )

    def _explode():
        raise AssertionError("P.build() was called despite a manifest existing")

    monkeypatch.setattr(L.P, "build", _explode)

    result = L.build()
    assert len(result["peptides"]) == 1
    assert result["peptides"][0]["peptide_id"] == "bench0"
    assert "not rebuilt" in result["summary"]["status"]


def test_load_returns_none_when_the_library_has_not_been_built(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "MANIFEST", tmp_path / "missing.jsonl")
    monkeypatch.setattr(L, "SUMMARY", tmp_path / "missing.summary.json")
    assert L.load() is None


def test_a_half_written_library_is_not_treated_as_built(tmp_path, monkeypatch):
    """A manifest with no summary is a kill in the middle of writing, not a
    finished stage. Reloading it would hide the reduction's own account of
    itself, including whether it came in over budget."""
    manifest = tmp_path / "library.jsonl"
    manifest.write_text(json.dumps({"peptide_id": "x", "source": "benchmark"}) + "\n")
    monkeypatch.setattr(L, "MANIFEST", manifest)
    monkeypatch.setattr(L, "SUMMARY", tmp_path / "library.summary.json")
    assert L.load() is None


def test_force_rebuilds_even_with_a_manifest_present(tmp_path, monkeypatch):
    _seed_manifest(
        tmp_path, monkeypatch,
        [{"peptide_id": "stale", "source": "benchmark", "sequence": "ACDE"}],
        {"selected": 1},
    )
    called = {"build": False}

    def _fake_build():
        called["build"] = True
        raise RuntimeError("stop here: the point is that it was called")

    monkeypatch.setattr(L.P, "build", _fake_build)

    with pytest.raises(RuntimeError):
        L.build(force=True)
    assert called["build"], "force did not trigger a rebuild"
