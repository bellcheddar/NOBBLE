"""The status page showed half of Gate G1 (F143).

`tools/status.sh` reported G1 from `projected_hours`, which prices tier 1.
Refinement was priced nowhere a reader looks: the decile cost 29 to 219 hours
against 71 remaining and the gates section said "G1 compute closed". The gate
was computed by `nobble.execute.budget` since F135 and not surfaced, and for
a status page that is most of the way to not being computed.

Three things it had to get right, each of which I got wrong first and fixed
against the real campaign.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = (ROOT / "tools" / "status.sh").read_text()


def test_both_halves_of_g1_are_reported():
    assert "G1 tier 1" in STATUS
    assert "G1 refine" in STATUS, (
        "the gates section prices tier 1 only, which is the gap F135 found "
        "in the projection itself"
    )


def test_the_refinement_price_is_scoped_to_the_decile():
    """Pricing every ternary job said 159 to 1,190 hours.

    Refinement only ever runs on the top decile, so pricing the whole
    campaign answers a question nobody asks and reads as a gate about to
    stop the build.
    """
    assert "DECILE_FRACTION" in STATUS


def test_the_decile_is_sized_from_the_campaign_not_from_the_last_selection():
    """tier2.json answers a different question.

    The recorded selection says what the last selection cost. A status page
    is asked what refinement will cost, and the two diverge as soon as
    scoring advances: the selection on the running campaign was taken
    against the six pairs scored at the time and names one pair, where the
    finished campaign's decile is sixteen.
    """
    section = STATUS[STATUS.index("-- gates"):]
    # Comments stripped: the comment that explains why the recorded
    # selection is not read names the file, and forbidding the name outright
    # would forbid the explanation.
    code = "\n".join(line for line in section.splitlines()
                     if not line.lstrip().startswith("#"))
    assert "tier2.json" not in code, (
        "the status page reads the recorded selection, so it reports the "
        "cost of the last selection rather than of the next one"
    )
    assert "tier2.json" in section, (
        "nothing says why the recorded selection is the wrong source, so the "
        "next reader will wire it back in"
    )


def test_it_says_what_happens_after_reduction():
    """An OPEN on the full decile does not stop the chain.

    tier2.run drops pairs from the bottom of the ranking until the rest
    fits, and only an empty result opens the gate for real. A line that
    says only OPEN reads as a halt.
    """
    assert "after reduction" in STATUS
    assert "affordable_pairs" in STATUS


def test_the_slice_is_labelled_as_a_size_and_not_as_the_ranking():
    """Which pairs are in the decile needs the scores.

    Before they exist this is the decile's size, and claiming it is the
    ranking would name pairs that are not the ones that will be refined.
    """
    assert "not the ranking" in STATUS


def test_the_chain_s_note_on_deploy_is_current():
    """A comment a reader relies on.

    run_chain.sh said deploy.sh refuses success unless all nine routes
    answer 200, which was the whole check until F140 added the build
    comparison.
    """
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    deploy_note = chain[chain.index("# Deploying is the point"):]
    deploy_note = deploy_note[:deploy_note.index("say \"deploying\"")]
    assert "fingerprint" in deploy_note, (
        "the chain still describes the deploy check as routes only"
    )
