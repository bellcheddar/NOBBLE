"""What PROGRESS asks of Marc must not contradict what it says is closed.

The "Waiting on Marc" table asked for the fifteen receptor constructs Tier B
needs, under a document whose own heading four sections earlier reads "Gate G1
closed: Tier B is assembled and queued". A reader acting on the table would
have gone looking for a decision Marc made on 2026-11-05 (D-NOB-072) and the
chain has since queued 1,540 jobs against (F290).

This asserts the property rather than the wording: no row of that table may
ask for something a closed-gate heading says is done.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "PROGRESS.md"


def _section(name: str) -> str:
    text = PROGRESS.read_text()
    start = text.index(f"## {name}")
    end = text.find("\n## ", start + 4)
    return text[start:end if end > 0 else len(text)]


def test_the_table_does_not_ask_for_what_a_closed_gate_provided():
    waiting = _section("Waiting on Marc")
    closed = [line for line in PROGRESS.read_text().splitlines()
              if line.startswith("## Gate ") and "closed" in line.lower()]
    assert closed, "no closed gate is recorded, so this check has no subject"
    for heading in closed:
        gate = re.search(r"Gate (G\d)", heading)
        if not gate:
            continue
        rows = [line for line in waiting.splitlines()
                if line.startswith("|") and gate.group(1) in line]
        for row in rows:
            assert "answered" in row.lower() or "record" in row.lower(), (
                f"{heading!r} says the gate is closed and the waiting table "
                f"still asks for it: {row[:120]}")


def test_the_count_matches_the_open_rows():
    """The prose says how many items are open; the table says which."""
    waiting = _section("Waiting on Marc")
    rows = [line for line in waiting.splitlines()
            if line.startswith("|") and "---" not in line
            and not line.startswith("| Item")]
    open_rows = [row for row in rows if "answered" not in row.lower()]
    stated = re.search(r"^(One|Two|Three|Four) items?", waiting, re.M)
    if not stated:
        pytest.skip("the section no longer states a count")
    words = {"One": 1, "Two": 2, "Three": 3, "Four": 4}
    assert words[stated.group(1)] == len(open_rows), (
        f"the prose says {stated.group(1).lower()} open item(s) and the table "
        f"has {len(open_rows)}: {[r[:60] for r in open_rows]}")


def test_the_next_manual_step_is_named():
    """A command, not a question, so it is not in the table.

    Whoever picks this up should not have to reconstruct the order of the two
    corrections and the refresh from three findings.
    """
    waiting = _section("Waiting on Marc")
    assert "tools/corrections.sh" in waiting, (
        "PROGRESS does not name the command that clears the atlas build's "
        "refusals")
