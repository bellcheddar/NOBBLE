"""The GPU guard waited on a name for the thing instead of the thing.

There is one MPS device, so two campaigns sharing it halve each other's
throughput and risk an out-of-memory. `nobble_wait_for_gpu` enforced that by
checking whether any of six tmux sessions existed.

A session name is a proxy. Kill a chain and its `run_queue` child keeps
running, outside every session the list knows, and the guard returns
immediately. I nearly did exactly that: to edit the chain script I
considered killing it and leaving its queue running, which would have let
the relaunched chain start a second campaign on the same device.

And `run_queue.sh`, the script that actually starts inference and the one
every other path reaches inference through, did not wait at all, though
`wait_for_gpu.sh` says it is "sourced by every script that starts
inference".

The guard now asks for the runner process itself, excluding its own
ancestry so a script inside a campaign never waits for the campaign that
launched it, and excluding `--throughput`, which rewrites a JSON from
results on disk and never opens the device (F60).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "tools" / "wait_for_gpu.sh"


MARKER = "nobble_gpu_guard_fake"


def _gpu_pids(pattern: str | None = None) -> set[str]:
    environment = dict(os.environ)
    if pattern:
        environment["NOBBLE_GPU_PATTERN"] = pattern
    completed = subprocess.run(
        ["bash", "-c", f"source {GUARD}; nobble_gpu_pids"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    return set(completed.stdout.split())


def _fake(argv0: str):
    """A process whose command line matches, without being a runner.

    argv[0] is what `pgrep -f` reads, so /bin/sleep can wear the name of a
    campaign. Spawning a real runner to test this would put a second job on
    the GPU, which is the thing being guarded against.
    """
    return subprocess.Popen([argv0, "30"], executable="/bin/sleep")


@pytest.fixture()
def fake_runner():
    process = _fake("python -m nobble.execute.runner --campaign campaigns/x")
    time.sleep(0.3)
    try:
        yield process
    finally:
        process.kill()
        process.wait(timeout=10)


def test_a_runner_outside_every_tmux_session_is_seen(fake_runner):
    """The hazard. This process is in no session on the list."""
    assert str(fake_runner.pid) in _gpu_pids()


def test_a_throughput_run_is_not_a_gpu_run():
    """refresh.sh runs it after every campaign. It reads results already on
    disk, so treating it as inference would make the chain wait on its own
    bookkeeping."""
    process = _fake(
        "python -m nobble.execute.runner --campaign campaigns/x --throughput")
    time.sleep(0.3)
    try:
        assert str(process.pid) not in _gpu_pids()
    finally:
        process.kill()
        process.wait(timeout=10)


def test_a_finished_runner_is_not_waited_for(fake_runner):
    assert str(fake_runner.pid) in _gpu_pids()
    fake_runner.kill()
    fake_runner.wait(timeout=10)
    time.sleep(0.3)
    assert str(fake_runner.pid) not in _gpu_pids()


def test_the_ancestry_is_computed_and_includes_this_shell():
    """What can actually be demonstrated about the exclusion.

    The point of excluding ancestors is that a script inside a campaign
    must not wait for the campaign that launched it. On macOS `pgrep -f`
    already omits its own ancestry, parent and grandparent alike (checked
    both ways while writing this), so removing the exclusion changes
    nothing observable here and a test claiming to cover it would be
    claiming more than it can show. What is observable is that the chain
    is computed at all and contains the asking shell, so a platform whose
    pgrep does report ancestors is covered by the same line.
    """
    completed = subprocess.run(
        ["bash", "-c", f"echo $$; source {GUARD}; nobble_ancestor_pids"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    own, _, chain = completed.stdout.partition("\n")
    ancestors = chain.split()
    assert own.strip() in ancestors, (
        f"the shell is not in its own ancestry: {completed.stdout!r}")
    assert len(ancestors) > 1, "no parent was walked to"


def test_the_wait_blocks_until_the_device_is_free():
    """That it waits, not only that it can tell. Removing the wait while
    keeping the detection passed every other test in this file.

    Calls the process half directly: with a campaign in a tmux session on
    this machine the session half never returns, so going through
    `nobble_wait_for_gpu` would hang rather than test anything.
    """
    process = _fake(f"python -m nobble.execute.runner {MARKER}")
    time.sleep(0.3)
    assert str(process.pid) in _gpu_pids(MARKER)

    started = time.monotonic()
    waiter = subprocess.Popen(
        ["bash", "-c", f"source {GUARD}; nobble_wait_for_runners"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env={**os.environ, "NOBBLE_GPU_POLL_SECONDS": "1",
                        # Only this test's own fake, because a real
                        # campaign on this machine would never release.
                        "NOBBLE_GPU_PATTERN": MARKER},
    )
    try:
        # It must still be waiting while the fake runner holds the device.
        with pytest.raises(subprocess.TimeoutExpired):
            waiter.wait(timeout=3)

        process.kill()
        process.wait(timeout=10)
        waiter.wait(timeout=30)
        assert waiter.returncode == 0
        assert time.monotonic() - started >= 3
    finally:
        if waiter.poll() is None:
            waiter.kill()
        if process.poll() is None:
            process.kill()


def test_the_wait_returns_when_nothing_holds_the_device():
    """A guard that can block forever on a quiet machine is worse than no
    guard. With no foreign runner this must return promptly."""
    if _gpu_pids():
        pytest.skip("a campaign is running on this machine")
    start = time.monotonic()
    completed = subprocess.run(
        ["bash", "-c", f"source {GUARD}; nobble_wait_for_gpu"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert time.monotonic() - start < 30


def test_the_queue_runner_waits_before_starting_inference():
    """The script that was not waiting. Checked by position, because a
    source line after the runner has already launched would be decoration."""
    source = (ROOT / "tools" / "run_queue.sh").read_text()
    assert "nobble_wait_for_gpu" in source, "run_queue.sh still does not wait"
    assert source.index("nobble_wait_for_gpu") < source.index(
        "nobble.execute.runner"), "it waits after starting the runner"


def test_every_script_that_starts_inference_waits():
    """The claim in wait_for_gpu.sh's own header, as a sweep. It was false
    for run_queue.sh for as long as the file has existed."""
    offenders = {}
    for path in sorted((ROOT / "tools").glob("*.sh")):
        source = path.read_text()
        # An invocation, not a mention: status.sh imports disk_gate from the
        # runner module and starts nothing, and a sweep that cannot tell the
        # difference reports a file that is not wrong.
        invocations = [line for line in source.splitlines()
                       if "-m nobble.execute.runner" in line
                       and not line.lstrip().startswith("#")]
        if not invocations:
            continue
        if all("--throughput" in line for line in invocations):
            continue            # measures from disk, never opens the device
        if "nobble_wait_for_gpu" not in source:
            offenders[path.name] = invocations[0].strip()
    assert not offenders, (
        f"script(s) that start inference without waiting for the GPU: {offenders}"
    )


def test_the_guard_runs_both_halves():
    """Splitting them is only safe if the caller still does both. A guard
    that waits for sessions and forgets processes is the bug this started
    from, arriving by refactor instead."""
    source = GUARD.read_text()
    body = source[source.index("nobble_wait_for_gpu() {"):]
    assert "nobble_wait_for_sessions" in body
    assert "nobble_wait_for_runners" in body
