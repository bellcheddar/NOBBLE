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


def test_gate_g1_is_judged_against_max_compute_not_the_run_target():
    """The two budgets are close enough to talk yourself across, so the
    distinction is pinned here.

    48 hours is the per-run target that sizes affordable_pairs. 96 hours is
    the Gate G1 threshold. The calibration set projects to ~51 hours: over
    the target, nowhere near the gate. Treating that as a gate would stop an
    unattended build for a scheduling fact the priority ordering handles.
    """
    from nobble.curate.diversity import projected_hours

    result = projected_hours(167)
    assert result["status"] == "within_max_compute"
    assert result["gate_g1_open"] is False
    assert result["over_wall_clock_target"] > 0, "this set does overrun the 48h target"
    assert result["projected_hours"] < result["max_compute_hours"]


def test_a_genuinely_unaffordable_set_does_open_gate_g1():
    from nobble.curate.diversity import projected_hours

    result = projected_hours(1000)
    assert result["gate_g1_open"] is True
    assert result["status"] == "gate_g1_open"
