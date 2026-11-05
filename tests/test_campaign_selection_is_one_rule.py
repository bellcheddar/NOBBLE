"""One rule for "the newest campaign", in each language (F190).

A campaign is complete when it has written `campaign.json`, which every
assembler writes last. `ls -d campaigns/<prefix>_* | tail -1` names the
newest *directory* instead, and a failed assembly leaves one holding an empty
`yaml/` and an empty `outputs/`. Three of those sat in `campaigns/` from a
failing design scan and the newest was what the chain would have handed to
`run_design.sh`, which is F57.

F57 was fixed in `run_chain.sh` and nowhere else. `refresh.sh` used the naive
form twice, `run_corrected.sh` and `run_design.sh` once each: the lesson
learned in one file out of four, which is the shape F172 asked me to stop
repeating. The rule now lives in `tools/newest_complete.sh`, sourced the way
`tools/wait_for_gpu.sh` already is, and `campaign.latest()` is the same rule
on the Python side.

These tests enumerate the category. Any shell script that selects a campaign
must use the helper, and none may use the naive form, so the next script
written cannot quietly reintroduce it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "newest_complete.sh"
SHELL_SCRIPTS = sorted((ROOT / "tools").glob("*.sh")) + sorted((ROOT / "deploy").glob("*.sh"))

# The naive rule, in the spellings the project actually used.
NAIVE = re.compile(r"ls\s+-d\s+campaigns/")


def test_the_helper_exists_and_defines_one_function():
    source = HELPER.read_text()
    assert "nobble_newest_complete()" in source
    assert "campaign.json" in source, (
        "the helper no longer judges completeness by campaign.json, which is "
        "the file every assembler writes last"
    )


def test_no_script_selects_a_campaign_the_naive_way():
    offenders = {}
    for script in SHELL_SCRIPTS:
        for number, line in enumerate(script.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue            # the comments explain the naive form
            if NAIVE.search(stripped):
                offenders.setdefault(script.name, []).append(f"{number}: {stripped[:70]}")
    assert not offenders, (
        "scripts naming the newest campaign directory rather than the newest "
        f"complete one: {offenders}. Source tools/newest_complete.sh and call "
        "nobble_newest_complete."
    )


def test_every_script_that_selects_a_campaign_sources_the_helper():
    """The other direction: using the helper without sourcing it is a no-op."""
    for script in SHELL_SCRIPTS:
        text = script.read_text()
        if "nobble_newest_complete" not in text:
            continue
        if script.name == HELPER.name:
            continue
        assert "newest_complete.sh" in text, (
            f"{script.name} calls nobble_newest_complete without sourcing the "
            "helper, so it would run as an unset command"
        )


def test_the_helper_prefers_a_complete_campaign_over_a_newer_incomplete_one(tmp_path):
    """The failure F57 recorded, reproduced and then prevented."""
    campaigns = tmp_path / "campaigns"
    for stamp, complete in (("20260101T000000Z", True),
                            ("20260202T000000Z", True),
                            ("20260303T000000Z", False)):
        directory = campaigns / f"design_{stamp}"
        (directory / "yaml").mkdir(parents=True)
        if complete:
            (directory / "campaign.json").write_text("{}")

    script = f'source {HELPER}; nobble_newest_complete design'
    done = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith("design_20260202T000000Z"), done.stdout

    naive = subprocess.run(["bash", "-c", "ls -d campaigns/design_* | tail -1"],
                           cwd=tmp_path, capture_output=True, text=True)
    assert naive.stdout.strip().endswith("design_20260303T000000Z"), (
        "the naive rule no longer picks the incomplete campaign, so this test "
        "is no longer demonstrating the difference"
    )


def test_the_helper_says_nothing_and_fails_when_there_is_no_campaign(tmp_path):
    """So a caller can tell "none" from "the newest" without parsing a message.

    The naive form cannot: with no match the glob is left unexpanded and
    `ls -d` prints an error, so the variable ends up holding a path that does
    not exist.
    """
    (tmp_path / "campaigns").mkdir()
    done = subprocess.run(["bash", "-c", f"source {HELPER}; nobble_newest_complete design"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert done.returncode == 1
    assert done.stdout.strip() == ""


def test_the_corrected_runner_reports_its_own_exit_status(tmp_path):
    """`exit=$?` after a command substitution reports the substitution's status.

    `run_corrected.sh` logged `=== finished $(date ...) exit=$? ===`, and
    expansion is left to right, so `$(date ...)` ran a subshell and set `$?`
    before it was read: the line said exit=0 whether the runner succeeded or
    failed, and `status.sh` scans these logs for failures that exit=0 cannot
    match (F190).
    """
    # Comments stripped first. The comment above the fix quotes the bug it
    # describes, so a search of the whole file matched the explanation of why
    # the bug is gone. That is the fourth check today to match prose rather
    # than code, after the two in F175 and the one in F177, and the remedy is
    # the same every time.
    lines = [line for line in (ROOT / "tools" / "run_corrected.sh").read_text().splitlines()
             if not line.strip().startswith("#")]
    text = "\n".join(lines)
    assert "exit=$?" not in text, (
        "the status is read inline again, where a command substitution on the "
        "same line clobbers it"
    )
    assert "STATUS=$?" in text

    # And the behaviour the fix depends on, demonstrated rather than asserted.
    clobbered = subprocess.run(
        ["bash", "-c", 'false; echo "x $(true) exit=$?"'],
        capture_output=True, text=True)
    assert clobbered.stdout.strip().endswith("exit=0")
    captured = subprocess.run(
        ["bash", "-c", 'false; s=$?; echo "x $(true) exit=$s"'],
        capture_output=True, text=True)
    assert captured.stdout.strip().endswith("exit=1")
