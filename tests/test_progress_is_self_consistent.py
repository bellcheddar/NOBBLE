"""PROGRESS.md must not contradict itself about the gates (F158).

It is the document that says whether the build needs a decision. F134 opened
Gate G1 on Tier B and recorded it in its own section; the "Gates open"
section further down still said "No gate is currently open. All six are
closed". Both were written deliberately and nothing compared them, so the
file answered the one question it exists to answer in two different ways,
and which answer a reader got depended on where they stopped.

Checked rather than remembered, because the next gate to open will be
recorded the same way: in a new section, by someone who does not scroll.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = (ROOT / "PROGRESS.md").read_text()

GATES = ("G1", "G2", "G3", "G4", "G5", "G6")


def _unquoted(text: str) -> str:
    """The file with quoted spans blanked.

    A check that forbids a sentence forbids its own explanation: the cell
    that used to say "No gate is currently open" now records that it said
    so, and the first version of this test fired on that record. Same
    mistake as F150's docstring and F152's conftest comment, which is three
    times now, so it is the rule rather than the exception.
    """
    return re.sub(r"\u201c[^\u201d]*\u201d|\"[^\"\n]*\"", " ", text)


def test_it_does_not_claim_no_gate_is_open_while_naming_one():
    declares_none = re.search(r"No gate is currently open", _unquoted(PROGRESS))
    opened = re.findall(r"Gate (G\d) open|(G\d) [A-Za-z]+ is open", PROGRESS)
    named = {a or b for a, b in opened}
    assert not (declares_none and named), (
        f"PROGRESS.md says no gate is open and names {sorted(named)} as open"
    )


def test_an_open_gate_is_named_in_the_gates_section():
    """A gate recorded only in its own section is a gate a reader misses.

    The "Gates open" section is where someone checks. If a gate is announced
    anywhere in the file, that section has to mention it.
    """
    announced = set(re.findall(r"Gate (G\d) open", PROGRESS))
    if not announced:
        return
    start = PROGRESS.index("## Gates open")
    section = PROGRESS[start:]
    next_heading = section.find("\n## ", 3)
    if next_heading > 0:
        section = section[:next_heading]
    missing = [gate for gate in sorted(announced) if gate not in section]
    assert not missing, (
        f"{missing} announced as open elsewhere in PROGRESS.md and absent "
        "from the Gates open section, which is where a reader looks"
    )


def test_the_gates_section_accounts_for_all_six():
    """Six gates exist. A section that lists three says nothing about the
    other three, and CLAUDE.md names all six."""
    start = PROGRESS.index("## Gates open")
    section = PROGRESS[start:]
    next_heading = section.find("\n## ", 3)
    if next_heading > 0:
        section = section[:next_heading]
    accounted = [gate for gate in GATES if gate in section]
    assert len(accounted) >= 3 or "other five gates are closed" in section \
        or "All six are closed" in section, (
        f"the Gates open section names only {accounted} of six and does not "
        "say what the rest are"
    )
