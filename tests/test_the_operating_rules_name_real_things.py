"""CLAUDE.md's operating rules point at things that exist (F311, F324b).

The rules were added after three failures on 2026-11-07. A rule that names a
script which has been renamed, or a tool which no longer takes the flag it
cites, is worse than no rule: it reads as current and is not. This checks the
nouns, not the prose.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = (ROOT / "CLAUDE.md").read_text()
SECTION = RULES[RULES.index("## Operating rules"):RULES.index("## Gates")]


def test_every_script_the_first_rule_protects_exists():
    """The list is the chain's own scripts, so a rename must update it."""
    named = ("run_chain.sh", "tier2.sh", "refresh.sh", "corrections.sh",
             "run_queue.sh", "wait_for_gpu.sh")
    missing = [name for name in named if not (ROOT / "tools" / name).exists()]
    assert not missing, f"the rule names scripts that are gone: {missing}"


def test_the_chain_still_calls_each_of_them():
    """A script that exists and is no longer in the chain's path does not
    need protecting, and listing it dilutes the rule."""
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    reached = (ROOT / "tools" / "tier2.sh").read_text() \
        + (ROOT / "tools" / "refresh.sh").read_text() \
        + (ROOT / "tools" / "corrections.sh").read_text()
    for name in ("tier2.sh", "refresh.sh", "corrections.sh"):
        assert name in chain, f"run_chain.sh no longer calls {name}"
    for name in ("run_queue.sh", "wait_for_gpu.sh"):
        assert name in chain or name in reached, (
            f"{name} is not reached from the chain any more")


def test_the_second_rule_s_command_works():
    """`tools/findings.py --grep` is the whole point of the rule."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "findings.py"),
         "--grep", "sync.conflict"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr
    assert "finding(s) match" in done.stdout


def test_the_second_rule_s_findings_are_the_ones_it_cites():
    """F173 and F186 are the record the rule says to search for, so they
    have to be findable by the search it recommends."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "findings.py"),
         "--grep", "sync.conflict|icloud"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    assert "F173" in done.stdout, done.stdout
    assert "F186" in done.stdout, done.stdout


def test_the_third_rule_s_numbers_are_not_invented():
    """330 MB and 2,515 files were measured. If the bundle has changed size
    by a lot the rule should say so rather than quote a stale figure."""
    tracked = subprocess.run(
        ["git", "ls-files", "deploy/atlas"],
        capture_output=True, text=True, cwd=ROOT, check=True)
    count = len([line for line in tracked.stdout.splitlines() if line])
    if count == 0:
        import pytest
        pytest.skip("deploy/atlas is not tracked on this checkout")
    assert count > 1000, (
        f"the rule says 2,515 tracked files and there are {count}: the "
        "reason for the rule has changed, so the rule should be re-read")


def test_each_rule_names_the_finding_that_earned_it():
    """A rule with no finding behind it is a preference, and this file is
    for the ones that cost time."""
    for finding in ("F308", "F304", "F303", "F321", "F322", "F323", "F324"):
        assert finding in SECTION, f"{finding} is not cited by any rule"
