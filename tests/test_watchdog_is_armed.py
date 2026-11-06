"""The stall detector has to run while a stall is possible.

`nobble.execute.watchdog` tells a working campaign apart from a stopped one.
That ambiguity is what F20 cost most of a night to: the queue sat still for
3h45m while every check that asked "is the process alive" answered yes. The
module is careful, separates an informational `overdue` from a `stalled` that
needs no tuning, and returns 0, 1 or 2 so a caller need not read its prose.

It was reachable only through `tools/status.sh`, and the chain calls that on
its last line. So for the forty-seven hours in which a stall can happen,
nothing consulted it, and it spoke once when the answer could no longer
matter. A detector that runs after the event is not a detector (F112).

`run_chain.sh` arms it for the length of the chain now, and these tests hold
the three things that make that real: it is armed before the first campaign
rather than after the last, it is taken down however the chain ends, and it
is keyed on the exit code rather than on the spacing of its output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHAIN = ROOT / "tools" / "run_chain.sh"


def test_the_chain_arms_it_before_running_anything():
    source = CHAIN.read_text()
    assert "watchdog_loop &" in source, "the chain no longer arms the watchdog"

    armed = source.index("watchdog_loop &")
    # The first thing the chain actually spends time on.
    for marker in ("nobble.execute.runner", "run_queue.sh", "tools/run_queue"):
        if marker in source:
            assert armed < source.index(marker), (
                f"the watchdog is armed after {marker}, so the first campaign "
                "runs unwatched"
            )
            break
    else:
        raise AssertionError("no campaign stage found in the chain")


def test_it_is_taken_down_however_the_chain_ends():
    """Otherwise a killed run leaves a loop polling a campaign nobody is
    running, and the next chain adds another."""
    source = CHAIN.read_text()
    assert "trap 'kill \"$WATCHDOG_PID\"" in source, source[:0]
    assert "EXIT" in source


def test_it_is_keyed_on_the_exit_code_and_not_on_the_printed_text():
    """The verdict's layout is presentation. F54 was a threshold duplicated
    into a template; keying on "   ok  " would be the same coupling."""
    source = CHAIN.read_text()
    loop = source[source.index("watchdog_loop() {"):source.index("watchdog_loop &")]
    assert "code=$?" in loop and '"$code" -ne 0' in loop, loop
    assert "grep" not in loop, "the loop greps the verdict instead of using the code"


def test_the_interval_comes_from_the_environment_and_not_a_literal():
    source = CHAIN.read_text()
    assert "NOBBLE_WATCHDOG_SECONDS" in source


def test_the_exit_code_is_what_the_loop_assumes():
    """The contract between the two. A healthy campaign must be 0, or the
    chain log fills with a line every ten minutes and stops being read."""
    result = subprocess.run(
        [str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python"),
         "-m", "nobble.execute.watchdog"],
        cwd=str(ROOT), capture_output=True, text=True,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode in (0, 1, 2), (result.returncode, result.stderr[-300:])


def _watchdog_code() -> str:
    """watchdog.py with comments and docstrings stripped, so prose about
    killing a job does not read as code that kills one."""
    import re

    source = (ROOT / "nobble" / "execute" / "watchdog.py").read_text()
    code = "\n".join(
        line for line in source.splitlines()
        if not line.strip().startswith("#")
    )
    return re.sub(r'""".*?"""', "", code, flags=re.S)


def test_the_watchdog_only_reads():
    """It is armed unattended for days beside a running campaign, so it must
    not be able to act on one. The only `kill` in it is in prose."""
    for forbidden in ("os.kill", "write_text", "unlink", "os.remove",
                      ".kill(", "rmtree", "os.system"):
        assert forbidden not in _watchdog_code(), forbidden


def test_the_only_command_the_watchdog_runs_is_pgrep():
    """`subprocess` was banned outright here until F216, which needed the
    watchdog to ask whether a runner is on the machine at all.

    The ban was a proxy for "cannot act", and a blanket proxy that has to be
    lifted stops protecting anything. So this names the one command instead:
    pgrep, which reads the process table and changes nothing. A
    `subprocess.run(["rm", ...])` would have been caught by the old ban and
    is caught by this.
    """
    import re

    code = _watchdog_code()
    assert "shell=True" not in code, "a shell can run anything"
    for construct in ("subprocess.Popen", "subprocess.call",
                      "subprocess.check_output", "subprocess.check_call"):
        assert construct not in code, (
            f"{construct}: the watchdog uses subprocess.run with a list argv"
        )
    calls = re.findall(r'subprocess\.run\(\s*\[\s*"([^"]+)"', code)
    assert calls, "no subprocess.run with a literal argv found"
    assert set(calls) == {"pgrep"}, calls
    # Every invocation is a literal list, so none of them is built at runtime
    # from anything a campaign directory could contain.
    assert len(calls) == code.count("subprocess.run("), (
        "a subprocess.run call does not open with a literal argv list"
    )
