"""Which parent was chosen, and why, are different records (F338).

`nobble.design.report.build`'s preview chooses a scan parent two ways and
says which in `chosen_because`:

- by largest measured Delta-ipTM over the scored parents; or
- when nothing is scored, by a fallback whose own wording is "a scan chosen
  this way has not been ranked against anything".

Both produced an identical `campaign.json`, because `assemble.assemble`
recorded `parent` and not the reason. So a scan whose parent was ranked
against 158 pairs was indistinguishable from one that was not ranked at all.

That distinction is the entire reason `tools/run_chain.sh` queues the design
stage last and re-assembles against the full campaign before running it, in
its own words: "reusing a parent chosen from the benchmark alone would throw
that away". The re-assembly runs with `|| true`, so on a failure the chain
hands `run_design.sh` whatever design campaign was already on disk, and
nothing downstream could tell.

Measured on 2026-11-08. `design_20261104T094939Z` was assembled at 09:49 on
the 4th, before the main campaign had scored, and the ranked answer against
all 158 pairs is the same peptide for a different reason: +0.316 Delta-ipTM
with five candidates excluded for a flagged seed collapse. The same parent
by luck, not by provenance, and the wording that would have said so was
discarded.

Two things are fixed. The assembler records the reason. And
`run_design.sh` checks the parent against what the ranking would choose now,
which is the question that decides whether 240 jobs are worth running: a
parent that is still the ranked choice is sound however it was picked, and
one that is not is 4.4 hours on the wrong peptide.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ASSEMBLE = (ROOT / "nobble" / "design" / "assemble.py").read_text()
SCRIPT = (ROOT / "tools" / "run_design.sh").read_text()


def _main_campaign():
    found = sorted(ROOT.glob("campaigns/campaign_*"))
    return found[-1] if found else None


def test_the_assembler_records_the_reason_not_only_the_parent():
    assert '"parent_provenance": parent_provenance(parent_id),' in ASSEMBLE, (
        "campaign.json records which parent and not why, so a scan ranked "
        "against the full campaign is indistinguishable from the fallback "
        "that was not ranked against anything"
    )


def test_the_ranked_choice_reports_the_reason():
    campaign = _main_campaign()
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")
    from nobble.design import assemble, report
    from nobble.app import data

    data.configure(str(campaign))
    parent = (report.build().get("preview") or {}).get("parent")
    if not parent:
        pytest.skip("no scannable parent")

    found = assemble.parent_provenance(parent["peptide_id"],
                                       scored_campaign=str(campaign))
    assert found.get("ranked") is True, found
    assert "delta-ipTM" in found["chosen_because"], found
    assert found["ranked_against"] == str(campaign), found
    assert "ranked_choice" not in found, found


def test_a_parent_the_ranking_would_not_choose_is_named_as_such():
    campaign = _main_campaign()
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")
    from nobble.design import assemble

    found = assemble.parent_provenance("not_a_real_peptide",
                                       scored_campaign=str(campaign))
    assert found.get("ranked_choice"), found
    assert found["ranked_choice"] != "not_a_real_peptide"
    assert "was not the ranked choice" in found["status"], found
    # The reason the other one was preferred, so a refusal says what to do
    # instead rather than only that something is wrong.
    assert "ranked_because" in found, found


def test_the_campaign_to_rank_against_is_an_argument():
    """The flaw this had when it was first written.

    `report.build` reads whatever `nobble.app.data` is configured to, and
    that is global state. Called with nothing configured it ranked against
    a different campaign and preferred a different peptide, so the check
    built on top of it refused the correct parent. Found by running it both
    ways rather than only the way that was convenient, which is the only
    reason it is not in the chain now.
    """
    assert "def parent_provenance(parent_id: str, scored_campaign" in ASSEMBLE
    assert "data.configure(str(scored_campaign))" in ASSEMBLE, (
        "the campaign to rank against is accepted and not used, so the "
        "answer still depends on whatever was configured elsewhere"
    )


def test_an_undeterminable_reason_is_a_status_not_an_empty_dict():
    """"Nobody asked" and "asked and could not tell" must differ."""
    window = ASSEMBLE[ASSEMBLE.index("def parent_provenance"):]
    window = window[:window.index("\ndef ", 10)]
    assert 'return {"status": f"could not be determined ' in window, (
        "a failure to determine the reason returns something that reads "
        "like an answer"
    )
    assert "return {}" not in window


def test_the_script_checks_the_parent_before_spending_the_jobs():
    assert "is the parent still the ranked choice" in SCRIPT
    check = SCRIPT.index("is the parent still the ranked choice")
    runner = SCRIPT.index("nobble.execute.runner")
    assert check < runner, (
        "the parent is checked after the 240 jobs have been run, which is "
        "the one ordering that cannot help"
    )


def test_the_script_ranks_against_the_main_campaign():
    assert 'SCORED="$(nobble_newest_complete campaign || true)"' in SCRIPT, (
        "the script does not name the campaign to rank against, so the "
        "check inherits whatever the data layer defaults to: the bug this "
        "whole file exists because of"
    )
    assert "scored_campaign='$SCORED'" in SCRIPT
    # And it must not rank against the design campaign, which holds the
    # parent under test and would make the question circular.
    assert "scored_campaign='$CAMPAIGN'" not in SCRIPT


def test_the_script_says_so_when_it_cannot_check():
    """Running the scan unchecked is a decision and reads as one."""
    assert "no complete main campaign to rank against" in SCRIPT
    assert "running the scan without that check" in SCRIPT


def test_the_design_campaign_on_disk_is_the_case_this_is_about():
    """Not a hypothetical: the campaign queued right now.

    Assembled before the main campaign scored, and its `campaign.json`
    carries no provenance because it predates this change. The check in
    `run_design.sh` is what covers it, because that asks the question
    against today's data rather than trusting the file.
    """
    found = sorted(ROOT.glob("campaigns/design_*"))
    if not found:
        pytest.skip("no design campaign on this checkout")
    meta = json.loads((found[-1] / "campaign.json").read_text())
    assert meta.get("parent"), meta
    if "parent_provenance" in meta:
        # Assembled after this change, so it must say something real.
        assert meta["parent_provenance"], meta
