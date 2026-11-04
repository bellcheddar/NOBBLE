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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = (ROOT / "PROGRESS.md").read_text()


def _git(*args: str) -> str:
    done = subprocess.run(("git",) + args, cwd=ROOT,
                          capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ""


def test_the_unpushed_count_is_the_real_one():
    stated = re.search(r"G4 Publish\*\*: (\d+) commits unpushed", PROGRESS)
    if not stated:
        raise AssertionError(
            "PROGRESS.md no longer states an unpushed commit count in the "
            "form this checks, so the figure is unpinned again"
        )
    actual = _git("rev-list", "--count", "origin/main..HEAD")
    if not actual:
        return          # no origin ref on this checkout
    assert int(stated.group(1)) == int(actual), (
        f"PROGRESS.md says {stated.group(1)} commits unpushed and there are "
        f"{actual}. A count typed into a handover is stale the next time "
        "anyone commits."
    )


def test_the_published_path_count_is_the_real_one():
    stated = re.search(r"carries (\d+) of the absolute project paths", PROGRESS)
    if not stated:
        raise AssertionError("the published-path figure is no longer stated")
    output = _git("grep", "-c", "/Users/dellboy", "origin/main",
                  "--", "deploy/atlas")
    if not output:
        return          # cannot inspect origin/main on this checkout
    actual = sum(int(line.rsplit(":", 1)[1])
                 for line in output.splitlines() if ":" in line)
    assert int(stated.group(1)) == actual, (
        f"PROGRESS.md says {stated.group(1)} absolute paths on origin/main "
        f"and there are {actual}"
    )


def test_the_table_still_names_all_three_pending_items():
    """A handover that loses an item is worse than one with a stale number."""
    section = PROGRESS[PROGRESS.index("## Waiting on Marc"):]
    section = section[:section.index("\n## ", 3)]
    for item in ("G1", "G4", "enable_gzip.sh"):
        assert item in section, f"the pending-items table no longer names {item}"
