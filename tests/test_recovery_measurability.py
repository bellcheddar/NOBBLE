"""A pose recovery statistic computed over a value that is not a number.

`_rmsd` sums squared coordinate differences and takes a square root.
`gemmi.Position` accepts a NaN coordinate, and one NaN anywhere in the sum
makes the result NaN. There was no guard, and the consumers filtered on
`is not None`, which a NaN passes.

What it reaches is wider than a median. `pose_recovery` sorts a pair's
values and reports `ordered[0]`, the middle element, and `ordered[-1]` as
best, median and worst recovery. Every comparison against NaN is false, so
`sorted` leaves the other elements unsorted too and none of the three is the
statistic it claims to be. All three are published on the Benchmark tab, and
median recovery is what `tools/check_prediction.py` scored F13's predictions
against (F78).

Demonstrated: a NaN coordinate yields a NaN RMSD, which reaches the
published median. Not demonstrated: that a Boltz-written CIF can carry a NaN
coordinate in the first place. The fix is cheap and the consequence is a
published figure, so it is guarded either way, and the half that is
speculative is named as such.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score import poses  # noqa: E402

NAN = float("nan")


def _positions(triples):
    import gemmi

    return [gemmi.Position(*triple) for triple in triples]


def test_a_nan_coordinate_is_accepted_by_gemmi():
    """The premise. If gemmi refused these, there would be nothing to fix."""
    import gemmi

    position = gemmi.Position(NAN, 2.0, 3.0)
    assert not math.isfinite(position.x)


def test_an_unmeasurable_rmsd_is_none_rather_than_nan():
    moving = _positions([(0, 0, 0), (1, 1, 1), (NAN, 0, 0)])
    fixed = _positions([(0, 0, 0), (1, 1, 1), (2, 0, 0)])
    assert poses._rmsd(moving, fixed, None) is None


def test_a_measurable_rmsd_is_unchanged():
    """The fix must not move a real figure. Two points 3 apart in one
    coordinate: sqrt((0 + 9) / 2)."""
    moving = _positions([(0, 0, 0), (0, 0, 0)])
    fixed = _positions([(0, 0, 0), (3, 0, 0)])
    assert poses._rmsd(moving, fixed, None) == math.sqrt(9 / 2)


def test_the_existing_refusals_still_refuse():
    assert poses._rmsd([], [], None) is None
    assert poses._rmsd(_positions([(0, 0, 0)]), [], None) is None


def test_the_success_curve_ignores_what_it_cannot_measure():
    """`present` filtered on `is not None`, which a NaN passes, and the
    curve counts values at or below each breakpoint: NaN <= 1.0 is false,
    so it silently became a failure at every breakpoint while still
    counting in the denominator."""
    curve = poses.success_rate_curve([0.5, NAN, 1.5], breakpoints=(1.0, 2.0))
    assert curve["n"] == 2, "the NaN is still in the denominator"
    assert curve["within_1.0A"] == 0.5
    assert curve["within_2.0A"] == 1.0


def test_the_curve_median_is_the_median_of_the_measurable_values():
    curve = poses.success_rate_curve([3.0, NAN, 1.0, 2.0], breakpoints=(1.0,))
    assert curve["median_rmsd"] == 2.0


def test_a_pair_with_nothing_measurable_is_absent_not_zero():
    curve = poses.success_rate_curve([NAN, NAN], breakpoints=(1.0, 2.0))
    assert curve["n"] == 0
    assert curve["within_1.0A"] is None


def test_the_best_and_worst_are_corrupted_too_without_the_filter():
    """Why filtering before `sorted` matters rather than taking the median
    carefully. One NaN and neither end of the list is an extreme."""
    values = [5.0, NAN, 1.0, 9.0]
    ordered = sorted(values)
    assert ordered[0] != min(v for v in values if not math.isnan(v)), (
        "this input no longer demonstrates the hazard"
    )
    clean = sorted(v for v in values if math.isfinite(v))
    assert clean[0] == 1.0 and clean[-1] == 9.0


def test_every_published_recovery_figure_is_finite():
    """The state of the atlas as published. 221 rmsd fields were compared
    before and after this change and none moved, so the guard is a floor
    rather than a correction."""
    import json

    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        import pytest

        pytest.skip("no published atlas")
    checked = 0
    for path in sorted(atlas.glob("*.json")):
        def walk(value):
            nonlocal checked
            if isinstance(value, dict):
                for key, item in value.items():
                    if "rmsd" in key.lower() and isinstance(item, float):
                        checked += 1
                        assert math.isfinite(item), f"{path.name}:{key} = {item}"
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(json.loads(path.read_text()))
    assert checked > 0, "no recovery figure was examined"
