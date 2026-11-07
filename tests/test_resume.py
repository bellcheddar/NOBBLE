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

import pytest

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


def test_resume_against_the_real_campaign_queue(tmp_path):
    """The spec gate asks for this explicitly: "Queue survives a forced kill
    mid-run and resumes without duplicating or dropping a job (test this
    explicitly, do not assume it)."

    The other tests here exercise the state machine on handfuls of records.
    This runs it against the actual assembled campaign, 2,360 jobs, because
    the failure that matters is the one that only appears at the size the
    queue will really be. It simulates a realistic kill: most jobs done, one
    left recorded as running, and a torn final line from a write that did
    not finish.
    """
    import glob
    import random

    campaigns = sorted(glob.glob("campaigns/campaign_*"))
    if not campaigns:
        import pytest
        pytest.skip("no assembled campaign to test against")

    queue = Path(campaigns[-1]) / "queue.jsonl"
    if not queue.exists():
        import pytest
        pytest.skip("campaign has no queue")

    jobs = [json.loads(line) for line in queue.read_text().splitlines() if line.strip()]
    assert len(jobs) > 100, "this test is about scale"

    random.seed(1)
    done = {job["job_id"] for job in random.sample(jobs, len(jobs) // 2)}
    victim = next(job["job_id"] for job in jobs if job["job_id"] not in done)

    lines = [_done(job_id) for job_id in sorted(done)]
    lines.append(_running(victim))
    state = tmp_path / "state.jsonl"
    # A torn final record, as a kill mid-write leaves.
    state.write_text("".join(lines) + '{"job_id": "torn", "sta')

    # completed() returns job_id -> record, not a bare set.
    resumed = set(completed(state))
    pending = [job for job in jobs if job["job_id"] not in resumed]

    assert resumed == done, "a torn final line lost earlier history"
    assert victim in {job["job_id"] for job in pending}, "a job left running was not re-queued"
    assert not (done & {job["job_id"] for job in pending}), "a completed job was re-queued"
    assert len(pending) + len(resumed) == len(jobs), "a job was dropped"


def test_a_failed_attempt_is_announced_before_the_job_resolves(capsys, tmp_path,
                                                               monkeypatch):
    """An 84-minute failed attempt was invisible in the chain log.

    The queue line prints once, the state row keeps saying `running`, and the
    only way to tell a retry from one slow job was to notice the Boltz child's
    elapsed time reset in the process table. The budget is per job (F100), so
    the retry spends what the failed attempt left: on a job carrying 39,000
    seconds that is hours of loss with nothing said (F233).
    """
    from nobble.execute import runner as runner_module

    calls = {"n": 0}

    def _fail_then_fail(command, env, timeout):
        calls["n"] += 1
        return "ok", 1, "", f"boom {calls['n']}"

    monkeypatch.setattr(runner_module, "_run_boltz", _fail_then_fail)
    monkeypatch.setattr(runner_module, "RETRIES", 1)

    campaign = tmp_path / "campaign_x"
    (campaign / "outputs").mkdir(parents=True)
    job = {"job_id": "pairX__ternary__unconstrained__seed1", "tokens": 10,
           "yaml": str(tmp_path / "x.yaml"), "timeout_seconds": 600,
           "seed": 1, "pair_id": "pairX", "complex_type": "ternary"}
    (tmp_path / "x.yaml").write_text("version: 1\n")

    outcome = runner_module.run_job(
        job, campaign, runner_module.settings_from_config(tier=1))
    printed = capsys.readouterr().out

    assert outcome.status.startswith("failed"), outcome.status
    assert calls["n"] == 2, calls
    assert "attempt 1 failed after" in printed, printed
    assert "budget left" in printed, printed
    assert "no retries left" in printed, printed


def test_an_exit_zero_with_no_result_keeps_what_boltz_said(tmp_path,
                                                           monkeypatch):
    """The branch where the exit code tells you nothing threw the evidence away.

    bench06's 1,223-token refinement exited 0 with an empty predictions
    directory, twice, 9,492 seconds across both attempts, and the reason is
    unrecoverable because this branch recorded only "exit 0 but no confidence
    JSON written". Boltz leaves no log of its own (F238).
    """
    from nobble.execute import runner as runner_module

    def _exit_zero_and_complain(command, env, timeout):
        return "ok", 0, "", "MPS backend out of memory (tried to allocate 40GB)"

    monkeypatch.setattr(runner_module, "_run_boltz", _exit_zero_and_complain)
    monkeypatch.setattr(runner_module, "RETRIES", 1)

    campaign = tmp_path / "campaign_y"
    (campaign / "outputs").mkdir(parents=True)
    (tmp_path / "y.yaml").write_text("version: 1\n")
    job = {"job_id": "pairY__ternary__unconstrained__seed1", "tokens": 10,
           "yaml": str(tmp_path / "y.yaml"), "timeout_seconds": 600,
           "seed": 1, "pair_id": "pairY", "complex_type": "ternary"}

    outcome = runner_module.run_job(
        job, campaign, runner_module.settings_from_config(tier=1))

    assert outcome.status.startswith("failed"), outcome.status
    assert "exit 0 but" in outcome.detail, outcome.detail
    assert "out of memory" in outcome.detail, (
        "the runner discarded what Boltz said on the one path where the exit "
        f"code carries no information: {outcome.detail}")


def test_an_exit_zero_that_said_nothing_says_that(tmp_path, monkeypatch):
    """Silence recorded as silence, not as an empty string."""
    from nobble.execute import runner as runner_module

    monkeypatch.setattr(runner_module, "_run_boltz",
                        lambda command, env, timeout: ("ok", 0, "", ""))
    monkeypatch.setattr(runner_module, "RETRIES", 0)

    campaign = tmp_path / "campaign_z"
    (campaign / "outputs").mkdir(parents=True)
    (tmp_path / "z.yaml").write_text("version: 1\n")
    job = {"job_id": "pairZ__ternary__unconstrained__seed1", "tokens": 10,
           "yaml": str(tmp_path / "z.yaml"), "timeout_seconds": 600,
           "seed": 1, "pair_id": "pairZ", "complex_type": "ternary"}

    outcome = runner_module.run_job(
        job, campaign, runner_module.settings_from_config(tier=1))
    assert "and said nothing" in outcome.detail, outcome.detail


def test_an_empty_job_id_cannot_clear_the_whole_outputs_directory(tmp_path):
    """`Path("x/outputs") / ""` is `Path("x/outputs")`.

    So a queue row with an empty job id would aim run_job's rmtree at the
    campaign's entire outputs directory. For the main campaign that is 2,360
    jobs' structures, which is weeks of inference. The assembler cannot
    produce such a row, which is the reachability `cd ""` had in F241.
    """
    from nobble.execute import runner as runner_module

    campaign = tmp_path / "campaign_guard"
    outputs = campaign / "outputs"
    (outputs / "someone_elses_job").mkdir(parents=True)
    (outputs / "someone_elses_job" / "structure.cif").write_text("data")

    for bad in ("", "..", "a/b", "/absolute"):
        with pytest.raises(ValueError, match="single path component"):
            runner_module.run_job(
                {"job_id": bad, "tokens": 10, "yaml": str(tmp_path / "g.yaml"),
                 "seed": 1, "pair_id": "p", "complex_type": "ternary"},
                campaign, runner_module.settings_from_config(tier=1))

    assert (outputs / "someone_elses_job" / "structure.cif").exists(), (
        "the guard let a malformed job id reach the rmtree")
