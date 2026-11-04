"""The queue must survive a Boltz job that will not die.

This exists because of a real stall. corr06_RBM39_DCAF15 ternary seed 1 wedged
in an uninterruptible Metal wait. Its 5400s timeout fired on schedule and
subprocess.run sent SIGKILL, then called wait() with no bound of its own: the
child could not be reaped, so the cleanup blocked and the corrected campaign
sat still for 3h45m with no log line and no failed job (F20). A 2,360-job
unattended campaign cannot have that failure mode.

A process that truly ignores SIGKILL cannot be built in userspace, so the
unkillable branch is driven directly and the killable-overrun branch is run
for real against a sleeping child.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import runner  # noqa: E402


def test_an_overrunning_job_is_killed_and_reported_rather_than_waited_on():
    """The real path: a child that overruns but can be killed."""
    started = time.monotonic()
    status, _returncode, _out, _err = runner._run_boltz(
        [sys.executable, "-c", "import time; time.sleep(60)"], None, timeout=1.0
    )
    elapsed = time.monotonic() - started
    assert status == "timeout"
    # The point of the fix: it comes back promptly instead of blocking.
    assert elapsed < 20, f"took {elapsed:.1f}s to give up on a 1s timeout"


def test_the_bound_holds_even_when_the_child_ignores_sigterm():
    """SIGKILL is not catchable, but an ignored SIGTERM must not matter."""
    child = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "time.sleep(60)\n"
    )
    started = time.monotonic()
    status, _rc, _out, _err = runner._run_boltz(
        [sys.executable, "-c", child], None, timeout=1.0
    )
    assert status == "timeout"
    assert time.monotonic() - started < 20


def test_an_unkillable_job_fails_the_job_without_retrying_it(monkeypatch, tmp_path):
    """An abandoned orphan may still hold the GPU, so it gets one go, not two.

    The retry exists for a transient crash. Re-running a job whose predecessor
    is still wedged on the device turns one lost job into two.
    """
    calls = []

    def never_dies(command, env, timeout):
        calls.append(command)
        return "unkillable", None, "", ""

    monkeypatch.setattr(runner, "_run_boltz", never_dies)
    monkeypatch.setattr(runner, "boltz_environment", lambda: None)

    job = {"job_id": "wedged", "yaml": "x.yaml", "seed": 1, "tokens": 1287}
    settings = {
        "recycles": 3, "diffusion_samples": 1, "potentials": False,
        "device": "mps", "job_timeout_seconds": 5400,
    }
    outcome = runner.run_job(job, tmp_path, settings)

    assert len(calls) == 1, f"retried an unkillable job {len(calls)} times"
    assert outcome.status.startswith("failed:")
    assert "SIGKILL" in outcome.status
    assert outcome.attempts == 1


def test_a_killable_timeout_is_still_retried(monkeypatch, tmp_path):
    """The opposite case, so the fix does not quietly disable the retry."""
    calls = []

    def always_times_out(command, env, timeout):
        calls.append(command)
        return "timeout", None, "", ""

    monkeypatch.setattr(runner, "_run_boltz", always_times_out)
    monkeypatch.setattr(runner, "boltz_environment", lambda: None)

    job = {"job_id": "slow", "yaml": "x.yaml", "seed": 1, "tokens": 400}
    settings = {
        "recycles": 3, "diffusion_samples": 1, "potentials": False,
        "device": "mps", "job_timeout_seconds": 5400,
    }
    outcome = runner.run_job(job, tmp_path, settings)

    assert len(calls) == runner.RETRIES + 1
    assert "timeout after 5400s" in outcome.status


def test_cleanup_is_bounded_when_the_child_cannot_be_fully_drained(monkeypatch):
    """The closest reproducible analogue of the Metal wedge.

    A process that ignores SIGKILL cannot be built in userspace, so the
    original stall cannot be reproduced directly. This reproduces the same
    *class* of fault: cleanup after the kill that has no bound. The child
    leaves a grandchild holding the stdout pipe open, so draining it after the
    child dies never completes. subprocess.run's POSIX cleanup path would sit
    there indefinitely; _run_boltz must give up and return.
    """
    monkeypatch.setattr(runner, "KILL_GRACE_SECONDS", 4)
    child = (
        "import subprocess, sys, time\n"
        # the grandchild inherits stdout and outlives the kill
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "time.sleep(120)\n"
    )
    started = time.monotonic()
    status, _rc, _out, _err = runner._run_boltz(
        [sys.executable, "-c", child], None, timeout=1.0
    )
    elapsed = time.monotonic() - started
    assert status == "unkillable", status
    assert elapsed < 30, f"cleanup ran for {elapsed:.1f}s: it is not bounded"
