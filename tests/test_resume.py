"""Queue resumability (spec Phase 2 gate).

The spec is unusually direct about this one: "Queue survives a forced kill
mid-run and resumes without duplicating or dropping a job (test this
explicitly, do not assume it)." It matters because multi-day MPS runs hit OOM
and NaN diffusion steps, and a queue that cannot resume is unusable.

The real queue was observed resuming once, in passing, which is not the same as
testing it. These exercise the logic directly, including the cases a casual
observation would never produce: a kill in the middle of writing a checkpoint,
a job recorded as running but never finished, and a restart after the state
file has been appended to by two separate runs.

The runner is not invoked here: Boltz is, and the GPU is busy. What is tested
is the state machine that decides what to re-run, which is the part that
decides whether work is duplicated or dropped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.execute.runner import completed


def _write(path: Path, records: list[str]) -> None:
    path.write_text("".join(records))


def _done(job_id: str) -> str:
    return json.dumps({"job_id": job_id, "status": "done", "seconds": 1.0,
                       "tokens": 100}) + "\n"


def _running(job_id: str) -> str:
    return json.dumps({"job_id": job_id, "status": "running"}) + "\n"


def test_completed_jobs_are_skipped(tmp_path):
    state = tmp_path / "state.jsonl"
    _write(state, [_running("a"), _done("a"), _running("b"), _done("b")])
    assert set(completed(state)) == {"a", "b"}


def test_a_job_left_running_is_rerun_not_skipped(tmp_path):
    """A kill between starting and finishing must re-run that job.

    This is the dropped-job case: if a 'running' record counted as progress,
    the job killed mid-flight would never be retried and the campaign would
    silently lose it.
    """
    state = tmp_path / "state.jsonl"
    _write(state, [_done("a"), _running("b")])
    done = completed(state)
    assert "a" in done
    assert "b" not in done


def test_a_torn_final_line_does_not_lose_the_whole_history(tmp_path):
    """A kill mid-write leaves a partial line. Everything before it must survive.

    An append-only log read with a strict parser would raise here and the
    restart would re-run the entire campaign.
    """
    state = tmp_path / "state.jsonl"
    _write(state, [_done("a"), _done("b"), '{"job_id": "c", "status": "do'])
    done = completed(state)
    assert set(done) == {"a", "b"}


def test_a_torn_line_in_the_middle_does_not_hide_later_records(tmp_path):
    state = tmp_path / "state.jsonl"
    _write(state, [_done("a"), '{"job_id": "b", "sta\n', _done("c")])
    done = completed(state)
    assert set(done) == {"a", "c"}


def test_repeated_restarts_do_not_duplicate_work(tmp_path):
    """Three runs over the same queue must between them run each job once."""
    state = tmp_path / "state.jsonl"
    queue = ["a", "b", "c", "d", "e"]
    attempted: list[str] = []

    for batch in ([2, 2, 1]):
        done = completed(state)
        pending = [job for job in queue if job not in done][:batch]
        attempted.extend(pending)
        with state.open("a") as handle:
            for job in pending:
                handle.write(_running(job))
                handle.write(_done(job))

    assert attempted == queue, "a job was duplicated or dropped across restarts"
    assert len(attempted) == len(set(attempted))
    assert set(completed(state)) == set(queue)


def test_a_failed_job_is_retried_on_the_next_run(tmp_path):
    """Failure is not completion: the fallback ladder retries, then degrades."""
    state = tmp_path / "state.jsonl"
    _write(state, [json.dumps(
        {"job_id": "a", "status": "failed: mps out of memory"}) + "\n"])
    assert "a" not in completed(state)


def test_missing_state_file_means_everything_is_pending(tmp_path):
    assert completed(tmp_path / "never-written.jsonl") == {}
