"""A design scan with nothing to profile refuses rather than reporting success (F321).

F195 made `tools/run_design.sh` exit non-zero when the lift step *raised*,
on the reasoning that the inference is the expensive part and the script
should say whether the analysis after it ran. A lift that legitimately
computes nothing was still a silent success: `if report.get('lifts'):`
simply skipped the profile, no `scan_profile.json` was written, and the
script printed "design scan done exit=0". F252's verdict then reads a
missing profile as "not yet testable" forever, with nothing saying why.

Three ways to get there, and the worst was the one with no explanation at
all: `from_scores`'s two early returns carried a status and its success path
did not, so a parent that is scored and has no design variants returned
`lifts: []` and nothing else.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.design import lift                             # noqa: E402

SCRIPT = (ROOT / "tools" / "run_design.sh").read_text()


def test_every_empty_result_carries_a_status(tmp_path):
    """All three, because the one that had none was the one that could not
    be diagnosed."""
    import json

    missing = lift.from_scores(tmp_path / "absent.jsonl", "p")
    assert missing["lifts"] == [] and missing["status"]

    scores = tmp_path / "scores.jsonl"
    scores.write_text(json.dumps(
        {"peptide_id": "p", "pair_id": "p", "peptide_sequence": "AAA"}) + "\n")

    no_parent = lift.from_scores(scores, "other")
    assert no_parent["lifts"] == []
    assert "not scored" in no_parent["status"]

    no_variants = lift.from_scores(scores, "p")
    assert no_variants["lifts"] == []
    assert "no design variants" in no_variants["status"], no_variants


def test_a_computed_report_says_computed(tmp_path):
    """The status must distinguish the healthy case, or a caller checking it
    cannot act on it."""
    import json

    scores = tmp_path / "scores.jsonl"
    scores.write_text("\n".join(json.dumps(row) for row in (
        {"peptide_id": "p", "pair_id": "p", "peptide_sequence": "AAA",
         "delta_iptm": 0.5},
        {"peptide_id": "v", "pair_id": "v", "parent_peptide_id": "p",
         "tier": "design", "peptide_sequence": "AAG", "delta_iptm": 0.6},
    )) + "\n")
    report = lift.from_scores(scores, "p")
    assert report["lifts"], report
    assert report["status"] == "computed"


def test_the_scan_refuses_rather_than_skipping_the_profile():
    """The guard, in the script. Without it the expensive half ran and the
    cheap half silently did not."""
    assert "if not report.get('lifts')" in SCRIPT
    assert "REFUSING: no lift to profile" in SCRIPT
    assert "SystemExit(3)" in SCRIPT


def test_the_refusal_names_which_of_the_three_it_is():
    """A refusal that does not say why leaves the same diagnosis to be made
    by hand, which is what the status exists for."""
    position = SCRIPT.index("REFUSING: no lift to profile")
    assert "report.get('status')" in SCRIPT[position:position + 300]


def test_the_refusal_comes_before_the_profile_is_written():
    """Below the write it would never run, which is F271's shape."""
    assert SCRIPT.index("if not report.get('lifts')") < SCRIPT.index(
        "scan_profile.json')")


def test_the_scan_still_exits_on_the_lift_code():
    """F195's fix must survive this one: the script's exit code is still the
    analysis step's, so a refusal reaches the chain."""
    assert "LIFT_CODE=$?" in SCRIPT
    assert "exit $LIFT_CODE" in SCRIPT
