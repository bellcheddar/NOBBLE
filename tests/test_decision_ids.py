"""Every decision has one number, and every cited number has a decision.

I collided twice in one session. The first time I grepped
`^## D-NOB-03[0-9]`, saw 039 as the highest and wrote D-NOB-040 and 041,
which already existed: "the design scan picks its target after the main
campaign" and "the site is not republished while a campaign is running", the
second cited by name in `run_chain.sh`. Renumbering to 050 and 051 collided
again, because those exist too.

The IDs are not contiguous. There are 51 of them, the highest is 59, and
1 to 7 and 45 are unused. Nothing checked, so a duplicate was silent and a
reader following a citation would land on whichever entry came first.

Measured rather than guessed now, and checked here (F113).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DECISIONS = ROOT / "DECISIONS.md"
# Two forms, and missing the second is what made me think 1 to 7 were free.
# D-NOB-001 to 007 came from the spec and sit in a table at the top of the
# file; everything decided during the build is a `## D-NOB-NNN` heading. A
# pattern that sees only one form reports the other as unused, which is the
# same incomplete-grep mistake that caused the collision this file exists to
# prevent.
HEADING = re.compile(r"^## D-NOB-(\d+)[.:]?\s*(.*)$", re.M)
TABLE_ROW = re.compile(r"^\|\s*D-NOB-(\d+)\s*\|\s*([^|]*)\|", re.M)
CITATION = re.compile(r"D-NOB-(\d+)")


def _headings() -> dict[int, list[str]]:
    found: dict[int, list[str]] = {}
    text = DECISIONS.read_text()
    for pattern in (HEADING, TABLE_ROW):
        for match in pattern.finditer(text):
            found.setdefault(int(match.group(1)), []).append(match.group(2).strip())
    return found


def test_no_number_is_used_twice():
    duplicates = {number: titles for number, titles in _headings().items()
                  if len(titles) > 1}
    assert not duplicates, duplicates


def test_there_are_decisions_to_check():
    """So the tests here cannot pass by finding nothing, which is the vacuous
    shape that has caught me three times today."""
    headings = _headings()
    assert len(headings) > 40, len(headings)


def test_both_forms_are_seen():
    """The table rows and the headings. Reading only one is what produced
    the collision."""
    headings = _headings()
    assert 1 in headings, "the spec's own table rows are not being read"
    assert 7 in headings and "widened in place" in headings[7][0], headings.get(7)
    assert 61 in headings, "the newest heading is not being read"


def test_every_number_cited_in_code_has_a_decision():
    """A citation pointing at nothing is worse than no citation: it reads as
    a reason that was written down."""
    known = set(_headings())
    dangling = {}
    for pattern in ("*.py", "*.sh", "*.toml", "*.html"):
        for path in sorted(ROOT.rglob(pattern)):
            parts = set(path.parts)
            if parts & {".pixi", "vendor", "__pycache__", ".git", "node_modules"}:
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            for cited in CITATION.findall(text):
                if int(cited) not in known:
                    dangling.setdefault(
                        str(path.relative_to(ROOT)), set()).add(f"D-NOB-{cited}")
    assert not dangling, {k: sorted(v) for k, v in dangling.items()}


def test_every_number_cited_in_the_logs_has_a_decision():
    known = set(_headings())
    dangling = {}
    for name in ("FINDINGS.md", "PROGRESS.md", "BUILD_LOG.md", "DESIGN_ARM.md",
                 "README.md", "DEPLOYED.md"):
        path = ROOT / name
        if not path.exists():
            continue
        for cited in CITATION.findall(path.read_text()):
            if int(cited) not in known:
                dangling.setdefault(name, set()).add(f"D-NOB-{cited}")
    assert not dangling, {k: sorted(v) for k, v in dangling.items()}


def test_a_new_decision_goes_above_the_highest_rather_than_into_a_gap():
    """The gaps are not free space. 1 to 7 and 45 are unused, and a gap
    exists because something was withdrawn or renumbered, so reusing one
    makes an old citation point at a new decision."""
    headings = _headings()
    highest = max(headings)
    gaps = [number for number in range(1, highest) if number not in headings]
    # Recorded as a fact rather than enforced, since filling a gap
    # deliberately is a choice someone may make with a reason. Once both
    # forms are read there is one gap, 45, and not the seven I first thought.
    assert gaps == [45], gaps
    assert highest >= 61, highest
