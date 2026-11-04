"""Spec 4.3's aggregation rule, made executable.

    delta_iptm = iptm_min_ternary - iptm_min_binary
    Using the minimum across the five seeds in each condition, not the mean.

A mutation sweep found that `min` in metrics._minimum could become `max`,
or a median, and the whole suite still passed. The rule that defines the
project's headline number had no test: every existing test used seed
values where the minimum, the median and the mean coincide closely enough
not to matter, or stubbed the aggregation out.

So these use seeds where the three answers are far apart and different
from each other, which is the only arrangement that can tell them apart.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score import metrics  # noqa: E402

# min 0.10, median 0.80, mean 0.64, max 0.95: no two coincide.
SPREAD = [0.10, 0.75, 0.80, 0.60, 0.95]


def test_the_helper_takes_the_minimum_not_the_median_or_the_mean():
    assert metrics._minimum(SPREAD) == 0.10
    assert metrics._minimum(SPREAD) != sorted(SPREAD)[len(SPREAD) // 2]
    assert metrics._minimum(SPREAD) != sum(SPREAD) / len(SPREAD)
    assert metrics._minimum(SPREAD) != max(SPREAD)


def test_missing_values_are_skipped_rather_than_treated_as_zero():
    """A null seed must not become the minimum, which would make every pair
    with one failed seed look like a total loss of interface."""
    assert metrics._minimum([None, 0.4, 0.9]) == 0.4
    assert metrics._minimum([None, None]) is None
    assert metrics._minimum([]) is None


def _job(seed, complex_type, iptm, conditioning="unconstrained"):
    return {
        "job_id": f"j{seed}{complex_type}", "pair_id": "p1", "seed": seed,
        "complex_type": complex_type, "conditioning": conditioning,
        "construct": "CRBN_CULT", "e3_gene": "CRBN", "peptide_id": "pep",
        "tier": "benchmark", "tokens": 400, "tier_setting": 1,
        "confidence": {"pair_chains_iptm": {"0": {"1": iptm}, "1": {"0": iptm}}},
    }


def _aggregate(tmp_path, binary, ternary):
    import json

    results = tmp_path / "results.jsonl"
    rows = [_job(i + 1, "binary", v) for i, v in enumerate(binary)]
    rows += [_job(i + 1, "ternary", v) for i, v in enumerate(ternary)]
    results.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    pairs = metrics.aggregate(results)
    assert len(pairs) == 1
    return pairs[0]


def test_delta_iptm_is_a_difference_of_minima(tmp_path):
    """Not a minimum of differences, and not a difference of medians.

    Binary seeds min 0.10; ternary seeds min 0.30. The difference of minima
    is 0.20. The difference of medians would be 0.05 and the difference of
    means 0.02, so a wrong aggregation cannot hide here.
    """
    pair = _aggregate(
        tmp_path,
        binary=[0.10, 0.75, 0.80, 0.60, 0.95],
        ternary=[0.30, 0.80, 0.85, 0.70, 0.90],
    )
    assert pair.iptm_min_binary == 0.10
    assert pair.iptm_min_ternary == 0.30
    assert pair.delta_iptm == 0.20

    median_binary = sorted([0.10, 0.75, 0.80, 0.60, 0.95])[2]
    median_ternary = sorted([0.30, 0.80, 0.85, 0.70, 0.90])[2]
    assert pair.delta_iptm != round(median_ternary - median_binary, 4)


def test_the_median_diagnostic_sits_beside_the_minimum_not_instead_of_it(tmp_path):
    """delta_iptm_median exists as a diagnostic (D-NOB-023). It must not be
    what delta_iptm reports, and the two must differ here so that confusing
    them would show."""
    pair = _aggregate(
        tmp_path,
        binary=[0.10, 0.75, 0.80, 0.60, 0.95],
        ternary=[0.30, 0.80, 0.85, 0.70, 0.90],
    )
    assert pair.delta_iptm_median is not None
    assert pair.delta_iptm_median != pair.delta_iptm


def test_one_collapsed_seed_sets_the_minimum_and_is_recorded_as_doing_so(tmp_path):
    """The reason the minimum is reported with collapse diagnostics beside
    it: a single bad seed decides the headline, so it has to be visible."""
    pair = _aggregate(
        tmp_path,
        binary=[0.80, 0.82, 0.78, 0.81, 0.79],
        ternary=[0.05, 0.88, 0.90, 0.87, 0.89],
    )
    assert pair.iptm_min_ternary == 0.05
    assert pair.delta_iptm < 0, "one collapsed ternary seed inverted the headline"
    assert pair.collapsed_seeds_ternary, (
        "the seed that set the minimum is not flagged as collapsed"
    )
