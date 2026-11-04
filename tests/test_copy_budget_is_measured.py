"""CLAUDE.md's copy budget is a rule nothing measured (F139).

"Keep narrative prose in the app to a minimum. One short line per panel
saying what it shows or what the number means. Reasoning belongs in
DECISIONS.md and FINDINGS.md, not on screen. Budget: under 40 words per
panel, under 150 per page, excluding tables, labels and pipeline-generated
status text."

Unmeasured for the whole build, and `/pose` had drifted to 49 words of
presentation provenance on screen, which is precisely the reasoning the rule
sends to DECISIONS.md.

The measurement needs a browser, because the rule is about what a reader
sees: a static count over the templates sums paragraphs that are mutually
exclusive in the rendered page, and it called the composite panel 124 words
where a reader sees 23. So it lives in `qc/copy_budget.mjs` and runs inside
browser QC, and these are the checks that it is wired and that the
exclusions are the rule's rather than whatever made the numbers pass.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "qc" / "copy_budget.mjs"
HARNESS = ROOT / "qc" / "qc.mjs"


def test_the_tool_exists_and_states_the_budget():
    source = TOOL.read_text()
    assert "> 40" in source and "> 150" in source, (
        "the tool no longer compares against the budget CLAUDE.md states"
    )


def test_browser_qc_runs_it_and_keys_on_its_exit_code():
    harness = HARNESS.read_text()
    assert "copy_budget.mjs" in harness, "browser QC does not run the measurement"
    assert "e.status === 4" in harness, (
        "qc.mjs does not distinguish an over-budget run from a failed one, so "
        "a crash in the tool would read as a page within budget"
    )
    assert "copyBudget" in harness.split("console.log('pages captured")[1], (
        "the result is measured and not reported in the summary"
    )


def test_the_tool_exits_non_zero_when_over_budget():
    assert "process.exit(4)" in TOOL.read_text()


def test_the_exclusions_are_the_rule_s_own():
    """Each exclusion has to be one the rule names, not one that made the
    numbers pass.

    The rule excludes tables, labels and pipeline-generated status text. The
    markup already separates all three, so each exclusion points at an
    existing class rather than at a word count.
    """
    source = TOOL.read_text()
    for marker, why in (
        ("closest('table')", "tables, which the rule excludes"),
        ("weight__note", "a label on a control, and its aria-describedby"),
        ("mono", "machine output, the pipeline-generated status text"),
        ("closest('.empty')", "an empty state, which is transient"),
    ):
        assert marker in source, f"{marker} is no longer excluded: {why}"


def test_about_is_exempt_and_says_so():
    """The one exemption, which is a decision and not an oversight."""
    source = TOOL.read_text()
    assert "EXPOSITION" in source
    assert "D-NOB-067" in source, (
        "the exemption is applied without pointing at the decision that "
        "justifies it"
    )


def test_the_reasoning_left_the_pose_panel():
    """The drift this found, pinned where it was.

    The provenance paragraph is now a Jinja comment, so it is still in the
    file for a reader of the template and no longer on screen.
    """
    page = (ROOT / "nobble" / "app" / "templates" / "pose.html").read_text()
    rendered = re.sub(r"\{#.*?#\}", " ", page, flags=re.S)
    assert "four-band pLDDT scale" not in rendered, (
        "the presentation provenance is back on screen"
    )
    assert "four-band pLDDT scale" in page, (
        "it was deleted rather than moved into a comment, so a reader of the "
        "template has lost why the viewer looks the way it does"
    )
