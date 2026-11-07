"""Time spent on a job that failed is still time spent.

`hours_spent` summed `results*.jsonl`, which the runner appends to only when
`outcome.status == "done"`. So the one instrument that answers "how much of
the compute budget is left" could not see any work that failed, and
`remaining = max_compute_hours - spent` reported that time as still
available.

bench06's refinement is the case that exposed it: it exits 0 without writing
a confidence JSON after about two and a half hours, ten jobs of it, roughly
26 hours that the budget read as zero (F255).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import budget


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _campaign(root: Path) -> Path:
    directory = root / "campaign_fixture"
    directory.mkdir()
    # One job that succeeded and one that failed, as the runner records them:
    # the success in both files, the failure in state alone.
    _write(directory / "results.jsonl",
           [{"job_id": "a", "status": "done", "seconds": 3600.0, "tokens": 400}])
    _write(directory / "state.jsonl", [
        {"job_id": "a", "status": "running", "started_at": 0.0},
        {"job_id": "a", "status": "done", "seconds": 3600.0, "tokens": 400},
        {"job_id": "b", "status": "running", "started_at": 0.0},
        {"job_id": "b", "status": "failed: exit 0 but no confidence JSON "
                                 "written", "seconds": 7200.0, "tokens": 1223},
    ])
    return directory


def test_a_failed_job_counts_against_the_budget(tmp_path):
    _campaign(tmp_path)
    spent = budget.hours_spent(tmp_path)
    assert spent["failed_hours"] == 2.0, spent
    assert spent["hours"] == 3.0, spent


def test_a_success_is_not_counted_twice(tmp_path):
    """It appears in results.jsonl and in state.jsonl, with the same seconds.

    Summing all of state on top of results would double every finished job,
    which is the obvious way to write this fix and is wrong in the direction
    that closes the gate early.
    """
    _campaign(tmp_path)
    spent = budget.hours_spent(tmp_path)
    assert spent["succeeded_hours"] == 1.0, spent


def test_a_running_job_adds_nothing(tmp_path):
    """A job still going has no settled cost.

    `running` records carry `started_at` and no `seconds`, so they are
    excluded by the absence of the field rather than by the status, and this
    pins that: a fixture with nothing but a running record must read zero,
    not a number derived from the clock.
    """
    directory = tmp_path / "campaign_fixture"
    directory.mkdir()
    _write(directory / "state.jsonl",
           [{"job_id": "c", "status": "running", "started_at": 1.0}])
    spent = budget.hours_spent(tmp_path)
    assert spent["hours"] == 0.0, spent
    assert spent["failed_jobs"] == 0, spent


def test_the_failure_status_is_matched_by_shape_not_by_equality(tmp_path):
    """The status carries its reason, so `== "failed"` matches nothing.

    This is how the first draft of the measurement summed 0.0 and read as
    "no failed time" on a campaign with two failures on disk. The test keeps
    the arbitrary reason text in the fixture so an equality test cannot pass
    it.
    """
    directory = tmp_path / "campaign_fixture"
    directory.mkdir()
    _write(directory / "state.jsonl", [
        {"job_id": "d", "status": "failed: something nobody predicted",
         "seconds": 1800.0, "tokens": 400},
    ])
    spent = budget.hours_spent(tmp_path)
    assert spent["failed_hours"] == 0.5, spent


def test_the_gate_judges_the_remainder_against_the_larger_figure(tmp_path):
    """Whatever else changes, spend must not be understated.

    `gate_g1` computes `remaining = max_compute_hours - spent["hours"]`, so
    an understated spend overstates the headroom, which is the wrong
    direction for a gate that exists to stop a run before it overruns.
    """
    _campaign(tmp_path)
    spent = budget.hours_spent(tmp_path)
    assert spent["hours"] >= spent["succeeded_hours"], spent
    assert spent["hours"] == round(
        spent["succeeded_hours"] + spent["failed_hours"], 2), spent
