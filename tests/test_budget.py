"""The campaign budget must not silently eat its own control set (D-NOB-021).

Measured throughput moved from the first optimistic 0.343 s/token to a median
of 0.4738, which cut the affordable pairs from 271 to 156. The Sievers matched
set is 160 peptides on its own, so the mandatory members now exceed the whole
budget.

`reduce_library` documents itself as "Select `budget` peptides" and never
trimmed the mandatory set, so it returned more than it promised and said
nothing. Trimming would have been worse: the Sievers split is the control set
the headline ROC is computed on, and quietly shortening it weakens the
measurement it exists to support. So the overrun is reported, and these tests
pin that it is reported rather than absorbed in either direction.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate.diversity import reduce_library


@dataclass
class _Peptide:
    peptide_id: str
    source: str
    sequence: str
    parent_peptide_id: str | None = None


def _library(benchmark: int, sievers: int, discovery: int = 0) -> list:
    peptides = []
    for i in range(benchmark):
        peptides.append(_Peptide(f"bench{i}", "benchmark", "ACDEFGHIKL"))
    for i in range(sievers):
        peptides.append(_Peptide(f"sv{i}", "sievers_zf", "MNPQRSTVWY"))
    for i in range(discovery):
        peptides.append(_Peptide(f"disc{i}", "curated_degron", "ACDEFGHIKL"))
    return peptides


def test_mandatory_members_are_not_trimmed_to_fit_the_budget():
    """The real shape of the problem: 167 mandatory against a budget of 156."""
    peptides = _library(benchmark=7, sievers=160)
    result = reduce_library(peptides, budget=156)

    assert len(result.selected_ids) == 167, "a control was dropped to hit a number"
    assert result.over_budget_by == 11
    assert result.status.startswith("over_budget")
    assert any("not trimmed" in note for note in result.notes)


def test_an_overrun_campaign_says_it_has_no_room_for_discovery():
    peptides = _library(benchmark=7, sievers=160, discovery=500)
    result = reduce_library(peptides, budget=156)

    assert result.diverse_ids == [], "discovery ran despite no headroom"
    assert any("calibration only" in note for note in result.notes)


def test_a_budget_that_fits_reports_no_overrun():
    peptides = _library(benchmark=7, sievers=160)
    result = reduce_library(peptides, budget=400)

    assert result.over_budget_by == 0
    assert result.status == "within_budget"
    assert result.notes == []


def test_the_benchmark_panel_still_sorts_ahead_of_the_sievers_split():
    """Priority ordering is what makes the overrun safe: a run cut short by
    the wall clock must lose discovery from the tail, never a control from
    the middle."""
    peptides = _library(benchmark=7, sievers=160)
    result = reduce_library(peptides, budget=156)

    first_seven = result.selected_ids[:7]
    assert all(pid.startswith("bench") for pid in first_seven), first_seven


def _with_throughput(monkeypatch, tmp_path, seconds_per_token, representative_tokens):
    """A known throughput measurement, so these tests assert the logic.

    The first version of the test below asserted the status of
    projected_hours(167) against whatever throughput file happened to be on
    disk. It passed while that came from the benchmark campaign and failed
    the moment the chain remeasured on the corrected one, whose jobs are
    three times larger: a test coupled to a measurement it does not control
    (F45).
    """
    import json

    from nobble import paths
    from nobble.curate import diversity

    path = tmp_path / "throughput.json"
    path.write_text(json.dumps({
        "campaign": "synthetic",
        "median_seconds_per_token": seconds_per_token,
        "representative_tokens": representative_tokens,
        "seconds_per_representative_job": seconds_per_token * representative_tokens,
        "jobs_per_pair": 15,
    }))
    monkeypatch.setattr(paths, "THROUGHPUT", path)
    monkeypatch.setattr(diversity.paths, "THROUGHPUT", path)


def test_gate_g1_is_judged_against_max_compute_not_the_run_target(
    monkeypatch, tmp_path
):
    """The two budgets are close enough to talk yourself across, so the
    distinction is pinned here.

    48 hours is the per-run target that sizes affordable_pairs. 96 hours is
    the Gate G1 threshold. A set that overruns the first is a scheduling
    fact the priority ordering handles; treating it as a gate would stop an
    unattended build.
    """
    from nobble.curate.diversity import projected_hours

    # 0.5028 s/token x 180 tokens = 90.5 s a job. 167 pairs x 15 jobs is
    # then 63 h: over the 48-hour target, well under the 96-hour gate.
    _with_throughput(monkeypatch, tmp_path, 0.5028, 180)
    result = projected_hours(167)
    assert result["status"] == "within_max_compute"
    assert result["gate_g1_open"] is False
    assert result["over_wall_clock_target"] > 0, "this set does overrun the 48h target"
    assert result["projected_hours"] < result["max_compute_hours"]


def test_a_genuinely_unaffordable_set_does_open_gate_g1(monkeypatch, tmp_path):
    from nobble.curate.diversity import projected_hours

    # The same rate, six times the pairs: 377 h.
    _with_throughput(monkeypatch, tmp_path, 0.5028, 180)
    result = projected_hours(1000)
    assert result["gate_g1_open"] is True
    assert result["status"] == "gate_g1_open"


def test_a_token_total_projects_from_real_job_sizes(monkeypatch, tmp_path):
    """The defect this guards. Throughput measured on a campaign whose
    median job is 397 tokens projected a campaign whose median job is 124
    at 104 hours and opened Gate G1 on a 54-hour run.

    The per-token rate transfers between campaigns; a representative job
    does not."""
    from nobble.curate.diversity import projected_hours

    _with_throughput(monkeypatch, tmp_path, 0.4, 397)

    # 2,370 jobs of a 397-token representative: the old method.
    without = projected_hours(158)
    # The same campaign's real tokens: 2,370 jobs averaging 166 tokens.
    with_tokens = projected_hours(158, total_tokens=2370 * 166)

    assert without["projected_hours"] > with_tokens["projected_hours"] * 2
    assert without["gate_g1_open"] is True
    assert with_tokens["gate_g1_open"] is False
    # And each says which basis it used, so the difference is explicable.
    assert "397-token job" in without["basis"]
    assert "tokens at the measured" in with_tokens["basis"]


def test_the_projection_names_the_campaign_its_representative_job_came_from(
    monkeypatch, tmp_path
):
    """Without a token total the estimate assumes the measured campaign's
    job-size mix, and has to say so rather than presenting one number."""
    from nobble.curate.diversity import projected_hours

    _with_throughput(monkeypatch, tmp_path, 0.4, 397)
    basis = projected_hours(158)["basis"]
    assert "synthetic" in basis, basis
    assert "not necessarily" in basis, basis
