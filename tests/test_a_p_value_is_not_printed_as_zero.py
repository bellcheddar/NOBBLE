"""`round(8.0466e-07, 5)` is 0.0, and a p of zero is not a small p (F350).

The scramble test stored its strongest result that way and the publication
hold printed "p 0.0" in the one print-out read at the moment publication is
decided. Printed as zero it reads as certainty, which is the opposite of
what a very small p means: a bound, not a proof.

Found while putting F349's power figures into the hold, by reading the lines
the change produced rather than checking they appeared.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.numeric import rounded_p, sign_test  # noqa: E402


def test_a_small_p_survives_rounding():
    assert rounded_p(sign_test(25, 26)) == 8.05e-07, rounded_p(sign_test(25, 26))
    assert rounded_p(8.0466627e-07) == 8.05e-07
    assert rounded_p(1.23456e-12) == 1.23e-12


def test_an_ordinary_p_rounds_exactly_as_before():
    """The common case must not move, or every recorded figure changes."""
    for value in (0.02945, 0.11532, 0.3323, 0.5, 0.00739):
        assert rounded_p(value) == round(value, 5), value
    assert rounded_p(0.0290456) == 0.02905


def test_none_passes_through():
    """A statistic with no decisive comparison has no p, which is not the
    same as a small one: `trials <= 0` returns None and must stay None."""
    assert rounded_p(None) is None
    assert sign_test(0, 0) is None
    assert rounded_p(sign_test(0, 0)) is None


def test_zero_stays_zero():
    """Nothing in this project produces an exact zero p, and if something
    does it must not be turned into a tiny non-zero one."""
    assert rounded_p(0.0) == 0.0


def test_the_scramble_test_uses_it():
    source = (ROOT / "tools" / "scramble_paired_test.py").read_text()
    assert "rounded_p(sign_test(wins, trials))" in source, (
        "the scramble test is back to round(p, 5), which stores 0.0 for its "
        "own strongest result"
    )
    assert "round(value, 5)" not in source


def test_the_scramble_table_prints_it():
    """Fixing the stored value is half of it: the table's own `.5f` still
    printed 0.00000 afterwards."""
    source = (ROOT / "tools" / "scramble_paired_test.py").read_text()
    assert ':.3g' in source, (
        "the table formats every p with fixed decimals, so a small one "
        "still prints as zero even though the stored value is right"
    )


def test_the_live_figure_is_not_zero():
    """Against the real campaign, which is where it was found."""
    import importlib.util
    import pytest

    campaign = sorted(ROOT.glob("campaigns/campaign_*"))
    if not campaign:
        pytest.skip("no campaign on this checkout")
    spec = importlib.util.spec_from_file_location(
        "scramble_paired_test", ROOT / "tools" / "scramble_paired_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import json
    rows = {r["pair_id"]: r for r in (
        json.loads(line) for line
        in (campaign[-1] / "scores.jsonl").read_text().splitlines()
        if line.strip())}
    verdict = module.compare(rows, "convergence_score")
    if verdict.get("p_two_sided") is None:
        pytest.skip("no decisive comparison on this checkout")
    assert verdict["p_two_sided"] > 0.0, (
        "the strongest result in the project reports a p of exactly zero, "
        f"which is not a p: {verdict}"
    )
    assert verdict["p_two_sided"] < 1e-5, verdict
