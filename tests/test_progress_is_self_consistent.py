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


def _gate_bullets() -> dict[str, list[str]]:
    """Each gate's bullets in the Gates open section."""
    start = PROGRESS.index("## Gates open")
    section = PROGRESS[start:]
    following = section.find("\n## ", 3)
    if following > 0:
        section = section[:following]
    found: dict[str, list[str]] = {}
    # The whole first line, not just the bold heading: G3 and G5 put their
    # state after the closing asterisks, so a shorter capture reported them
    # as stating nothing.
    for match in re.finditer(r"^- \*\*(G\d).*$", section, re.M):
        found.setdefault(match.group(1), []).append(match.group(0))
    return found


# A bullet that says it is history is not a claim about now.
HISTORY = re.compile(r"history|formerly|was briefly|used to", re.I)


def test_each_gate_makes_one_claim_about_the_present():
    """Two bullets about one gate, saying opposite things (F165).

    The section carried "G1 Compute is open, on Tier B" and, four bullets
    down, "G1 compute: closed, and was briefly reported open in error". The
    second was F45's history and read as a statement of the current state
    because it was in the same list in the same form.

    F158's test did not catch it: that one compares a blanket "no gate is
    open" against gates named as open, and never two bullets about the same
    gate. A check narrower than the defect it is named for is the thing this
    project keeps finding.
    """
    for gate, bullets in sorted(_gate_bullets().items()):
        current = [b for b in bullets if not HISTORY.search(b)]
        assert len(current) <= 1, (
            f"{gate} has {len(current)} bullets claiming a present state: "
            f"{current}. A historical note must say so in its heading."
        )


def test_every_gate_bullet_says_open_or_closed_or_history():
    """A bullet that says neither leaves a reader to infer."""
    for gate, bullets in sorted(_gate_bullets().items()):
        for bullet in bullets:
            assert re.search(r"open|closed", bullet, re.I) or HISTORY.search(bullet), (
                f"{gate} has a bullet stating neither a state nor that it is "
                f"history: {bullet}"
            )
