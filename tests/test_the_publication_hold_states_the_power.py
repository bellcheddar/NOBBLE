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

    Asserted against the arm rather than the hold, because F350c moved the
    computation there to stop it being written twice. The hold now reads
    the figure, so this is the only place the exclusion can live.
    """
    arm = (ROOT / "tools" / "matched_arm_stratified.py").read_text()
    assert 'startswith("composite")' in arm, (
        "the power figure is back to reading every row, including the "
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
    arm = (ROOT / "tools" / "matched_arm_stratified.py").read_text()
    assert "sign_test(round(rate * n), n)" in arm, (
        "the required block count is no longer computed from the observed "
        "rate, so it cannot follow the arm as blocks are added"
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


def test_the_power_figure_is_computed_once(monkeypatch):
    """One sign-test inversion, not two (F350c).

    F350 put the arithmetic in the hold, one directory from the arm it
    describes. Two copies of a sign test is D-NOB-007's subject and F154's
    shape, and this project already had that exact duplication once:
    `sign_test` lives in `nobble/numeric.py` because it was written twice an
    hour apart (F326).

    It now lives in `matched_arm_stratified._power`, beside the arm, inside
    the report the atlas already publishes, so the hold and about.json say
    the same thing by construction rather than by agreement.
    """
    arm = (ROOT / "tools" / "matched_arm_stratified.py").read_text()
    assert "def _power(results: list[dict]" in arm
    assert '"power": _power(results,' in arm, (
        "the arm no longer carries its own power figure, so the hold and "
        "the page must each work it out"
    )
    assert "sign_test(round(rate * n), n)" in arm
    assert "sign_test(round(rate * n), n)" not in SOURCE, (
        "the publication hold inverts the sign test again, which is the "
        "second copy this was written to remove"
    )
    assert 'power = blocks.get("power")' in SOURCE


def test_the_power_figure_ignores_the_fitted_composite():
    """In both places now, so the fix cannot be lost in one of them."""
    arm = (ROOT / "tools" / "matched_arm_stratified.py").read_text()
    assert 'startswith("composite")' in arm, (
        "the power figure is back to reading every statistic, including the "
        "in-sample composite, whose rate is highest by construction"
    )


def test_the_about_page_says_underpowered_rather_than_null():
    """One sentence, where a figure would be actively misread without it.

    Every interval in that panel contains a half, which reads as no effect.
    The project's copy rule allows a disclaimer exactly here, and caps it at
    one sentence.
    """
    import re

    from jinja2 import Environment

    page = (ROOT / "nobble" / "app" / "templates" / "about.html").read_text()
    assert "Underpowered, not null" in page
    start = page.index("{% set power = matched_blocks.get('power') %}")
    end = page.index("{% endif %}", start) + len("{% endif %}")
    template = Environment().from_string(page[start:end])

    # Whitespace-normalised before matching. A rendered template wraps, so
    # "about 27 decisive blocks" arrives as "about 27 decisive\n      blocks"
    # and a substring check fails on text that is there. Third time today:
    # the "writes nothing" check, then "wrong population", then this, which
    # I wrote minutes after writing a test about that exact trap. The
    # remedy is one `' '.join(x.split())` and I keep rediscovering it.
    shown = " ".join(template.render(matched_blocks={"power": {
        "needed_decisive": 27, "decisive": 17,
        "positives_modellable": 24, "positives_in_screen": 32}}).split())
    assert "about 27 decisive blocks" in shown
    assert "the arm has 17" in shown
    words = len(re.sub(r"<[^>]+>", " ", shown).split())
    assert words <= 40, (words, shown)
    assert shown.count(".") == 1, (
        "more than one sentence, and the copy rule allows one", shown)

    # A bundle built before the figure existed renders nothing, not an
    # empty warning.
    assert template.render(matched_blocks={}).strip() == ""
    assert template.render(matched_blocks={"power": None}).strip() == ""
