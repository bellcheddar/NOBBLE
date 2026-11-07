"""The findings lookup reads the file, so it cannot go stale.

FINDINGS.md is 14,000 lines and 291 numbers, and the code cites them
constantly: a comment says F219 and expects the reader to find it. On
7 November I re-ran a sweep whose finding was four hours old because looking
it up meant grepping (F291).

`tools/findings.py` computes its index on every call and writes nothing,
which is why it is a tool rather than a section at the top of the document:
an index in the file would be one more thing to keep in step with an
append-only log.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "findings_tool", ROOT / "tools" / "findings.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_finding_heading_is_parsed():
    """The count is asserted against the file, not against a literal.

    A pattern that stops matching reports fewer findings rather than an
    error, which is the failure this project keeps finding in its own
    measurements.
    """
    import re

    module = _module()
    entries = module.entries()
    text = (ROOT / "FINDINGS.md").read_text()
    # `F` followed by a digit. The first version counted every line starting
    # "## F", which includes prose headings such as "## From the parser
    # source", so it reported more headings than there are findings and
    # failed on its own counter rather than on the tool.
    headings = len(re.findall(r"^#{2,3}\s*F\d", text, re.M))
    assert len(entries) == headings, (
        f"parsed {len(entries)} of {headings} heading(s): the pattern has "
        "narrowed")


def test_a_lettered_sub_finding_is_its_own_label():
    """F2b is not a second F2.

    The first version of `--check` grouped by number and reported F2 and F4
    as unexplained repeats, because F2b and F4a sit at the same heading
    level. The file was right and the check was wrong (F292).
    """
    from collections import Counter

    module = _module()
    labels = [module._label(entry) for entry in module.entries()
              if entry["level"] == 2]
    repeats = {label: count for label, count in Counter(labels).items()
               if count > 1}
    assert repeats == {"F82": 2}, (
        f"labels repeat beyond the one deliberate case: {repeats}")
    assert "F2b" in labels and "F2" in labels, labels[:10]


def test_the_only_repeat_is_the_deliberate_one():
    """F82 keeps its superseded text, which is the project on the record."""
    module = _module()
    assert module.main(["--check"]) == 0, (
        "the numbering check fails: run tools/findings.py --check")


def test_a_lookup_returns_the_body():
    module = _module()
    entries = {entry["number"]: entry for entry in module.entries()}
    assert 219 in entries, "F219 is cited all over the code"
    body = module.body(entries[219])
    assert body.startswith("## F219") or body.startswith("### F219"), body[:60]
    assert len(body.splitlines()) > 3, body


def test_grep_finds_a_known_finding():
    module = _module()
    assert module.main(["--grep", "hydroxyproline"]) == 0
    assert module.main(["--grep", "a phrase that appears in no finding"]) == 1


def test_an_unknown_number_is_an_error_not_an_empty_answer():
    module = _module()
    assert module.main(["99999"]) == 1
