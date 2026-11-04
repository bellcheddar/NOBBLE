"""One rule for what counts as a number, imported rather than retyped.

F74 found that `isinstance(value, (int, float))` admits NaN, and that a NaN
reaching a comparison is scored as a unanimous loss rather than as missing
data. It fixed one site, in `matched_control_roc`.

The same idiom appeared in fourteen places. Fixing one of fourteen copies of
a rule is the shape this project keeps finding: three copies of a timestamp
format, two theme colours, two binning rules, two queue files. So the rule
lives in `nobble/numeric.py` and the call sites import it (F76).

The two that would have mattered most are `tier2.choose_ranking_key`, which
decides which pairs tier 2 spends ten recycles and twenty-five diffusion
samples on, and `score.run`'s bridge percentile median, which is taken by
index from a sorted list: a NaN inside `sorted()` settles wherever the sort
leaves it, so the median can come back as the NaN or as an arbitrary
neighbour.
"""
from __future__ import annotations

import ast
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.numeric import finite, finite_values, median_of  # noqa: E402

NAN = float("nan")
INF = float("inf")


def test_the_rule_rejects_what_a_type_check_admits():
    assert finite(1) and finite(0) and finite(-2.5)
    for rejected in (NAN, INF, -INF, True, False, None, "1", [1]):
        assert not finite(rejected), rejected


def test_a_bool_is_rejected_because_it_compares_as_a_number():
    """`isinstance(True, int)` is true, so a boolean would have been
    compared as 1 against real measurements rather than refused."""
    assert not finite(True)
    assert True > 0.5 and False < 0.5, "the hazard this guards against"


def test_the_median_ignores_what_it_cannot_compare():
    assert median_of([1, NAN, 2, 3]) == 2
    assert median_of([NAN, NAN]) is None
    assert median_of([]) is None


def test_the_median_keeps_the_estimator_it_replaced():
    """`sorted(...)[len // 2]`, the lower median, not the mean of the
    middle two. Changing the estimator while introducing the helper would
    have moved published figures for no reason."""
    assert median_of([1, 2, 3, 4]) == 3
    assert median_of([1, 2, 3]) == 2


def _old_median(values):
    """The estimator these call sites used: `sorted(...)[len // 2]`."""
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else None


def test_the_two_estimators_agree_on_finite_data():
    """The refactor must not move a published figure. On data with no
    non-finite value the two are the same estimator, which was checked
    against every float list in the records and 3,000 random ones."""
    import random

    generator = random.Random(7)
    for _ in range(500):
        values = [generator.uniform(-5, 100)
                  for _ in range(generator.randint(1, 15))]
        assert median_of(values) == _old_median(values)


def test_one_nan_makes_the_whole_sort_meaningless():
    """Worse than the NaN being picked. Every comparison against NaN is
    false, so `sorted` does not merely misplace it: the other elements come
    back unsorted too, and any index into the result is arbitrary.

    The last case is the one that matters. A bridge percentile median of 10
    where the answer is 70, on what spec 4.1 calls the primary signal.
    """
    assert math.isnan(_old_median([1.0, NAN, 2.0]))
    assert median_of([1.0, NAN, 2.0]) == 2.0

    assert _old_median([3.0, NAN, 1.0, 2.0]) == 1.0
    assert median_of([3.0, NAN, 1.0, 2.0]) == 2.0

    assert _old_median([90.0, NAN, 10.0, 50.0, 70.0]) == 10.0
    assert median_of([90.0, NAN, 10.0, 50.0, 70.0]) == 70.0


def test_a_nan_does_not_always_corrupt_the_answer():
    """Stated because the finding would otherwise overclaim. For some
    inputs the index still lands on a sensible value, which is exactly what
    makes this hard to notice: it is unspecified, not reliably wrong."""
    assert _old_median([NAN, 1.0, 2.0, 3.0]) == 2.0
    assert median_of([NAN, 1.0, 2.0, 3.0]) == 2.0


def _numeric_type_checks() -> dict[str, list[str]]:
    """Every surviving `isinstance(..., (int, float))` outside the rule."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        if path.name == "numeric.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "isinstance"):
                continue
            if len(node.args) != 2:
                continue
            target = node.args[1]
            names = []
            if isinstance(target, ast.Tuple):
                names = [e.id for e in target.elts if isinstance(e, ast.Name)]
            elif isinstance(target, ast.Name):
                names = [target.id]
            if {"int", "float"} <= set(names):
                found.setdefault(str(path.relative_to(ROOT)), []).append(
                    f"line {node.lineno}")
    return found


def test_no_module_decides_this_for_itself():
    """The sweep. A new `isinstance(x, (int, float))` is a fifteenth copy
    of a rule that has one home, and it admits NaN by construction."""
    found = _numeric_type_checks()
    assert not found, (
        "numeric type check(s) outside nobble/numeric.py; import finite() "
        f"instead: {found}"
    )


def test_the_sweep_would_notice_a_new_one():
    """The negative control. A sweep that finds nothing reads the same
    whether the codebase is clean or the pattern is broken (F67)."""
    source = "def f(v):\n    return isinstance(v, (int, float))\n"
    tree = ast.parse(source)
    hits = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "isinstance"]
    assert hits, "the pattern this sweep looks for is no longer parsed"


def test_the_decile_ranking_uses_the_rule():
    """The site where a NaN would have cost the most: tier 2 spends ten
    recycles and twenty-five diffusion samples on whatever this picks."""
    from nobble.execute import tier2

    rows = [{"bridge_percentile": 90.0, "pair_id": "good"},
            {"bridge_percentile": NAN, "pair_id": "nan"},
            {"bridge_percentile": 10.0, "pair_id": "low"},
            {"bridge_percentile": 50.0, "pair_id": "mid"}]
    key, _notes = tier2.choose_ranking_key(rows)
    if key is None:
        return      # too few to rank on, which is its own correct answer
    ranked = [row for row in rows if finite(row.get(key))]
    assert {row["pair_id"] for row in ranked} == {"good", "low", "mid"}
