"""The hold printed the project at its worst and omitted the power (F350).

`tools/publication_hold.py` is the print-out read at the moment publication
is decided, and `deploy/deploy.sh` runs it as its first pre-flight step. It
showed the composite's held-out AUC at p 0.077 and Delta-ipTM below chance,
which are the two weakest readings in the matched arm, and nothing else.

So a reader saw a weak result where the truth is an unpowered one, and had
no way to see the strongest thing the project has. Both are now printed, and
the power statement is what distinguishes them: at the best unfitted rate,
clearing the corrected threshold needs about 27 decisive blocks and the arm
has 17.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE = (ROOT / "tools" / "publication_hold.py").read_text()


def test_the_best_single_component_is_printed():
    assert 'row_of(blocks, "convergence_score")' in SOURCE, (
        "the hold no longer prints the best single component, so it shows "
        "the composite and Delta-ipTM and nothing above them"
    )
    assert 'row_of(scrambles, "convergence_score")' in SOURCE


def test_the_power_statement_is_printed():
    assert "_power_note(blocks)" in SOURCE
    assert "decisive blocks and the arm has" in SOURCE, (
        "the hold no longer says how many blocks would be needed, so its p "
        "values read as a weak result rather than an unpowered one"
    )


def test_the_power_note_refuses_the_fitted_row():
    """The dangerous version, which it had for one run.

    `composite, in sample` has the highest rate by construction, 18 of 22,
    so taking the maximum picked it and the note read "needs about 22
    decisive blocks and the arm has 22": a power warning that reassured,
    computed from the one row the matched-arm tool says not to read.
    """
    assert 'in sample" not in str(entry.get("statistic"' in SOURCE, (
        "the power note is back to reading every row, including the "
        "in-sample composite, which makes it report that the arm is "
        "adequately powered"
    )


def test_the_power_note_says_it_is_the_favourable_case():
    assert "at the best unfitted rate" in SOURCE, (
        "the note no longer says the rate it uses is the most favourable "
        "unfitted one, so a reader cannot tell it is an optimistic bound"
    )


def test_the_note_computes_rather_than_transcribes():
    """So it follows the arm as blocks are added.

    A transcribed 27 would be wrong the moment the eight recoverable
    positives are curated, which is exactly the change F349 recommends.
    """
    assert "from nobble.numeric import sign_test" in SOURCE
    assert "sign_test(round(rate * n), n)" in SOURCE, (
        "the required block count is no longer computed from the observed "
        "rate, so it cannot follow the arm"
    )


def test_the_hold_still_refuses(monkeypatch):
    """None of this may have turned the gate into a report.

    `main()` takes no argv and parses `sys.argv` itself, so under pytest it
    sees pytest's arguments and argparse exits. Two wrong calls before the
    right one: `main([])` raised TypeError, then `main()` failed on
    "unrecognized arguments: tests/". `inspect.signature` gave the arity
    and only running it gave the rest.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "publication_hold", ROOT / "tools" / "publication_hold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", ["publication_hold.py"])
    assert module.main() != 0, (
        "the publication hold now exits zero, so deploy.sh would publish"
    )
