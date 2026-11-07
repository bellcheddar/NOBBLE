"""Four directions, four conclusions (F200).

`compare.conclude`'s verdict is the sentence on the benchmark page that says
whether F6 held: whether submitting a substrate as the whole domain rather
than a 15-mer recovers poses better. It had a label for "better", a label for
"nothing changed", and `mixed` for everything else.

"Everything else" is two different results. Some better and some worse is
mixed. None better and several worse is not mixed at all: it is F6
contradicted, the whole domain recovering poses less well than the fragment.
That is a finding, and this project publishes a failed control rather than
softening it, so describing it with a word that means "both ways" was the one
reading that lost the direction.

The counts were printed either way, so nothing was hidden. The headline word
was simply wrong for one of its two cases, which is the same defect as F198
and F199: correct arithmetic in a sentence that says something else.

A second thing in the same branch. `control {'held' if control_ok else
'moved'}` had a false arm that could never run, because the two branches
above the F6 ones return for every state in which the control has not held.
The conditional is gone and the sentence says "control held", which is what
it always said.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import compare  # noqa: E402

SOURCE = (ROOT / "nobble" / "validate" / "compare.py").read_text()


def code_only(text: str) -> str:
    import re
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    return re.sub(r'""".*?"""', "", body, flags=re.S)


def _row(gene: str, verdict: str, control: bool = False):
    row = compare.PairComparison(gene=gene, e3="CRBN",
                                 baseline_pair="b", corrected_pair="c")
    row.verdict, row.is_control, row.delta_rmsd = verdict, control, 0.1
    return row


def conclude(improved: int, worse: int) -> str:
    """Drive the real branches with a hand-built set of comparisons."""
    rows = [_row("IKZF1", "control held", control=True)]
    rows += [_row(f"u{i}", "improved") for i in range(improved)]
    rows += [_row(f"d{i}", "worse") for i in range(worse)]
    return compare.conclude(rows) if hasattr(compare, "conclude") else ""


def test_the_source_has_a_label_for_every_direction():
    """Read off the source, because `conclude` may not be callable alone."""
    code = code_only(SOURCE)
    for label in ("F6 supported", "F6 not supported", "F6 contradicted",
                  "mixed", "NOT TRUSTWORTHY", "not concluded"):
        assert label in code, f"no branch says {label!r}"


def test_the_all_worse_case_is_not_called_mixed():
    """The case that had no word (F200).

    Located in the source rather than by calling, because the conclusion is
    built inside a longer function. The ordering is what matters: the
    contradicted branch has to be tested before the catch-all, or every
    all-worse run falls through to `mixed` exactly as before.
    """
    code = code_only(SOURCE)
    contradicted = code.index("F6 contradicted")
    guard = code.index("elif worse and not improved")
    catch_all = code.rindex("mixed:")
    assert guard < contradicted < catch_all, (
        "the contradicted branch is not guarded before the catch-all, so an "
        "all-worse comparison is still reported as mixed"
    )


def test_the_dead_control_arm_is_gone():
    """`control_ok` is True by construction in the final branch."""
    code = code_only(SOURCE)
    assert "'held' if control_ok else 'moved'" not in code, (
        "the final branch tests a condition that cannot be false there, so "
        "its 'moved' arm can never run"
    )
    assert "control held" in code


def test_the_two_f6_directions_say_opposite_things():
    """A reader must be able to tell them apart without counting."""
    code = code_only(SOURCE)
    supported = code[code.index("F6 supported"):]
    supported = supported[:supported.index("elif")]
    contradicted = code[code.index("F6 contradicted"):]
    contradicted = contradicted[:contradicted.index("else:")]
    assert "improved" in supported and "none got worse" in supported
    assert "got worse" in contradicted and "none improved" in contradicted


def test_the_report_carries_both_campaigns_recovery_curves():
    """The published bundle showed the negative without what scopes it.

    validation.json said "0 of 65 within 3 A, median 17.535" and
    comparison.json told the whole-domain story with no curve in it, in a
    different tab, with no cross-reference either way. The same statistic on
    the whole-domain campaign is 53.8 per cent within 3 A at 2.494 A (F236),
    and a reader of the first number could not get to the second.
    """
    from pathlib import Path

    from nobble.validate import compare as compare_module

    from nobble.execute.campaign import latest_or_absent

    baseline = latest_or_absent("benchmark")
    corrected = latest_or_absent("corrected")
    if baseline is None or corrected is None:
        pytest.skip("both campaigns are needed for the contrast")

    report = compare_module.compare(Path(baseline), Path(corrected))
    for key in ("baseline_recovery_curve", "corrected_recovery_curve"):
        curve = report.get(key)
        assert curve, key
        assert curve.get("status"), curve
        if curve["status"] != "computed":
            continue
        assert "within_3.0A" in curve, curve
        assert curve.get("median_rmsd") is not None, curve
        assert curve.get("campaign"), curve


def test_a_campaign_without_validation_says_so_rather_than_nothing(tmp_path):
    """Absent is not zero, and an empty curve would read as a failed one."""
    from nobble.validate import compare as compare_module

    curve = compare_module._recovery_curve(tmp_path / "campaign_absent")
    assert curve["status"].startswith("not computed"), curve
    assert "within_3.0A" not in curve, curve


def test_the_benchmark_page_renders_both_curves():
    """Data nothing displays does not reach a reader.

    compare.compare was given each campaign's own pose-recovery curve so the
    bundle would stop showing the negative without the measurement that
    scopes it. The template names its fields rather than iterating, so the
    two new keys sat in comparison.json unrendered and the stated reason for
    adding them was not yet true of the site.
    """
    template = (ROOT / "nobble" / "app" / "templates" / "benchmark.html").read_text()
    for key in ("baseline_recovery_curve", "corrected_recovery_curve"):
        assert key in template, (
            f"{key} is carried in comparison.json and shown nowhere")
    # The radius the headline failure is quoted in, and the one the
    # whole-domain campaign clears.
    assert "within_3.0A" in template, template[:0]
    assert "15-mer" in template and "whole domain" in template


def _curve_panel():
    """The comparison panel's curve table, as a renderable snippet.

    Rendered rather than grepped. The first version of this test asserted the
    guard's text appeared in the template, which says nothing about what the
    template does with it: the same reason the "exit 0 but" detail test moved
    from matching a source line to running the job.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "nobble" / "app" / "templates")),
        autoescape=select_autoescape())
    source = (ROOT / "nobble" / "app" / "templates" / "benchmark.html").read_text()
    start = source.index("{% set base_curve")
    end = source.index("{% endif %}", start) + len("{% endif %}")
    return env.from_string(source[start:end])


COMPUTED_BASE = {"status": "computed", "median_rmsd": 17.14,
                 "within_3.0A": 0.0, "within_2.0A": 0.0, "n": 65}
COMPUTED_CORR = {"status": "computed", "median_rmsd": 2.494,
                 "within_3.0A": 0.5385, "within_2.0A": 0.4154, "n": 65}


def test_both_curves_present_renders_the_contrast():
    rendered = _curve_panel().render(comparison={
        "baseline_recovery_curve": COMPUTED_BASE,
        "corrected_recovery_curve": COMPUTED_CORR})
    assert "<table" in rendered, rendered
    assert "17.14" in rendered and "2.494" in rendered, rendered
    assert "0.5385" in rendered, rendered


def test_a_bundle_without_the_curves_renders_nothing():
    """The live state: the published bundle predates the keys.

    It was built before compare.compare carried them, so the guard is
    load-bearing now rather than in principle.
    """
    import json

    published = json.loads(
        (ROOT / "deploy" / "atlas" / "comparison.json").read_text())
    rendered = _curve_panel().render(comparison=published)
    assert "<table" not in rendered, rendered
    assert rendered.strip() == "", rendered


def test_one_uncomputed_curve_renders_nothing():
    """Half a comparison must not render as a measured row beside a blank."""
    rendered = _curve_panel().render(comparison={
        "baseline_recovery_curve": COMPUTED_BASE,
        "corrected_recovery_curve": {"status": "not computed"}})
    assert "<table" not in rendered, rendered
    assert "17.14" not in rendered, rendered
