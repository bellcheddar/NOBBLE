"""The published scan target was chosen by the method that was rejected.

`_default_parent` ranks the candidate degrons by measured Delta-ipTM,
because "the degron worth scanning first is the one with the largest signal
to move". It falls back to the shortest glue parent when nothing is scored,
so the tab has something before a campaign runs, and its own docstring says
why ranking by length is wrong: it "was an arbitrary tiebreak that happened
to land on BRD4/VHL: a PROTAC pair, when the arm is about glue dependence".

`build_atlas.py` never configured a campaign before building the design
report. With none configured `data.scores()` returns an empty list, so the
ranking saw nothing and the fallback fired on every atlas ever published.
The chain does configure before assembling the scan, so the published target
was GSPT1, chosen by length, and the scan that actually runs is IKZF1,
chosen by a measured Delta-ipTM of +0.316 (F89).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import data  # noqa: E402
from nobble.design import report  # noqa: E402
from nobble.execute.campaign import latest  # noqa: E402

PYTHON = str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python")


def _scored_campaign():
    for campaign in (latest("campaign"), latest("benchmark")):
        if campaign and (campaign / "scores.jsonl").exists():
            return campaign
    pytest.skip("no scored campaign on this checkout")


def test_the_two_selections_differ_so_the_bug_was_visible():
    """The premise. If the fallback and the ranking agreed, this would have
    been invisible and harmless; they do not."""
    campaign = _scored_campaign()
    data.configure(None)
    data._CAMPAIGN = None               # the state build_atlas ran in
    fallback = report._default_parent(report.candidate_parents())

    data.configure(str(campaign))
    ranked = report._default_parent(report.candidate_parents())

    assert fallback["peptide_id"] != ranked["peptide_id"], (
        "the length fallback and the measured ranking now agree, so this "
        "file no longer demonstrates anything"
    )
    assert "delta-ipTM" in (ranked.get("chosen_because") or ""), ranked


def test_the_ranked_choice_cites_a_measurement():
    campaign = _scored_campaign()
    data.configure(str(campaign))
    chosen = report._default_parent(report.candidate_parents())
    because = chosen.get("chosen_because") or ""
    assert "measured" in because, because
    assert any(ch.isdigit() for ch in because), (
        "the reason gives no figure, so it cannot be checked against the "
        "scores it claims to come from"
    )


def _buildable_campaign():
    """A scored campaign whose atlas build does not refuse.

    The main campaign's build refuses while F47's correction is pending, so
    asking for "the latest scored campaign" made this test skip, and a
    wiring test that skips is the thing F40 is about. The benchmark panel
    is scored and builds, so it is the one to drive the build with.
    """
    from nobble.validate import inputs

    for campaign in (latest("benchmark"), latest("campaign")):
        if not campaign or not (campaign / "scores.jsonl").exists():
            continue
        if not inputs.stale_inputs(campaign):
            return campaign
    pytest.skip("no scored campaign builds without refusing")


def test_the_atlas_build_configures_before_choosing(tmp_path):
    """The wiring (F40). A configure call in the source is not the same as
    the published file naming the ranked parent."""
    campaign = _buildable_campaign()
    target = tmp_path / "atlas"
    completed = subprocess.run(
        [PYTHON, "deploy/build_atlas.py", str(campaign)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        env={**os.environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE",
             "NOBBLE_ATLAS_OUT": str(target)},
    )
    if completed.returncode != 0:
        pytest.skip(f"the atlas build refused: {completed.stderr[-200:]}")

    published = json.loads((target / "design.json").read_text())
    parent = (published.get("preview") or {}).get("parent") or {}

    data.configure(str(campaign))
    expected = report._default_parent(report.candidate_parents())
    assert parent.get("peptide_id") == expected["peptide_id"], (
        "the atlas published a different scan target than the ranking "
        "chooses for the same campaign"
    )
    assert "delta-ipTM" in (parent.get("chosen_because") or ""), (
        "the published parent was chosen by the length fallback"
    )


def test_the_published_cost_names_its_parent(tmp_path):
    """Two parents of the same length emit the same job count and different
    token totals, so a cost without its subject invites exactly the
    comparison I made in F88."""
    campaign = _scored_campaign()
    data.configure(str(campaign))
    preview = report.build().get("preview") or {}
    cost = preview.get("cost") or {}
    parent = (preview.get("parent") or {}).get("peptide_id")
    assert cost.get("parent") == parent
    assert parent in (cost.get("basis") or ""), cost.get("basis")
