"""Why a bridge percentile cannot come back as a confident 0.0.

`percentile_of` bisects the atlas distribution and returns
`100 * position / len(reference)`. Every comparison against a NaN is false,
so `bisect_left` walks left the whole way and returns 0, which means a
non-finite dSASA would be reported as percentile **0.0**: the lowest possible
value, indistinguishable from a real but tiny interface. Bridge percentile is
spec 4.1's primary signal and the key tier-2 selection ranks on, so a pair
would be pushed to the bottom of the ranking by an unmeasurable number
wearing a plausible one's clothes.

It cannot happen, and the reason is one line in another repository. BINMAN's
`find_bridges` admits a half-interface only when
`self.dsasa >= min_dsasa and self.contacts >= min_contacts`, and `NaN >= x`
is false, so a non-finite half never qualifies. `dsasa_total` is the sum of
two halves that did qualify, so it is finite by construction.

That is a structural protection rather than a lucky threshold: any `>=`
rejects NaN whatever the cutoff. But it is protection NOBBLE depends on and
does not own, and the obvious equivalent rewrite, `not (dsasa < min_dsasa)`,
accepts NaN. So the dependency is pinned here, where it is depended on
(F115).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.score import geometry  # noqa: E402


def test_a_non_finite_value_would_be_reported_as_the_lowest_percentile():
    """The hazard, stated so the guard below has something to be about. This
    is a property of bisection, not a defect: it is why the value must never
    get here."""
    import bisect

    reference = tuple(float(step) for step in range(0, 1000, 10))
    assert bisect.bisect_left(reference, math.nan) == 0
    assert bisect.bisect_left(reference, -math.inf) == 0
    # And a real small value is indistinguishable from it.
    assert bisect.bisect_left(reference, -1.0) == 0


def test_binmans_criterion_rejects_a_non_finite_dsasa():
    """The guard NOBBLE relies on, in the repository that owns it."""
    sys.path.insert(0, str(paths.BINMAN))
    from pipeline.geometry import ChainContact  # noqa: PLC0415

    minimum = 25.0
    for section in paths.thresholds().values():
        if isinstance(section, dict):
            for key, value in section.items():
                if "min_dsasa" in key and isinstance(value, (int, float)):
                    minimum = float(value)

    def half(dsasa: float) -> ChainContact:
        return ChainContact(chain_label="peptide", entity_id="P", dsasa=dsasa,
                            contacts=100, interface_residues=[], min_distance=3.0)

    for bad in (math.nan, -math.inf):
        assert not half(bad).passes(minimum, 1), (
            bad, "a non-finite half-interface qualified")

    assert half(minimum + 10.0).passes(minimum, 1), (
        "a finite half above the floor was rejected")
    assert not half(minimum - 10.0).passes(minimum, 1), (
        "the floor is not being applied at all, so the NaN rejection above "
        "would pass for the wrong reason"
    )


def test_the_criterion_is_written_as_a_comparison_that_rejects_nan():
    """`dsasa >= min` rejects NaN; `not (dsasa < min)` accepts it, and reads
    as the same thing. The rewrite is the realistic way this breaks."""
    source = (Path(paths.BINMAN) / "pipeline" / "geometry.py").read_text()
    assert "self.dsasa >= min_dsasa and self.contacts >= min_contacts" in source, (
        "BINMAN's bridging criterion has been rewritten. If it now admits a "
        "non-finite dSASA, NOBBLE's bridge percentile reports it as 0.0, "
        "which is the lowest real value and not a refusal"
    )


def test_every_percentile_in_the_live_campaigns_is_finite_and_in_range():
    """The property end to end, on real data rather than on the argument for
    it."""
    import json

    checked = 0
    for scores in sorted((ROOT / "campaigns").glob("*/scores.jsonl")):
        for line in scores.read_text().splitlines():
            if not line.strip():
                continue
            value = json.loads(line).get("bridge_percentile")
            if value is None:
                continue
            assert isinstance(value, (int, float)) and math.isfinite(value), (
                scores.parent.name, value)
            assert 0.0 <= value <= 100.0, (scores.parent.name, value)
            checked += 1
    if not checked:
        pytest.skip("no scored bridge percentile on this checkout")
    assert checked > 5, checked


def test_an_empty_reference_is_a_refusal_rather_than_a_zero():
    """The one case `percentile_of` does guard, and it guards it the right
    way round: no distribution to compare against gives NaN, not 0.0."""
    original = geometry.reference_distribution
    geometry.reference_distribution = lambda: {"dsasa_total": ()}
    try:
        assert math.isnan(geometry.percentile_of(100.0, "dsasa_total"))
    finally:
        geometry.reference_distribution = original
