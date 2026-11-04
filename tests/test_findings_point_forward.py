"""A finding that was revised later has to say so (F164).

FINDINGS.md is the document of record, read from the top by anyone tracing
why something is the way it is. Nine findings from one session were revised
by later ones and not one pointed forward, so a reader of F134 would conclude
Tier B costs 16.5 hours and stop, where F163 says it cannot be assembled at
all; a reader of F142 would conclude the runner's appends are told from a
rewrite, where F154 says an identical rewrite was reported as an append.

This is F158's defect across findings rather than within PROGRESS.md: two
statements written deliberately, each true when written, with nothing
comparing them, and the one a reader reaches first being the stale one.

The convention is a `**Revised by FNNN:**` line at the end of the earlier
finding. The relation is maintained here rather than inferred, because
"this finding revises that one" is a judgement and a regex guessing at it
would either miss revisions or invent them. What the test guarantees is that
the relation, once recorded, stays symmetric and keeps pointing somewhere
real.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = (ROOT / "FINDINGS.md").read_text()

# earlier finding -> the findings that revised it.
REVISED = {
    134: [163],
    135: [161],
    138: [159, 162],
    139: [159, 160],
    142: [154],
    147: [160],
    153: [155],
}


def _bodies() -> dict[int, str]:
    heads = [(m.start(), int(m.group(1)))
             for m in re.finditer(r"^## F(\d+)\.", FINDINGS, re.M)]
    out = {}
    for index, (start, number) in enumerate(heads):
        end = heads[index + 1][0] if index + 1 < len(heads) else len(FINDINGS)
        out[number] = FINDINGS[start:end]
    return out


def test_every_revised_finding_points_forward():
    bodies = _bodies()
    for earlier, later in sorted(REVISED.items()):
        body = bodies.get(earlier)
        assert body, f"F{earlier} is not in FINDINGS.md"
        assert "**Revised by" in body, (
            f"F{earlier} was revised by {later} and does not say so, so a "
            "reader who stops there has the superseded answer"
        )
        for number in later:
            assert f"F{number}" in body, (
                f"F{earlier}'s revision note does not name F{number}"
            )


def test_the_revision_note_is_last_so_it_is_not_missed():
    """At the end of the finding, where a reader who read it will be."""
    bodies = _bodies()
    for earlier in sorted(REVISED):
        body = bodies[earlier].rstrip()
        tail = body[-400:]
        assert "**Revised by" in tail, (
            f"F{earlier}'s revision note is buried in the middle of it"
        )


def test_both_ends_of_every_recorded_revision_exist():
    """A note pointing at a finding that does not exist is worse than none."""
    numbers = {int(m.group(1))
               for m in re.finditer(r"^## F(\d+)\.", FINDINGS, re.M)}
    for earlier, later in sorted(REVISED.items()):
        assert earlier in numbers, f"F{earlier} does not exist"
        for number in later:
            assert number in numbers, (
                f"F{earlier} is recorded as revised by F{number}, which does "
                "not exist"
            )


def test_a_revision_is_not_recorded_backwards():
    """A finding cannot be revised by an earlier one."""
    for earlier, later in sorted(REVISED.items()):
        for number in later:
            assert number > earlier, (
                f"F{earlier} is recorded as revised by the earlier F{number}"
            )
