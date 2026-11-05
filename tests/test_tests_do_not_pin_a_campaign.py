"""Eighteen test files named a campaign directory by its timestamp.

A pinned name is right until the campaign it names is superseded or pruned,
and then the test does not fail: it finds nothing, its `.exists()` guard
returns false, and it skips. Nothing reports that a check stopped checking.
The main campaign running now will produce a new directory, and G5 prunes
old ones when disk gets tight, so both triggers were in the diary.

Found by reading the skip list rather than the code.
`test_the_live_tier2_queue_shares_the_tier1_yaml` skipped with "tier 2 has
not been selected on this checkout" while the benchmark campaign had held a
ten-row `queue_tier2.jsonl` the whole time: it was keyed on the main
campaign's pinned name. One visible skip, seventeen more files behind it.

They now resolve through `campaign.latest_or_absent(prefix)`, which is
`campaign.latest` returning a path that does not exist rather than None, so
every existing `.exists()` guard keeps its meaning while the campaign in
use is the newest complete one. One definition, in the module that already
owns the rule, rather than a copy per test file, which is what F181, F183
and F187 were each about. The same rule in the shell is
`tools/newest_complete.sh`, from F190.

This is the guard. One reference remains, listed with its reason,
because it is not a read of live campaign data. The docstring in
test_tier2_refines_what_it_selected.py also names a campaign, in
backticks rather than as a path expression, and the pattern does not
reach prose.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TESTS = ROOT / "tests"
# A dated campaign directory name: <prefix>_<ISO timestamp>.
DATED = r"(?:benchmark|campaign|corrected|design|smoke|zinc)_\d{8}T\d{6}Z"
# Only a name joined to the project's real campaigns directory counts.
#
# The first version of this matched any dated name anywhere in a test, and
# flagged nine files that invent one inside a tmp_path fixture: a synthetic
# `design_20260101T000000Z` written by the test itself is the test's own
# data and has nothing to do with what is on disk. Keying on the real root
# is what separates "reads a campaign that may be pruned" from "makes one
# up", and it is the same set of spellings the rewrite replaced.
PINNED = re.compile(
    r"ROOT\s*/\s*\"campaigns\"\s*/\s*\"" + DATED + r"\""
    r"|paths\.CAMPAIGNS\s*/\s*\"" + DATED + r"\""
    r"|\"campaigns/" + DATED
)

ALLOWED = {
    "test_mutation_harness.py":
        "a string handed to mutate._refuse_protected, which matches on the "
        "path's shape and reads nothing from disk",
}


def _offenders() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(TESTS.glob("test_*.py")):
        names = sorted({m.group(0) for m in PINNED.finditer(path.read_text())})
        if names:
            found[path.name] = names
    return found


def test_no_test_names_a_campaign_directory():
    unexplained = {name: hits for name, hits in _offenders().items()
                   if name not in ALLOWED}
    assert not unexplained, (
        "test(s) naming a campaign directory by its timestamp, which will "
        "skip silently once that campaign is superseded or pruned. Resolve "
        f"it with campaign.latest_or_absent(prefix) instead: {unexplained}"
    )


def test_the_allowances_are_all_still_real():
    """An allowlist that outlives what it allows is a hole, which is the
    shape tests/test_template_cutoffs.py already guards for cutoffs."""
    present = _offenders()
    stale = [name for name in ALLOWED if name not in present]
    assert not stale, f"ALLOWED names files that no longer pin one: {stale}"


def test_the_resolver_finds_the_campaigns_that_are_here():
    """Otherwise the sweep above passes while every test it governs skips,
    which is the failure it exists to prevent rather than detect."""
    from nobble.execute.campaign import latest, latest_or_absent

    for prefix in ("benchmark", "campaign"):
        resolved = latest_or_absent(prefix)
        assert resolved == latest(prefix), prefix
        assert resolved.exists(), (
            f"no complete {prefix} campaign on this checkout, so the tests "
            "that read one are skipping"
        )


def test_an_absent_prefix_gives_a_path_that_does_not_exist():
    """The contract the `.exists()` guards rely on: never None, never a
    directory that happens to be there."""
    from nobble.execute.campaign import latest_or_absent

    missing = latest_or_absent("nosuchprefix")
    assert isinstance(missing, Path)
    assert not missing.exists()
    assert "nosuchprefix" in missing.name
