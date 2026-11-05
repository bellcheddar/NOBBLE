"""Every budget verdict states its conclusion, not just its numbers (F201).

`gate_g1`'s verdict is the sentence a person reads when refinement is priced,
and `tier2.py` prints it after "GATE G1 OPEN:" when the gate opens. It had
four cases and three stated a conclusion:

- fits:                     "costs X h or less against Y h remaining"
- over, measured factor:    "costs X h against Y h remaining of the Z h budget"
- over, bounded range:      "costs X to Y h, and the upper end exceeds ..."
- unpriceable:              "a refusal to guess"

The second was the one that said nothing. It is also the branch that opens
the gate on a cost that is known rather than bounded, and it read almost
exactly like the passing verdict: the distinguishing words were "or less".
A reader skimming "costs 150.0 h against 67.7 h remaining" has to do the
comparison to learn that it is a stop condition.

These tests assert the property on the real function, by driving it with
projections rather than by reading the source, because the source is one
nested conditional expression and the point is what comes out of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE = (ROOT / "nobble" / "execute" / "budget.py").read_text()


def code_only(text: str) -> str:
    import re
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    return re.sub(r'""".*?"""', "", body, flags=re.S)


def _verdict(monkeypatch, *, fits: bool, collapsed: bool) -> str:
    """Drive the real `gate_g1` into one of its branches.

    By monkeypatching the two things it reads, `tier2_projection` and
    `hours_spent`, rather than by scanning the source. The first version of
    these tests asserted on source text and failed twice on my own fix: the
    f-string wraps across lines so "which exceeds the" is not a substring,
    and `code.index('"verdict": (')` found the unpriceable dict rather than
    the main one. The docstring above said to drive the function; I scanned
    the source anyway.
    """
    from nobble import paths
    from nobble.execute import budget

    # Derived from the configured ceiling, not quoted. These were literals,
    # 150 h for the collapsed over-budget case and 29.2 to 219.3 for the
    # bounded one, chosen when max_compute_hours was 96. Marc raised it to
    # 240 and every over-budget case silently became an under-budget one:
    # four of these tests failed asserting that a verdict said "exceeds"
    # while the fixture no longer exceeded anything (D-NOB-073).
    spent = 28.3
    remaining = float(paths.tuning()["campaign"]["max_compute_hours"]) - spent
    assert remaining > 0, "the budget is already spent, so neither branch is reachable"
    under, over = remaining * 0.2, remaining * 1.5

    low, high = (under, under) if collapsed else (under / 2, under)
    if not fits:
        low, high = (over, over) if collapsed else (under, over)
    # `collapsed` is read from measured_scaling.factor: a measured factor
    # collapses the range to one number, and None leaves it bounded.
    monkeypatch.setattr(budget, "tier2_projection", lambda *a, **k: {
        "priceable": True, "jobs": 140, "pairs": 15,
        "hours_low": low, "hours_high": high,
        "measured_scaling": {"factor": 3.4 if collapsed else None},
    })
    monkeypatch.setattr(budget, "hours_spent", lambda *a, **k: {
        "hours": spent, "jobs": 861, "by_campaign": {},
    })
    return budget.gate_g1(Path("campaigns/does_not_matter"))["verdict"]


def test_the_over_budget_measured_case_says_it_exceeds(monkeypatch):
    """The branch that stated numbers and no conclusion."""
    verdict = _verdict(monkeypatch, fits=False, collapsed=True)
    assert "exceeds" in verdict, (
        "a known cost over the budget still states no conclusion: " + verdict
    )


def test_both_over_budget_branches_say_it_exceeds(monkeypatch):
    for collapsed in (True, False):
        verdict = _verdict(monkeypatch, fits=False, collapsed=collapsed)
        assert "exceeds" in verdict, (collapsed, verdict)


def test_the_passing_verdict_cannot_be_mistaken_for_a_failing_one(monkeypatch):
    """They differed only by "or less", which is thin for a stop condition."""
    passing = _verdict(monkeypatch, fits=True, collapsed=True)
    failing = _verdict(monkeypatch, fits=False, collapsed=True)
    assert "exceeds" not in passing, passing
    assert "exceeds" in failing, failing
    assert passing != failing
    # And the distinction is not carried by two words alone.
    assert "or less" in passing


def test_the_gate_flag_agrees_with_the_sentence(monkeypatch):
    """A verdict saying "exceeds" while gate_g1_open is False, or the
    reverse, would be worse than either alone (F161's shape)."""
    from nobble.execute import budget

    for fits in (True, False):
        low, high = (20.0, 20.0) if fits else (150.0, 150.0)
        monkeypatch.setattr(budget, "tier2_projection", lambda *a, **k: {
            "priceable": True, "jobs": 140, "pairs": 15,
            "hours_low": low, "hours_high": high,
            "measured_scaling": {"factor": 3.4},
        })
        monkeypatch.setattr(budget, "hours_spent", lambda *a, **k: {
            "hours": 28.3, "jobs": 861, "by_campaign": {},
        })
        report = budget.gate_g1(Path("campaigns/does_not_matter"))
        says_over = "exceeds" in report["verdict"]
        assert says_over is report["gate_g1_open"], report
        assert says_over is not report["fits"], report
