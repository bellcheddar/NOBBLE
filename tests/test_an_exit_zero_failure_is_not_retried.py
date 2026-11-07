"""A clean exit with no result is not retried; a crash still is.

The runner retries once. F100 established that the budget is per job rather
than per attempt, and its reasoning about timeouts is that re-running an
identical command against an identical input "is the one retry guaranteed to
end the same way, because nothing about it changed".

That applies verbatim to a job which exits 0 and writes no confidence JSON.
An exit code of 0 is Boltz saying it finished, so there is no transient fault
for a second attempt to get past. Measured on the only pair that reaches this
branch, bench06's 1,223-token refinements: six jobs, two attempts each,
twelve attempts and no success, every duration inside 1.7 per cent of 9,513
seconds. The retry spent the second half of each job's budget reproducing the
first half's outcome (F289).

A crash is a different case and is still retried once, which is what the
fallback ladder asks for.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import runner


def _run(tmp_path, monkeypatch, outcomes):
    """Run one job, with `_run_boltz` returning each outcome in turn.

    The job and settings dicts are the shape
    `test_unused_affordances.py` already uses for this, rather than a
    `settings_from_config` call: the first version of this file built them by
    hand, left out `seed`, and every test failed on a KeyError in the command
    builder before reaching the branch under test.
    """
    calls = []

    def fake_run_boltz(command, env, timeout):
        calls.append(timeout)
        return outcomes[min(len(calls) - 1, len(outcomes) - 1)]

    monkeypatch.setattr(runner, "_run_boltz", fake_run_boltz)
    monkeypatch.setattr(runner, "_read_outputs",
                        lambda output_dir, job_id: (None, None, None,
                                                    "no confidence JSON written"))
    outcome = runner.run_job(
        {"job_id": "j1", "seed": 1, "yaml": str(tmp_path / "j1.yaml"),
         "tokens": 150, "timeout_seconds": 600},
        tmp_path,
        {"recycles": 3, "diffusion_samples": 1, "potentials": False,
         "device": "mps", "job_timeout_seconds": 600},
    )
    return outcome, calls


def test_an_exit_zero_with_no_result_is_attempted_once(tmp_path, monkeypatch):
    outcome, calls = _run(tmp_path, monkeypatch, [("ok", 0, "", "")])
    assert len(calls) == 1, (
        f"{len(calls)} attempt(s): the clean-exit failure is being retried, "
        "which spends the rest of the budget reproducing the same outcome")
    assert outcome.attempts == 1, outcome
    assert "exit 0" in outcome.status or "exit 0" in outcome.detail, outcome


def test_a_crash_is_still_retried_once(tmp_path, monkeypatch):
    """The fallback ladder asks for one retry, and a crash may be transient."""
    outcome, calls = _run(tmp_path, monkeypatch, [("ok", 1, "", "boom")])
    assert len(calls) == 2, (
        f"{len(calls)} attempt(s): a crash should still get its one retry")
    assert outcome.attempts == 2, outcome


def test_the_second_attempt_still_gets_what_is_left_of_the_budget(
        tmp_path, monkeypatch):
    """F100: per job, not per attempt, so the retry cannot double the cap."""
    outcome, calls = _run(tmp_path, monkeypatch, [("ok", 1, "", "boom")])
    assert len(calls) == 2, calls
    assert calls[1] <= calls[0], (
        f"the retry was given {calls[1]}s against the first attempt's "
        f"{calls[0]}s, so the budget is per attempt again")


def test_the_reason_is_kept_on_the_record(tmp_path, monkeypatch):
    """F238: the tail is the only information this branch has."""
    outcome, _ = _run(tmp_path, monkeypatch, [("ok", 0, "", "")])
    assert "said nothing" in outcome.detail or ":" in outcome.detail, outcome
