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


def test_the_watchdog_only_reads():
    """It is armed unattended for days beside a running campaign, so it must
    not be able to act on one. The only `kill` in it is in prose."""
    source = (ROOT / "nobble" / "execute" / "watchdog.py").read_text()
    code = "\n".join(
        line for line in source.splitlines()
        if not line.strip().startswith("#")
    )
    # Strip docstrings crudely: everything between triple quotes.
    import re

    code = re.sub(r'""".*?"""', "", code, flags=re.S)
    for forbidden in ("os.kill", "subprocess", "write_text", "unlink",
                      "os.remove", ".kill("):
        assert forbidden not in code, forbidden
