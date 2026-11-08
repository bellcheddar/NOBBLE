"""A tool whose docstring says it writes nothing must not write (F326d).

`--limit` on the scorer cost 157 scored pairs because a command that reads
like an inspection writes. Five tools in this project say in their own
docstrings that they write nothing, and four of them were written today by
the same person who then ran a truncating flag at a live campaign.

So the claim is checked rather than trusted. This is F218's shape applied to
my own prose: a guarantee stated in a docstring, with nothing behind it,
about the one property a reader would rely on before pointing the tool at
real data.

Checked by parsing rather than grepping, so `write_text` inside a string or a
comment does not count and a call through an alias does.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Each of these says so in its module docstring.
READ_ONLY = (
    "bridge_on_crystals.py",
    "composite_crossval.py",
    "scramble_paired_test.py",
    "matched_arm_stratified.py",
    "findings.py",
)

# Attribute calls that put bytes on disk or take them off it.
WRITES = {"write_text", "write_bytes", "unlink", "mkdir", "rmdir", "rename",
          "replace", "touch", "copy", "copy2", "copytree", "move", "rmtree",
          "writelines"}


def _writes_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in WRITES:
            found.append(f"{node.func.attr} at line {node.lineno}")
        # open(..., "w") and friends.
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            for argument in list(node.args[1:]) + [
                    kw.value for kw in node.keywords if kw.arg == "mode"]:
                if (isinstance(argument, ast.Constant)
                        and isinstance(argument.value, str)
                        and any(ch in argument.value for ch in "wxa+")):
                    found.append(f"open(mode={argument.value!r}) at line "
                                 f"{node.lineno}")
    return found


def test_each_one_says_something_about_writing():
    """The premise, as a claim rather than a phrasing.

    The first version asked for the literal "writes nothing" and failed on
    `findings.py`, which says "Nothing is written". Four tools say it one way
    and one says it the other, and normalising the prose to satisfy a test
    would be the test dictating the code. So this asks that each one
    addresses writing at all: a tool silently added to the list without
    claiming anything is the staleness worth catching, and whether it says
    "writes nothing" or "nothing is written" is not.
    """
    missing = []
    for name in READ_ONLY:
        path = ROOT / "tools" / name
        if not path.exists():
            missing.append(f"{name} is gone")
            continue
        text = (ast.get_docstring(ast.parse(path.read_text())) or "").lower()
        if "writ" not in text:
            missing.append(f"{name}'s docstring says nothing about writing, "
                           "so its presence in this list rests on nothing")
    assert not missing, missing


def test_none_of_them_writes():
    offenders = {}
    for name in READ_ONLY:
        path = ROOT / "tools" / name
        if not path.exists():
            continue
        found = _writes_in(path)
        if found:
            offenders[name] = found
    assert not offenders, (
        f"tools that say they write nothing and do: {offenders}. Either the "
        "write is wrong or the docstring is"
    )


def test_the_check_can_see_a_write():
    """Otherwise the test above passes by looking for nothing, which is the
    shape it exists to catch."""
    probe = ROOT / "tools" / "clean_sync_conflicts.py"
    if not probe.exists():
        pytest.skip("no writing tool to calibrate against")
    # This one deletes on purpose and says so, which is why it is the
    # calibration rather than a failure.
    assert _writes_in(probe), (
        "the detector finds no write in a tool that unlinks files, so it "
        "would not find one anywhere"
    )
