"""The best-window pLDDT search decides Tier B membership.

spec 3.3 filters receptors on mean pLDDT, and `summary` reports both the
whole-model mean and the best 200-residue window. The window matters
because a long protein with one well-ordered domain and a lot of
disorder has a poor whole-model mean and a good domain: judging it on the
whole would reject exactly the receptors worth running.

The search is a rolling sum with 1-based reporting, which is the shape
that goes wrong by one and still returns a plausible number. The module
had no test. These use a constructed profile, so no AlphaFold model is
needed and the expected answer is known rather than observed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate import plddt


def _summary(profile, monkeypatch) -> dict:
    monkeypatch.setattr(plddt, "plddt_profile", lambda accession: tuple(profile))
    return plddt.summary("TEST")


def test_a_short_model_reports_the_whole_thing_as_its_window(monkeypatch):
    """Below the window length there is nothing to slide."""
    result = _summary([90.0] * 50, monkeypatch)
    assert result["status"] == "ok"
    assert result["residues"] == 50
    assert result["mean_plddt"] == 90.0
    assert result["best_window_mean_plddt"] == 90.0
    assert result["best_window"] == [1, 50]


def test_the_window_finds_an_ordered_domain_inside_a_disordered_protein(monkeypatch):
    """The case the window exists for: 200 good residues buried in noise.
    Reported 1-based and inclusive, so a domain at positions 301 to 500
    must come back as [301, 500] and not [300, 499] or [302, 501]."""
    profile = [20.0] * 300 + [95.0] * 200 + [20.0] * 300
    result = _summary(profile, monkeypatch)

    assert result["residues"] == 800
    assert result["best_window"] == [301, 500], result["best_window"]
    assert result["best_window_mean_plddt"] == 95.0
    # The whole-model mean would have rejected this receptor outright.
    assert result["mean_plddt"] < 50


def test_the_window_at_the_very_start_and_the_very_end(monkeypatch):
    """Both edges, because a rolling sum typically fails at one of them."""
    start = _summary([95.0] * 200 + [10.0] * 300, monkeypatch)
    assert start["best_window"] == [1, 200], start["best_window"]

    end = _summary([10.0] * 300 + [95.0] * 200, monkeypatch)
    assert end["best_window"] == [301, 500], end["best_window"]
    assert end["best_window"][1] == end["residues"]


def test_an_unreadable_or_absent_model_reports_rather_than_raises(monkeypatch):
    """Tier B selection runs over hundreds of accessions, so one missing
    model must not stop the pass. It reports a status instead."""
    monkeypatch.setattr(plddt, "plddt_profile", lambda a: ())
    empty = plddt.summary("NOMODEL")
    assert empty["status"] == "no_model"
    assert empty["mean_plddt"] is None

    def _boom(accession):
        raise OSError("file is not there")

    monkeypatch.setattr(plddt, "plddt_profile", _boom)
    broken = plddt.summary("BROKEN")
    assert broken["status"].startswith("unreadable: OSError")
    assert broken["best_window_mean_plddt"] is None
