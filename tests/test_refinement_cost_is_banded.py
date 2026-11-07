"""The tier-2 over tier-1 ratio is not constant across job size.

One pooled median priced every refinement as if it were the commonest size.
On the main campaign 129 of 151 refinements are under 200 tokens, so the
pooled 4.615 is effectively that band's figure, and the ratio measured by
band runs 4.60, 6.11, 8.22 and 10.52 as jobs grow. The pooled factor's error
is 1.0 per cent in the band holding most jobs and 24, 44 and 56 per cent in
the three above it, which is why the overall median error (1.2 per cent)
showed nothing: the aggregate was dominated by the band that was right
(F257).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import budget, runner
from nobble import paths


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _campaign(root: Path, big_ratio: float = 10.0,
              small_ratio: float = 4.0) -> Path:
    """A campaign whose small jobs refine cheaply and large ones do not."""
    directory = root / "campaign_banded"
    directory.mkdir()
    tier1, tier2, queue = [], [], []
    for index, (tokens, ratio) in enumerate(
            [(150, small_ratio)] * 6 + [(1200, big_ratio)] * 2):
        job = f"pair{index}__ternary__conditioned__seed1"
        base = 100.0
        tier1.append({"job_id": job, "pair_id": f"pair{index}",
                      "status": "done", "seconds": base, "tokens": tokens,
                      "complex_type": "ternary"})
        tier2.append({"job_id": job + budget.TIER2_SUFFIX, "status": "done",
                      "seconds": base * ratio, "tokens": tokens})
        queue.append({"job_id": job, "pair_id": f"pair{index}",
                      "tokens": tokens, "complex_type": "ternary"})
    _write(directory / "results.jsonl", tier1)
    _write(directory / "results_tier2.jsonl", tier2)
    _write(directory / "queue.jsonl", queue)
    return directory


def test_the_factor_is_measured_per_band(tmp_path):
    observed = budget.measured_scaling(_campaign(tmp_path))
    bands = {(b["min_tokens"], b["max_tokens"]): b["factor"]
             for b in observed["by_band"]}
    assert bands[(0, 200)] == 4.0, bands
    assert bands[(800, 1600)] == 10.0, bands


def test_a_large_job_is_priced_at_its_own_band(tmp_path):
    """Not at the pooled median, which the small jobs set.

    This is the whole defect: six small jobs and two large ones give a
    pooled median of 4.0, and pricing the large pair at 4.0 underprices it
    by a factor of two and a half.
    """
    observed = budget.measured_scaling(_campaign(tmp_path))
    assert observed["factor"] == 4.0, observed
    assert budget.band_factors(observed, 1200)[0] == 10.0, observed
    assert budget.band_factors(observed, 150)[0] == 4.0, observed


def test_the_projection_uses_the_per_job_factor(tmp_path):
    """Eight jobs at 100 tier-1 seconds each: 6 x 4 + 2 x 10 = 44 job-ratios.

    Pooled would give 8 x 4 = 32. The projection must report the former.
    """
    directory = _campaign(tmp_path)
    report = budget.tier2_projection(directory)
    assert report["jobs"] == 8, report
    assert report["hours_mid"] == round(4400.0 / 3600.0, 2), report
    # And the reported aggregate ratio agrees with the reported hours, so a
    # reader cannot derive a different cost from the two numbers.
    assert report["scaling_low"] <= 44 / 8 <= report["scaling_high"], report


def test_an_unmeasured_band_falls_back_to_the_pooled_factor(tmp_path):
    """Not to zero, and not to the nearest band.

    A job size nothing has refined yet has no band figure. The pooled median
    is the honest answer there; silently using a neighbouring band's would
    state a precision the data does not have.
    """
    observed = budget.measured_scaling(_campaign(tmp_path))
    factor, low, high = budget.band_factors(observed, 300)
    assert factor == observed["factor"], (factor, observed["factor"])
    assert low == observed["observed_min"]
    assert high == observed["observed_max"]


def test_a_failed_refinement_contributes_its_ratio(tmp_path):
    """It cost that wall clock, and this factor prices cost.

    Reading results_tier2.jsonl alone excluded every failure, and failures
    are not a random sample: they are the largest jobs, so their absence
    pushed the factor down exactly where it was already too low.
    """
    directory = _campaign(tmp_path)
    # A large job that has a tier-1 time and no successful refinement, which
    # is what a failure is. Reusing a job that already succeeded would test
    # nothing: `setdefault` prefers the authoritative results record, and it
    # should.
    with (directory / "results.jsonl").open("a") as results:
        results.write(json.dumps(
            {"job_id": "pair8__ternary__conditioned__seed1",
             "pair_id": "pair8", "status": "done", "seconds": 100.0,
             "tokens": 1200, "complex_type": "ternary"}) + "\n")
    _write(directory / "state_tier2.jsonl", [
        {"job_id": "pair8__ternary__conditioned__seed1" + budget.TIER2_SUFFIX,
         "status": "failed: exit 0 but no confidence JSON written",
         "seconds": 2000.0, "tokens": 1200},
    ])
    observed = budget.measured_scaling(directory)
    bands = {b["min_tokens"]: b for b in observed["by_band"]}
    assert bands[800]["jobs"] == 3, observed
    assert bands[800]["observed_max"] == 20.0, observed


def test_a_successful_refinement_is_read_from_the_results_file(tmp_path):
    """A job in both files is counted once, from the authoritative record.

    The state file holds a record per outcome and the results file holds the
    settled one, so a job that was retried appears several times in state. If
    this preferred state, a retried job would price at its last attempt and
    a job with any history at all would be double counted.
    """
    directory = _campaign(tmp_path)
    job = "pair7__ternary__conditioned__seed1" + budget.TIER2_SUFFIX
    before = budget.measured_scaling(directory)
    _write(directory / "state_tier2.jsonl", [
        {"job_id": job, "status": "failed: first attempt",
         "seconds": 9999.0, "tokens": 1200},
        {"job_id": job, "status": "done", "seconds": 1000.0, "tokens": 1200},
    ])
    after = budget.measured_scaling(directory)
    assert after["jobs"] == before["jobs"], (before, after)
    assert after["observed_max"] == before["observed_max"], (before, after)


def test_a_running_refinement_contributes_nothing(tmp_path):
    """It has no settled cost, and its record carries no seconds."""
    directory = _campaign(tmp_path)
    before = budget.measured_scaling(directory)["jobs"]
    _write(directory / "state_tier2.jsonl", [
        {"job_id": "pair7__ternary__conditioned__seed1" + budget.TIER2_SUFFIX,
         "status": "running", "started_at": 1.0},
    ])
    assert budget.measured_scaling(directory)["jobs"] == before


def test_a_record_without_a_token_count_still_prices(tmp_path):
    """Banding must refine the pooled factor, never subtract from it.

    The first version required `tokens` on the tier-2 record and dropped the
    record entirely without one, so two fixtures went from a factor of 2.0
    to no factor at all and the gate fell back to judging on a bound.
    """
    directory = tmp_path / "campaign_tokenless"
    directory.mkdir()
    _write(directory / "results.jsonl", [
        {"job_id": "p__ternary__conditioned__seed1", "status": "done",
         "seconds": 100.0, "tokens": 150, "complex_type": "ternary"}])
    _write(directory / "results_tier2.jsonl", [
        {"job_id": "p__ternary__conditioned__seed1" + budget.TIER2_SUFFIX,
         "status": "done", "seconds": 500.0}])
    observed = budget.measured_scaling(directory)
    assert observed["factor"] == 5.0, observed
    assert observed["by_band"] == [], observed


def test_the_two_band_rules_agree(tmp_path):
    """`budget._token_band` repeats `runner.token_band` to avoid a cycle.

    Two copies of a rule is two things to keep in step, so this holds them
    together across every edge in config and a size either side of each.
    """
    edges = [int(edge) for edge in
             paths.thresholds()["throughput"]["token_bands"]]
    sizes = [0, 1, 10_000]
    for edge in edges:
        sizes += [edge - 1, edge, edge + 1]
    for tokens in sizes:
        assert budget._token_band(tokens, edges) == runner.token_band(
            tokens, edges), tokens


def test_the_range_brackets_the_point_estimate(tmp_path):
    """low <= mid <= high, whatever the bands say.

    The range comes from each band's own observed minimum and maximum, so a
    band measured once has a degenerate range and a band measured often has
    a real one. A mid outside it would mean the three were computed from
    different samples.
    """
    report = budget.tier2_projection(_campaign(tmp_path))
    assert report["hours_low"] <= report["hours_mid"] <= report["hours_high"], (
        report)
