"""PROGRESS.md's library figures, recomputed from the manifest (F136).

The phase table said "25,567-peptide library reduced to 220". The manifest
says 25,519 candidates reduced to 158. Both numbers were from an earlier
build: the candidate pool before a deduplication, and a budget before the
hardware probe measured the real one.

Nobody would act on a wrong reduction ratio, which is exactly why it sat
there. The figures a reader quotes should be the figures on disk, and the
cheapest way to keep them so is to recompute them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "data" / "manifests" / "library.summary.json"
PROGRESS = ROOT / "PROGRESS.md"


def _summary() -> dict:
    return json.loads(SUMMARY.read_text())


def test_the_candidate_and_selected_counts_match_the_manifest():
    summary = _summary()
    text = PROGRESS.read_text()
    phrase = re.search(
        r"([\d,]+)-candidate library reduced to ([\d,]+) selected", text)
    assert phrase is not None, (
        "PROGRESS.md no longer states the library reduction in the form this "
        "test recomputes, so the figures are unpinned again"
    )
    candidates = int(phrase.group(1).replace(",", ""))
    selected = int(phrase.group(2).replace(",", ""))
    assert candidates == summary["candidates"], (
        f"PROGRESS.md says {candidates} candidates, the manifest says "
        f"{summary['candidates']}"
    )
    assert selected == summary["selected"], (
        f"PROGRESS.md says {selected} selected, the manifest says "
        f"{summary['selected']}"
    )


def test_the_reduction_ratio_matches():
    summary = _summary()
    found = re.search(r"`reduction_ratio` ([\d.]+)", PROGRESS.read_text())
    assert found is not None, "the reduction ratio is no longer stated"
    assert float(found.group(1)) == summary["reduction_ratio"]


def test_the_claim_that_no_diverse_peptides_were_selected_is_true():
    """The sentence a reader would challenge, checked against the manifest.

    If a later campaign does have headroom, `diverse` stops being zero and
    this fails, which is the right time to rewrite the sentence rather than
    leave a stale one standing.
    """
    summary = _summary()
    text = PROGRESS.read_text()
    assert "`diverse: 0`" in text
    assert summary["diverse"] == 0, (
        f"the manifest now selects {summary['diverse']} diverse peptide(s), "
        "so PROGRESS.md's claim that this campaign is calibration only is "
        "out of date"
    )


def test_three_of_the_five_spec_sources_really_do_contribute_nothing():
    """Spec 3.4 names five peptide sources. The manifest holds three.

    Named rather than counted, because "three of five" is only true while
    the five are the five the spec lists.
    """
    spec = ROOT / "BUILD_SPEC.md"
    section = spec.read_text().split("### 3.4")[1].split("### 3.5")[0]
    for source in ("Curated degrons", "Sievers zinc fingers", "C-degrons",
                   "Benchmark degrons", "Negatives"):
        assert source in section, (
            f"spec 3.4 no longer lists {source}, so PROGRESS.md's "
            "'three of five' is counting against a different list"
        )
    present = set(_summary()["sources"])
    assert present == {"benchmark", "scramble", "sievers_zf"}, present
