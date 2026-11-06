"""A killed job must not look like a hung one for the rest of the campaign.

The state log is append-only, so a job killed between its `running` record
and its outcome leaves `running` as its last word. The resume path does not
mind: `running` is not terminal, so the job is re-run. The watchdog does
mind, because it reads the same log to tell a working campaign from a stopped
one, and it reported two jobs killed by hand as 30.9 and 38.9 minutes overdue
against 5.8 expected while the GPU was working through an unrelated job.

`run_chain.sh` prints the watchdog only when its verdict stops being "ok", so
a detector that cannot stop firing arrives as noise that never stops, and
every later real stall is inside it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from nobble.execute import runner


def _state(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "state.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def test_a_job_left_running_is_found(tmp_path):
    path = _state(tmp_path, [
        {"job_id": "a", "status": "running", "started_at": 1.0},
        {"job_id": "a", "status": "done", "seconds": 2.0},
        {"job_id": "b", "status": "running", "started_at": 3.0},
    ])
    assert runner.abandoned_in_progress(path) == ["b"]


def test_a_finished_job_is_not_found_whatever_the_order(tmp_path):
    # Only the last record for a job counts. A job re-run after a kill has a
    # `running` record earlier in the file than its `done`.
    path = _state(tmp_path, [
        {"job_id": "a", "status": "running", "started_at": 1.0},
        {"job_id": "a", "status": "abandoned", "abandoned_at": 2.0},
        {"job_id": "a", "status": "running", "started_at": 3.0},
        {"job_id": "a", "status": "done", "seconds": 4.0},
    ])
    assert runner.abandoned_in_progress(path) == []


def test_an_already_abandoned_job_is_not_found_again(tmp_path):
    # Otherwise every restart appends another record for the same job and the
    # log grows without bound.
    path = _state(tmp_path, [
        {"job_id": "a", "status": "running", "started_at": 1.0},
        {"job_id": "a", "status": "abandoned", "abandoned_at": 2.0},
    ])
    assert runner.abandoned_in_progress(path) == []


def test_a_failed_job_is_not_treated_as_abandoned(tmp_path):
    path = _state(tmp_path, [
        {"job_id": "a", "status": "running", "started_at": 1.0},
        {"job_id": "a", "status": "failed: boltz exited 1", "seconds": 5.0},
    ])
    assert runner.abandoned_in_progress(path) == []


def test_a_torn_tail_does_not_hide_an_abandoned_job(tmp_path):
    # The append-only log tolerates a torn final line by design, and a kill is
    # exactly when one is written.
    path = tmp_path / "state.jsonl"
    path.write_text(
        json.dumps({"job_id": "a", "status": "running", "started_at": 1.0}) + "\n"
        + '{"job_id": "b", "status": "run'
    )
    assert runner.abandoned_in_progress(path) == ["a"]


def test_a_missing_state_file_is_empty_rather_than_an_error(tmp_path):
    assert runner.abandoned_in_progress(tmp_path / "nothing.jsonl") == []


def test_closing_out_does_not_mark_the_job_done(tmp_path):
    # The whole point: the job is still re-run. `abandoned` must not be
    # terminal, or a kill would silently drop a job from the campaign.
    assert "abandoned" not in runner.TERMINAL_STATUSES
    path = _state(tmp_path, [
        {"job_id": "a", "status": "running", "started_at": 1.0},
        {"job_id": "a", "status": "abandoned", "abandoned_at": 2.0},
    ])
    assert "a" not in runner.completed(path)


def test_the_record_written_carries_a_reason_and_a_time(tmp_path):
    # Written the way the runner writes it, then read back the way the
    # watchdog reads it.
    path = _state(tmp_path, [
        {"job_id": "a", "status": "running", "started_at": time.time()},
    ])
    before = len(path.read_text().splitlines())
    with path.open("a") as handle:
        for job_id in runner.abandoned_in_progress(path):
            handle.write(json.dumps({
                "job_id": job_id, "status": "abandoned",
                "abandoned_at": time.time(),
                "reason": "a previous runner exited while this job was "
                          "running, so no outcome was recorded",
            }) + "\n")
    lines = path.read_text().splitlines()
    assert len(lines) == before + 1
    record = json.loads(lines[-1])
    assert record["status"] == "abandoned"
    assert record["reason"]
    assert record["abandoned_at"] > 0
    # And a second pass finds nothing, so this is idempotent.
    assert runner.abandoned_in_progress(path) == []
