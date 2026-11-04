"""Shell entry points must call the Python they claim to call.

Two defects in one day came from a script invoking a module with arguments
that module does not accept, or dropping an argument it was given. Neither
fails until the stage runs, and by then the compute it was meant to drive
has either been spent or skipped.

These parse the scripts rather than executing them: they are GPU entry
points, and running them to find out is the thing being avoided.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _scripts() -> list[Path]:
    return sorted((ROOT / "tools").glob("*.sh")) + sorted((ROOT / "deploy").glob("*.sh"))


def test_every_shell_script_parses():
    for script in _scripts():
        result = subprocess.run(["bash", "-n", str(script)],
                                capture_output=True, text=True)
        assert result.returncode == 0, f"{script.name}: {result.stderr}"


def test_the_runner_is_never_given_a_positional_campaign():
    """nobble.execute.runner takes --campaign. tier2.sh passed the campaign
    positionally, so tier 2 would have died on argparse the moment the chain
    reached it, after the main campaign's 52 hours."""
    # Only module invocations, not Python imports. The first version
    # matched "from nobble.execute.runner import disk_gate" in a script
    # that reads the gate, which is not a CLI call at all.
    pattern = re.compile(r"-m\s+nobble\.execute\.runner\s+(?!--)(?!\"\$@\")\S")
    offenders = []
    for script in _scripts():
        for number, line in enumerate(script.read_text().splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{script.name}:{number}: {line.strip()}")
    assert not offenders, "positional campaign passed to the runner:\n" + "\n".join(offenders)


def test_the_runner_accepts_the_flags_the_scripts_use():
    """Assert against the parser rather than a remembered signature."""
    from nobble.execute import runner

    source = Path(runner.__file__).read_text()
    for flag in ("--campaign", "--tier", "--limit", "--throughput"):
        assert f'"{flag}"' in source, flag


def test_refresh_passes_its_campaign_to_the_atlas():
    """refresh.sh accepted a campaign, scored it, then published a
    different one because build_atlas was called bare."""
    text = (ROOT / "tools" / "refresh.sh").read_text()
    assert 'build_atlas.py "$CAMPAIGN"' in text, (
        "build_atlas is being called without the campaign refresh.sh just scored"
    )


def test_no_gpu_runner_aborts_before_scoring_what_ran():
    """The runner exits 1 when any job failed. A script with `set -e` then
    dies before its scoring step, throwing away the jobs that succeeded to
    report a failure the log already shows. tier2.sh did this."""
    runners = ["run_queue.sh", "run_corrected.sh", "run_design.sh", "tier2.sh",
               "run_chain.sh"]
    offenders = []
    for name in runners:
        text = (ROOT / "tools" / name).read_text()
        for line in text.splitlines():
            if line.strip().startswith("set -") and "e" in line.split()[1].lstrip("-"):
                offenders.append(f"{name}: {line.strip()}")
    assert not offenders, "set -e in a runner that must score partial work:\n" + "\n".join(offenders)


def test_the_gpu_wait_does_not_wait_for_its_own_session():
    """A deadlock that would stall the whole chain silently.

    run_chain.sh runs inside tmux `nobble-chain`, and `nobble-chain` is in
    the session list it waits on. It currently blocks on `nobble-corrected`,
    which comes first, so the self-wait is unreached and untested in the
    live run: it would fire the moment the corrected campaign finishes, and
    the chain would wait for itself forever with nothing in the log but the
    line it had already printed.
    """
    import shutil

    import pytest

    if not shutil.which("tmux"):
        pytest.skip("tmux not available")

    session = "nobble-skiptest"

    # Written to a file rather than passed as `bash -c '...'`. The script
    # has to narrow NOBBLE_GPU_PATTERN, because the guard grew a second half
    # that waits for the runner process itself (F60) and on a machine with a
    # campaign going that half never returns, which would hang this test on
    # a behaviour it is not about. A pattern in a command line is matched by
    # pgrep against the tmux process carrying it, which is a sibling and so
    # not excluded, and quoting it inside `bash -c '...'` closes the outer
    # quote. A file has neither problem.
    import tempfile

    handle = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False)
    handle.write(
        f"cd {ROOT}\n"
        "source tools/wait_for_gpu.sh\n"
        f"NOBBLE_GPU_SESSIONS=({session})\n"
        "NOBBLE_GPU_PATTERN='^$'\n"
        "nobble_wait_for_gpu && echo DID_NOT_WAIT_FOR_SELF\n"
        "sleep 5\n"
    )
    handle.close()

    subprocess.run(["tmux", "kill-session", "-t", session],
                   capture_output=True)
    subprocess.run(["tmux", "new-session", "-d", "-s", session,
                    f"bash {handle.name}"], capture_output=True)
    try:
        import time
        deadline = time.time() + 15
        output = ""
        while time.time() < deadline:
            output = subprocess.run(["tmux", "capture-pane", "-pt", session],
                                    capture_output=True, text=True).stdout
            if "DID_NOT_WAIT_FOR_SELF" in output:
                break
            time.sleep(1)
        assert "DID_NOT_WAIT_FOR_SELF" in output, (
            "the wait blocked on its own session:\n" + output)
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session],
                       capture_output=True)
        Path(handle.name).unlink(missing_ok=True)
