"""The handover's figures are measured, not typed (F167).

PROGRESS.md's "Waiting on Marc" table said 160 commits unpushed. It was 202
by the time anyone read it, because a count typed into a document is stale
the next time anyone commits, and this session commits often.

The same table says `origin/main` still carries some of the absolute project
paths F128 removed, which is the reason a push does not fix that on its own.
That number moves too, in the other direction, if the branch is ever
rewritten.

Neither figure is worth a reader's trust unless something checks it, and
both are one git command away.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = (ROOT / "PROGRESS.md").read_text()


def _git(*args: str) -> str:
    done = subprocess.run(("git",) + args, cwd=ROOT,
                          capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ""


def test_the_push_row_gives_a_command_rather_than_a_number():
    """A figure that moves with every commit must not be written down (F168).

    F167 replaced two stale numbers with measured ones and pinned them with
    a test. Committing that fix incremented the unpushed count, so the test
    failed on the commit that introduced it: 202 written, 203 by the time
    anything could read it.

    A number nobody can state correctly is not a number to state. The row
    hands the reader the command instead, and this checks that it does.
    """
    section = PROGRESS[PROGRESS.index("## Waiting on Marc"):]
    section = section[:section.index("\n## ", 3)]
    push = [line for line in section.splitlines() if "G4 Publish" in line]
    assert push, "the pending-items table no longer has a G4 row"
    row = push[0]
    assert "rev-list --count origin/main..HEAD" in row, (
        "the G4 row does not say how to get the unpushed count"
    )
    assert not re.search(r"\b\d{2,} commits unpushed", row), (
        "the G4 row quotes a commit count, which is wrong the moment it is "
        "committed"
    )
    assert "git grep -c" in row, (
        "the row does not say how to count the absolute paths still on "
        "origin/main"
    )


def test_the_table_still_names_all_three_pending_items():
    """A handover that loses an item is worse than one with a stale number."""
    section = PROGRESS[PROGRESS.index("## Waiting on Marc"):]
    section = section[:section.index("\n## ", 3)]
    for item in ("G1", "G4", "enable_gzip.sh"):
        assert item in section, f"the pending-items table no longer names {item}"


def test_the_suite_size_is_a_command_not_a_number():
    """The same trap as the commit count, one turn later (F168).

    F167 replaced the stale "Suite 1,003 passing" with a measured figure and
    a test tying it to what pytest collects. Adding that test moved the
    collected count from 1,052 to 1,053, so the fix failed its own check for
    the second time in two attempts.

    The distinction that settles it: a figure that is a property of the
    *data* can be stated and checked, because it changes only when the data
    does, and 25,519 library candidates or 2,360 jobs or 285,996 bridges all
    are. A figure that is a property of the *work* changes as a consequence
    of doing the work, and writing one down is a race against oneself.
    Commits, tests and findings are all of that kind.
    """
    section = PROGRESS[PROGRESS.index("**Suite"):]
    section = section[:200]
    assert "--collect-only" in section, (
        "the suite's size is not given as a command"
    )
    assert not re.search(r"Suite [\d,]+ passing", section), (
        "the suite size is quoted as a number, which is wrong as soon as a "
        "test is added"
    )


def test_the_session_range_covers_every_finding_it_claims():
    """It said "F132 to F148, Seventeen findings" at F167."""
    stated = re.search(r"F132 to F(\d+)\.\*\*", PROGRESS)
    assert stated, "the session's finding range is no longer stated"
    highest = max(
        int(m.group(1)) for m in
        re.finditer(r"^## F(\d+)\.", (ROOT / "FINDINGS.md").read_text(), re.M))
    assert int(stated.group(1)) == highest, (
        f"PROGRESS.md says this session runs to F{stated.group(1)} and "
        f"FINDINGS.md reaches F{highest}"
    )
